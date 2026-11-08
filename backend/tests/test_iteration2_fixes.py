"""Iteration 2 retest: report fixes (COD write-off, cancel refund), discount overpay guard, CMS URL guard,
removed-line claims, positional line updates under concurrency, vehicle plate conflict."""
import threading
import pytest
from conftest import BASE_URL, uid, stock_of, ensure_stock
from test_predator_core import new_job, phone, pkg_line

B = BASE_URL + "/api"


def summ(owner, d):
    r = owner.get(f"{B}/reports/summary?start={d}&end={d}")
    assert r.status_code == 200
    return r.json()


def today(s):
    return s.get(f"{B}/reports/daily").json()["date"]


# ---- Report fix 1: returned COD order write-off ----
class TestCodWriteOff:
    def test_cod_return_write_off(self, kasir, owner, admin, items, pkg):
        for sku in ("TEST-BILED-01", "TEST-SHROUD-01", "TEST-RELAY-01"):
            ensure_stock(owner, items[sku]["id"], 3)
        d = today(owner)
        s0 = summ(owner, d)
        o = kasir.post(f"{B}/orders", json={"customer_name": f"TEST_cod_{uid()}", "customer_phone": phone(), "address": "Surabaya",
                                            "province": "Jawa Timur", "payment_type": "cod", "shipping_cost": 20000,
                                            "lines": [pkg_line(pkg, False)]}).json()
        assert o["total"] == 1520000
        assert kasir.post(f"{B}/orders/{o['id']}/ship", json={"resi": "T2"}).status_code == 200
        full = kasir.get(f"{B}/orders/{o['id']}").json()
        ret_items = {}
        for l in full["lines"]:
            for c in l["components"]:
                ret_items[c["item_id"]] = ret_items.get(c["item_id"], 0) + c["qty"] * l["qty"]
        r = admin.post(f"{B}/tx/order/{o['id']}/return", json={
            "items": [{"item_id": k, "qty": v, "condition": "layak"} for k, v in ret_items.items()],
            "refund_amount": 0, "reason": "TEST paket kembali"})
        assert r.status_code == 200, r.text
        rec = r.json()["returns"][-1]
        assert rec["write_off"] == 1500000
        s2 = summ(owner, d)
        dw = s2["write_off"] - s0["write_off"]
        assert dw == 1500000
        assert s2["net_revenue"] == s2["omzet_total"] - s2["return_refund"] - s2["write_off"]
        assert s2["gross_profit"] == s2["net_revenue"] - (s2["hpp"] - s2["return_hpp_back"])
        d_omzet = s2["omzet_total"] - s0["omzet_total"]
        d_net = s2["net_revenue"] - s0["net_revenue"]
        d_gp = s2["gross_profit"] - s0["gross_profit"]
        print(f"delta omzet={d_omzet} write_off={dw} net_revenue={d_net} gross_profit={d_gp}")
        # A fully returned unpaid COD order should be profit-neutral
        assert d_gp == 0, f"returned COD changes gross profit by {d_gp} (write_off includes shipping, omzet excludes it)"

    def test_cod_partial_returns_no_double_write_off(self, kasir, owner, admin, items, pkg):
        for sku in ("TEST-BILED-01", "TEST-SHROUD-01", "TEST-RELAY-01"):
            ensure_stock(owner, items[sku]["id"], 3)
        o = kasir.post(f"{B}/orders", json={"customer_name": f"TEST_cod_{uid()}", "customer_phone": phone(), "address": "Surabaya",
                                            "province": "Jawa Timur", "payment_type": "cod", "lines": [pkg_line(pkg, False)]}).json()
        kasir.post(f"{B}/orders/{o['id']}/ship", json={})
        comps = o["lines"][0]["components"]
        r1 = admin.post(f"{B}/tx/order/{o['id']}/return", json={"items": [{"item_id": comps[0]["item_id"], "qty": 1, "condition": "layak"}], "reason": "TEST part1"})
        assert r1.status_code == 200
        r2 = admin.post(f"{B}/tx/order/{o['id']}/return", json={"items": [{"item_id": comps[1]["item_id"], "qty": 1, "condition": "layak"}], "reason": "TEST part2"})
        if r2.status_code == 200:
            total_wo = sum(x["write_off"] for x in r2.json()["returns"])
            assert total_wo <= o["total"], f"write_off counted twice: {total_wo} > total {o['total']}"


# ---- Report fix 2: cancel refund of Masuk job ----
class TestCancelReport:
    def test_cancel_dp_refund_not_in_gross_profit(self, kasir, owner):
        d = today(owner)
        s0 = summ(owner, d)
        j = new_job(kasir, [{"type": "service", "name": "TEST jasa", "unit_price": 200000}])
        kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 100000, "method": "tunai"})
        r = owner.post(f"{B}/jobs/{j['id']}/cancel", json={"reason": "TEST batal", "refund_amount": 60000})
        assert r.status_code == 200
        s1 = summ(owner, d)
        assert s1["gross_profit"] - s0["gross_profit"] == 0
        assert s1["return_refund"] - s0["return_refund"] == 0
        assert s1["refund_total"] - s0["refund_total"] == 60000
        assert s1["net_cash"] - s0["net_cash"] == 40000
        assert s1["cancel_kept"] - s0["cancel_kept"] == 40000


# ---- Discount after full payment ----
class TestDiscountGuard:
    def test_request_after_full_payment_rejected(self, kasir, owner):
        j = new_job(kasir, [{"type": "service", "name": "TEST jasa", "unit_price": 100000}])
        kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 100000, "method": "tunai"})
        assert owner.post(f"{B}/tx/job/{j['id']}/discount", json={"amount": 20000, "reason": "test diskon"}).status_code == 400
        assert kasir.post(f"{B}/tx/job/{j['id']}/discount", json={"amount": 20000, "reason": "test diskon"}).status_code == 400
        g = kasir.get(f"{B}/jobs/{j['id']}").json()
        assert g["discount"] is None and g["total"] == 100000

    def test_partial_payment_allows_discount_within_limit(self, kasir, owner):
        j = new_job(kasir, [{"type": "service", "name": "TEST jasa", "unit_price": 100000}])
        kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 50000, "method": "tunai"})
        assert owner.post(f"{B}/tx/job/{j['id']}/discount", json={"amount": 60000, "reason": "terlalu besar"}).status_code == 400
        r = owner.post(f"{B}/tx/job/{j['id']}/discount", json={"amount": 50000, "reason": "pas"})
        assert r.status_code == 200 and r.json()["total"] == 50000

    def test_approve_rejected_when_total_below_paid(self, kasir, admin, owner):
        j = new_job(kasir, [{"type": "service", "name": "TEST jasa", "unit_price": 100000}])
        kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 50000, "method": "tunai"})
        r = kasir.post(f"{B}/tx/job/{j['id']}/discount", json={"amount": 20000, "reason": "langganan"})
        assert r.status_code == 200 and r.json()["discount"]["status"] == "pending"
        lid = r.json()["lines"][0]["lid"]
        assert admin.put(f"{B}/jobs/{j['id']}/lines/{lid}", json={"unit_price": 60000, "reason": "koreksi harga"}).status_code == 200
        r = owner.post(f"{B}/tx/job/{j['id']}/discount/decide", json={"approve": True})
        assert r.status_code == 400, r.text
        g = kasir.get(f"{B}/jobs/{j['id']}").json()
        assert g["discount"]["status"] == "pending"

    def test_line_edit_below_paid(self, kasir, admin):
        """Extra probe: admin line edit making total < paid (overpayment) is not guarded."""
        j = new_job(kasir, [{"type": "service", "name": "TEST jasa", "unit_price": 100000}])
        kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 80000, "method": "tunai"})
        lid = j["lines"][0]["lid"]
        r = admin.put(f"{B}/jobs/{j['id']}/lines/{lid}", json={"unit_price": 30000, "reason": "koreksi harga"})
        if r.status_code == 200:
            assert r.json()["total"] >= r.json()["paid"], f"overpaid via line edit: total {r.json()['total']} paid {r.json()['paid']}"


# ---- CMS URL guard ----
class TestCmsUrls:
    def test_nav_cta_href(self, admin):
        cms = {d["key"]: d for d in admin.get(f"{B}/cms").json()}
        nav = cms["navigation"]["draft"]
        try:
            assert admin.put(f"{B}/cms/navigation", json={"data": nav | {"cta_href": "javascript:alert(1)"}}).status_code == 400
            assert admin.put(f"{B}/cms/navigation", json={"data": nav | {"cta_href": " JaVaScRiPt:alert(1)"}}).status_code == 400
            for ok in ("/layanan", "#whatsapp", "https://wa.me/628123"):
                r = admin.put(f"{B}/cms/navigation", json={"data": nav | {"cta_href": ok}})
                assert r.status_code == 200, (ok, r.text)
        finally:
            admin.put(f"{B}/cms/navigation", json={"data": nav})

    def test_image_fields(self, admin):
        cms = {d["key"]: d for d in admin.get(f"{B}/cms").json()}
        prof, ident = cms["profile"]["draft"], cms["identity"]["draft"]
        try:
            for bad in ("javascript:alert(1)", "data:text/html,xx", "vbscript:x"):
                assert admin.put(f"{B}/cms/profile", json={"data": prof | {"image": bad}}).status_code == 400, bad
                assert admin.put(f"{B}/cms/identity", json={"data": ident | {"logo": bad}}).status_code == 400, bad
                assert admin.put(f"{B}/cms/identity", json={"data": ident | {"default_image": bad}}).status_code == 400, bad
            for ok in ("/api/media/file/public/x.webp", "https://example.com/a.jpg"):
                assert admin.put(f"{B}/cms/profile", json={"data": prof | {"image": ok}}).status_code == 200, ok
                assert admin.put(f"{B}/cms/identity", json={"data": ident | {"logo": ok}}).status_code == 200, ok
        finally:
            admin.put(f"{B}/cms/profile", json={"data": prof})
            admin.put(f"{B}/cms/identity", json={"data": ident})


# ---- Claims on removed line ----
class TestClaimRemoved:
    def test_claim_removed_line_404(self, kasir, admin, owner, items):
        iid = items["TEST-RELAY-01"]["id"]
        ensure_stock(owner, iid, 2)
        j = new_job(kasir, [{"type": "item", "item_id": iid, "qty": 1}, {"type": "service", "name": "TEST jasa", "unit_price": 50000}])
        rm = j["lines"][0]["lid"]
        keep = j["lines"][1]["lid"]
        assert admin.post(f"{B}/jobs/{j['id']}/lines/{rm}/remove", json={"reason": "batal pasang"}).status_code == 200
        assert kasir.post(f"{B}/jobs/{j['id']}/complete").status_code == 200
        r = kasir.post(f"{B}/claims", json={"ref_type": "job", "ref_id": j["id"], "line_lid": rm, "symptom": "mati"})
        assert r.status_code == 404
        r = kasir.post(f"{B}/claims", json={"ref_type": "job", "ref_id": j["id"], "line_lid": keep, "symptom": "kurang"})
        assert r.status_code == 200 and r.json()["kind"] == "garansi"


# ---- Positional line updates under concurrency ----
class TestConcurrentLines:
    def test_admin_edit_while_kasir_adds(self, kasir, admin):
        j = new_job(kasir, [{"type": "service", "name": "TEST A", "unit_price": 10000}])
        lid = j["lines"][0]["lid"]
        res = []

        def edit(q):
            res.append(admin.put(f"{B}/jobs/{j['id']}/lines/{lid}", json={"qty": q, "reason": "ubah qty"}).status_code)

        def add(n):
            res.append(kasir.post(f"{B}/jobs/{j['id']}/lines", json={"type": "service", "name": f"TEST B{n}", "unit_price": 1000}).status_code)

        ts = []
        for n in range(5):
            ts += [threading.Thread(target=edit, args=(n + 2,)), threading.Thread(target=add, args=(n,))]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert all(c == 200 for c in res), res
        g = kasir.get(f"{B}/jobs/{j['id']}").json()
        active = [l for l in g["lines"] if not l.get("removed")]
        assert len(active) == 6, [l["name"] for l in g["lines"]]
        a = next(l for l in active if l["lid"] == lid)
        assert a["qty"] in range(2, 7) and a["subtotal"] == a["qty"] * 10000
        assert g["subtotal"] == sum(l["subtotal"] for l in active) and g["total"] == g["subtotal"]
        # remove concurrently with add
        res.clear()
        ts = [threading.Thread(target=lambda: res.append(admin.post(f"{B}/jobs/{j['id']}/lines/{lid}/remove", json={"reason": "hapus"}).status_code)),
              threading.Thread(target=add, args=(99,))]
        [t.start() for t in ts]
        [t.join() for t in ts]
        g = kasir.get(f"{B}/jobs/{j['id']}").json()
        active = [l for l in g["lines"] if not l.get("removed")]
        assert len(active) == 6 and all(l["lid"] != lid for l in active)
        assert g["total"] == sum(l["subtotal"] for l in active) == 6000


# ---- Vehicle plate conflict ----
class TestPlate:
    def test_existing_plate_409_and_select_by_id(self, kasir):
        j = new_job(kasir)
        plate = j["vehicle"]["plate"]
        r = kasir.post(f"{B}/jobs", json={"customer": {"name": f"TEST_{uid()}", "phone": phone()},
                                          "vehicle": {"plate": plate.lower(), "brand": "Yamaha", "model": "NMAX"}})
        assert r.status_code == 409 and "Plat sudah terdaftar" in r.json()["detail"]
        r = kasir.post(f"{B}/jobs", json={"customer": {"id": j["customer_id"], "name": j["customer"]["name"], "phone": j["customer"]["phone"]},
                                          "vehicle": {"id": j["vehicle_id"], "plate": plate}})
        assert r.status_code == 200, r.text
        assert r.json()["vehicle_id"] == j["vehicle_id"] and r.json()["vehicle"]["plate"] == plate
