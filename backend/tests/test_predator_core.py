"""Predator Autolight backend regression: auth/RBAC, jobs, packages stock, discount, DP, cancel, sales, orders, returns, claims, stock, CMS, media."""
import io
import pytest
import random
import threading
from conftest import BASE_URL, CREDS, uid, stock_of, ensure_stock

B = BASE_URL + "/api"


def phone():
    return "0812" + str(random.randint(10000000, 99999999))


def new_job(s, lines=None, name=None):
    p = "TS" + uid()[:6].upper()
    r = s.post(f"{B}/jobs", json={"customer": {"name": name or f"TEST_{uid()}", "phone": phone()},
                                  "vehicle": {"plate": p, "brand": "Honda", "model": "Vario"},
                                  "complaint": "TEST lampu redup", "lines": lines or []})
    assert r.status_code == 200, r.text
    return r.json()


def pkg_line(pkg, opt=True):
    return {"type": "package", "package_id": pkg["id"], "option_ids": [pkg["options"][0]["id"]] if opt else [], "qty": 1}


# ---- Auth / RBAC ----
class TestAuth:
    def test_cookies_httponly(self):
        import requests
        r = requests.post(f"{B}/auth/login", json={"email": CREDS["kasir"][0], "password": CREDS["kasir"][1]})
        assert r.status_code == 200
        sc = r.headers.get("set-cookie", "")
        assert "access_token" in sc and "HttpOnly" in sc
        assert r.json()["role"] == "kasir"

    def test_wrong_password(self, anon):
        r = anon.post(f"{B}/auth/login", json={"email": f"nobody_{uid()}@x.local", "password": "x"})
        assert r.status_code == 401

    def test_kasir_forbidden(self, kasir, items):
        iid = items["TEST-RELAY-01"]["id"]
        assert kasir.get(f"{B}/reports/summary?start=2026-01-01&end=2026-12-31").status_code == 403
        assert kasir.post(f"{B}/items", json={"sku": "TEST-X", "name": "x", "price": 1}).status_code == 403
        assert kasir.get(f"{B}/cms").status_code == 403
        assert kasir.post(f"{B}/stock/correction", json={"item_id": iid, "delta": 1, "reason": "test"}).status_code == 403

    def test_admin_forbidden(self, admin):
        assert admin.get(f"{B}/reports/summary?start=2026-01-01&end=2026-12-31").status_code == 403
        assert admin.get(f"{B}/discounts/pending").status_code == 403
        assert admin.get(f"{B}/users").status_code == 403

    def test_kasir_no_cost(self, kasir):
        its = kasir.get(f"{B}/items").json()
        assert its and all("cost" not in i for i in its)
        pk = kasir.get(f"{B}/packages").json()
        assert pk and all("cost_total" not in p for p in pk)
        assert all("cost" not in c for p in pk for c in p["components"])


# ---- Jobs ----
class TestJobs:
    def test_multiple_masuk(self, kasir):
        ids = [new_job(kasir)["id"] for _ in range(3)]
        listed = {j["id"] for j in kasir.get(f"{B}/jobs?status=Masuk").json()}
        assert set(ids) <= listed
        for i in ids:
            j = kasir.get(f"{B}/jobs/{i}").json()
            assert j["status"] == "Masuk" and j["no"].startswith("NB-")

    def test_package_complete_once(self, owner, kasir, items, pkg):
        need = {"TEST-BILED-01": 2, "TEST-SHROUD-01": 0, "TEST-RELAY-01": 1, "TEST-SHROUD-RGB": 2}
        for sku, q in need.items():
            ensure_stock(owner, items[sku]["id"], max(q, 1) * 2)
        before = {sku: stock_of(owner, items[sku]["id"]) for sku in need}
        j = new_job(kasir, [pkg_line(pkg)])
        assert j["total"] == 1850000
        res = []
        ts = [threading.Thread(target=lambda: res.append(kasir.post(f"{B}/jobs/{j['id']}/complete").status_code)) for _ in range(3)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        r = kasir.post(f"{B}/jobs/{j['id']}/complete")
        assert r.status_code == 200 and r.json()["status"] == "Selesai"
        after = {sku: stock_of(owner, items[sku]["id"]) for sku in need}
        for sku, q in need.items():
            assert before[sku] - after[sku] == q, (sku, before[sku], after[sku], res)
        muts = owner.get(f"{B}/stock/mutations?item_id={items['TEST-BILED-01']['id']}").json()
        rows = muts if isinstance(muts, list) else muts.get("items", muts.get("rows", []))
        assert len([m for m in rows if m.get("ref_id") == j["id"]]) == 1

    def test_kasir_line_edit_forbidden_admin_ok(self, kasir, admin, owner, items):
        j = new_job(kasir)
        r = kasir.post(f"{B}/jobs/{j['id']}/lines", json={"type": "item", "item_id": items["TEST-RELAY-01"]["id"], "qty": 1})
        assert r.status_code == 200
        lid = r.json()["lines"][0]["lid"]
        assert kasir.put(f"{B}/jobs/{j['id']}/lines/{lid}", json={"qty": 2, "reason": "test"}).status_code == 403
        assert kasir.post(f"{B}/jobs/{j['id']}/lines/{lid}/remove", json={"reason": "test"}).status_code == 403
        r = admin.put(f"{B}/jobs/{j['id']}/lines/{lid}", json={"qty": 2, "reason": "salah input"})
        assert r.status_code == 200 and r.json()["total"] == 70000
        assert admin.put(f"{B}/jobs/{j['id']}/lines/{lid}", json={"qty": 3}).status_code == 422
        r = admin.post(f"{B}/jobs/{j['id']}/lines/{lid}/remove", json={"reason": "batal pasang"})
        assert r.status_code == 200 and r.json()["total"] == 0
        logs = owner.get(f"{B}/audit").json()
        logs = logs if isinstance(logs, list) else logs.get("items", [])
        assert any(l.get("ref_id") == j["id"] and l["action"] == "hapus_baris" for l in logs)

    def test_discount_flow(self, kasir, owner, items):
        ensure_stock(owner, items["TEST-RELAY-01"]["id"], 2)
        j = new_job(kasir, [{"type": "item", "item_id": items["TEST-RELAY-01"]["id"], "qty": 2}])
        r = kasir.post(f"{B}/tx/job/{j['id']}/discount", json={"amount": 10000, "reason": "langganan"})
        assert r.status_code == 200 and r.json()["discount"]["status"] == "pending" and r.json()["total"] == 70000
        assert kasir.post(f"{B}/jobs/{j['id']}/complete").status_code == 400
        assert any(d["id"] == j["id"] for d in owner.get(f"{B}/discounts/pending").json())
        assert kasir.post(f"{B}/tx/job/{j['id']}/discount/decide", json={"approve": True}).status_code == 403
        r = owner.post(f"{B}/tx/job/{j['id']}/discount/decide", json={"approve": True})
        assert r.status_code == 200 and r.json()["total"] == 60000
        assert kasir.post(f"{B}/jobs/{j['id']}/complete").status_code == 200

    def test_dp_pelunasan(self, kasir, owner, items):
        ensure_stock(owner, items["TEST-RELAY-01"]["id"], 1)
        j = new_job(kasir, [{"type": "item", "item_id": items["TEST-RELAY-01"]["id"], "qty": 1},
                            {"type": "service", "name": "TEST jasa", "unit_price": 65000}])
        assert j["total"] == 100000
        k = "idem-" + uid()
        r = kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 40000, "method": "tunai", "idem_key": k})
        assert r.status_code == 200 and r.json()["paid"] == 40000 and r.json()["payments"][0]["kind"] == "dp"
        r = kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 40000, "method": "tunai", "idem_key": k})
        assert r.json()["paid"] == 40000 and len(r.json()["payments"]) == 1
        assert kasir.post(f"{B}/jobs/{j['id']}/complete").status_code == 200
        assert kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 70000, "method": "tunai"}).status_code == 400
        r = kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 60000, "method": "transfer"})
        assert r.status_code == 200 and r.json()["paid"] == 100000 and r.json()["payments"][-1]["kind"] == "pelunasan"
        d = r.json()["date_local"]
        s = owner.get(f"{B}/reports/summary?start={d}&end={d}").json()
        tx = [t for t in s["transactions"] if t["id"] == j["id"]]
        assert len(tx) == 1 and tx[0]["total"] == 100000

    def test_owner_cancel_dp(self, kasir, admin, owner):
        j = new_job(kasir, [{"type": "service", "name": "TEST jasa", "unit_price": 200000}])
        kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 100000, "method": "tunai"})
        body = {"reason": "pelanggan batal", "refund_amount": 60000}
        assert kasir.post(f"{B}/jobs/{j['id']}/cancel", json=body).status_code == 403
        assert admin.post(f"{B}/jobs/{j['id']}/cancel", json=body).status_code == 403
        assert owner.post(f"{B}/jobs/{j['id']}/cancel", json={"reason": "x", "refund_amount": 200000}).status_code in (400, 422)
        r = owner.post(f"{B}/jobs/{j['id']}/cancel", json=body)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "Batal" and d["cancel"]["kept"] == 40000 and d["refunded"] == 60000
        assert any(p["direction"] == "out" and p["amount"] == 60000 for p in d["payments"])

    def test_discount_after_full_payment(self, kasir, owner):
        """Edge: approving discount after DP covering full total -> paid > total (overpayment)."""
        j = new_job(kasir, [{"type": "service", "name": "TEST jasa", "unit_price": 100000}])
        kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 100000, "method": "tunai"})
        r = owner.post(f"{B}/tx/job/{j['id']}/discount", json={"amount": 20000, "reason": "test diskon"})
        if r.status_code == 200:
            assert r.json()["total"] >= r.json()["paid"], f"overpaid: total {r.json()['total']} paid {r.json()['paid']}"


# ---- Sales ----
class TestSales:
    def test_sale_idempotent(self, kasir, owner, items):
        iid = items["TEST-LEDALIS-01"]["id"]
        ensure_stock(owner, iid, 2)
        before = stock_of(owner, iid)
        k = "sale-" + uid()
        body = {"customer_name": "TEST_beli", "lines": [{"item_id": iid, "qty": 1}], "method": "tunai", "cash_received": 200000, "idem_key": k}
        r1 = kasir.post(f"{B}/sales", json=body)
        r2 = kasir.post(f"{B}/sales", json=body)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"] and r1.json()["no"].startswith("PJ-") and r1.json()["change"] == 50000
        assert stock_of(owner, iid) == before - 1
        d = r1.json()["date_local"]
        daily = kasir.get(f"{B}/reports/daily?date={d}").json()
        assert any(s["id"] == r1.json()["id"] for s in daily["sales"]) and daily["types"]["sale"]["count"] >= 1

    def test_sale_insufficient(self, kasir, owner, items):
        iid = items["TEST-LEDALIS-01"]["id"]
        r = kasir.post(f"{B}/sales", json={"lines": [{"item_id": iid, "qty": stock_of(owner, iid) + 1}], "method": "tunai", "idem_key": "s-" + uid()})
        assert r.status_code == 409

    def test_shared_stock_and_sale_return(self, kasir, owner, admin, items):
        iid = items["TEST-RELAY-01"]["id"]
        ensure_stock(owner, iid, 6)
        s0 = stock_of(owner, iid)
        j = new_job(kasir, [{"type": "item", "item_id": iid, "qty": 1}])
        kasir.post(f"{B}/jobs/{j['id']}/complete")
        s1 = stock_of(owner, iid)
        sale = kasir.post(f"{B}/sales", json={"lines": [{"item_id": iid, "qty": 3}], "method": "transfer", "idem_key": "s-" + uid()}).json()
        s2 = stock_of(owner, iid)
        o = kasir.post(f"{B}/orders", json={"customer_name": "TEST_wa", "customer_phone": phone(), "address": "Jl Test", "province": "Jawa Timur",
                                            "payment_type": "prabayar", "lines": [{"type": "item", "item_id": iid, "qty": 1}]}).json()
        kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": o["total"], "method": "transfer"})
        s3 = stock_of(owner, iid)
        assert (s0 - s1, s1 - s2, s2 - s3) == (1, 3, 1)
        assert kasir.post(f"{B}/tx/sale/{sale['id']}/return", json={"items": [{"item_id": iid, "qty": 1, "condition": "layak"}], "reason": "test"}).status_code == 403
        r = admin.post(f"{B}/tx/sale/{sale['id']}/return", json={"items": [{"item_id": iid, "qty": 1, "condition": "layak"},
                                                                           {"item_id": iid, "qty": 1, "condition": "rusak"}],
                                                                 "refund_amount": 70000, "refund_method": "transfer", "reason": "TEST retur"})
        assert r.status_code == 200, r.text
        assert stock_of(owner, iid) == s3 + 1
        g = admin.get(f"{B}/sales/{sale['id']}").json()
        assert g["no"] == sale["no"] and len(g["lines"]) == 1 and len(g["returns"]) == 1 and g["refunded"] == 70000
        assert admin.post(f"{B}/tx/sale/{sale['id']}/return", json={"items": [{"item_id": iid, "qty": 2, "condition": "layak"}], "reason": "lebih"}).status_code == 400
        dmg = owner.get(f"{B}/damaged").json()
        dmg = dmg if isinstance(dmg, list) else dmg.get("items", [])
        assert any(d.get("ref_id") == sale["id"] for d in dmg)


# ---- Orders ----
class TestOrders:
    def test_prepaid_bali(self, kasir, owner, items):
        iid = items["TEST-LEDALIS-01"]["id"]
        ensure_stock(owner, iid, 1)
        base = {"customer_name": "TEST_bali", "customer_phone": phone(), "address": "Denpasar", "province": "Bali",
                "shipping_cost": 30000, "lines": [{"type": "item", "item_id": iid, "qty": 1}]}
        assert kasir.post(f"{B}/orders", json=base | {"payment_type": "cod"}).status_code == 400
        o = kasir.post(f"{B}/orders", json=base | {"payment_type": "prabayar"}).json()
        assert o["no"].startswith("WA-") and o["total"] == 180000
        s0 = stock_of(owner, iid)
        assert kasir.post(f"{B}/orders/{o['id']}/ship", json={"resi": "X"}).status_code == 400
        kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 100000, "method": "transfer"})
        assert stock_of(owner, iid) == s0
        assert kasir.post(f"{B}/orders/{o['id']}/ship", json={}).status_code == 400
        assert kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 80000, "method": "transfer"}).status_code == 400
        kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 50000, "method": "transfer"})
        assert stock_of(owner, iid) == s0 - 1
        assert kasir.post(f"{B}/orders/{o['id']}/ship", json={}).status_code == 400  # ongkir di muka belum dibayar
        kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 30000, "method": "transfer", "purpose": "ongkir"})
        r = kasir.post(f"{B}/orders/{o['id']}/ship", json={"resi": "JT123"})
        assert r.status_code == 200 and r.json()["ship_status"] == "Dikirim"

    @pytest.mark.skip(reason="COD harga barang dihapus (revisi COD ongkir)")
    def test_cod_jatim_and_return(self, kasir, owner, admin, items, pkg):
        for sku in ("TEST-BILED-01", "TEST-SHROUD-01", "TEST-RELAY-01"):
            ensure_stock(owner, items[sku]["id"], 2)
        bi = items["TEST-BILED-01"]["id"]
        o = kasir.post(f"{B}/orders", json={"customer_name": "TEST_cod", "customer_phone": phone(), "address": "Surabaya",
                                            "province": "Jawa Timur", "payment_type": "cod", "shipping_cost": 20000,
                                            "lines": [pkg_line(pkg, False)]}).json()
        assert o["total"] == 1520000
        assert kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 1520000, "method": "cod"}).status_code == 400
        s0 = stock_of(owner, bi)
        r = kasir.post(f"{B}/orders/{o['id']}/ship", json={"resi": "COD1"})
        assert r.status_code == 200 and stock_of(owner, bi) == s0 - 2
        assert any(x["id"] == o["id"] for x in kasir.get(f"{B}/orders?cod_pending=true").json())
        d = r.json()["date_local"]
        s = owner.get(f"{B}/reports/summary?start={d}&end={d}").json()
        assert any(c["id"] == o["id"] for c in s["cod_pending"])
        recv_before = s["received"]["cod"]
        # return package for COD order
        r = admin.post(f"{B}/tx/order/{o['id']}/return", json={"items": [{"item_id": bi, "qty": 2, "condition": "layak"}], "reason": "TEST paket kembali"})
        assert r.status_code == 200 and r.json()["ship_status"] == "Kembali"
        assert stock_of(owner, bi) == s0
        s2 = owner.get(f"{B}/reports/summary?start={d}&end={d}").json()
        assert s2["received"]["cod"] == recv_before
        assert not any(x["id"] == o["id"] for x in kasir.get(f"{B}/orders?cod_pending=true").json())

    @pytest.mark.skip(reason="COD harga barang dihapus (revisi COD ongkir)")
    def test_cod_settle(self, kasir, owner, items):
        iid = items["TEST-RELAY-01"]["id"]
        ensure_stock(owner, iid, 1)
        o = kasir.post(f"{B}/orders", json={"customer_name": "TEST_cod2", "customer_phone": phone(), "address": "Semarang",
                                            "province": "Jawa Tengah", "payment_type": "cod", "lines": [{"type": "item", "item_id": iid, "qty": 1}]}).json()
        kasir.post(f"{B}/orders/{o['id']}/ship", json={})
        d = kasir.get(f"{B}/orders/{o['id']}").json()["date_local"]
        before = owner.get(f"{B}/reports/summary?start={d}&end={d}").json()["received"]["cod"]
        assert kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 35000, "method": "tunai"}).status_code == 400
        r = kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 35000, "method": "cod"})
        assert r.status_code == 200 and r.json()["cod_settled"] is True
        assert owner.get(f"{B}/reports/summary?start={d}&end={d}").json()["received"]["cod"] == before + 35000


# ---- Warranty claims ----
class TestClaims:
    def test_claim_flow(self, kasir, owner, items):
        bi = items["TEST-BILED-01"]["id"]
        ensure_stock(owner, bi, 2)
        j = new_job(kasir, [{"type": "item", "item_id": bi, "qty": 1}])
        kasir.post(f"{B}/jobs/{j['id']}/complete")
        lid = j["lines"][0]["lid"]
        r = kasir.post(f"{B}/claims", json={"ref_type": "job", "ref_id": j["id"], "line_lid": lid, "symptom": "mati sebelah"})
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["no"].startswith("NG-") and c["kind"] == "garansi" and c["claim"]["claim_seq"] == 1 and c["claim"]["in_warranty"] is True
        r = kasir.post(f"{B}/jobs/{c['id']}/lines", json={"type": "item", "item_id": bi, "qty": 1, "warranty_replacement": True})
        assert r.status_code == 200 and r.json()["lines"][0]["unit_price"] == 0
        s0 = stock_of(owner, bi)
        assert kasir.post(f"{B}/jobs/{c['id']}/complete").status_code == 200
        assert stock_of(owner, bi) == s0 - 1
        c2 = kasir.post(f"{B}/claims", json={"ref_type": "job", "ref_id": j["id"], "line_lid": lid, "symptom": "kedip"}).json()
        assert c2["claim"]["claim_seq"] == 2
        s1 = stock_of(owner, bi)
        assert kasir.post(f"{B}/jobs/{c2['id']}/complete").status_code == 200
        assert stock_of(owner, bi) == s1
        orig = kasir.get(f"{B}/jobs/{j['id']}").json()
        assert {c["id"], c2["id"]} <= {x["id"] for x in orig["claims"]}
        h = kasir.get(f"{B}/vehicles/{j['vehicle_id']}/history").json()
        assert {c["id"], c2["id"], j["id"]} <= {x["id"] for x in h["jobs"]}
        assert kasir.post(f"{B}/jobs/{j['id']}/lines", json={"type": "item", "item_id": bi, "qty": 1, "warranty_replacement": True}).status_code == 400


# ---- Stock ----
class TestStock:
    def test_correction_opname(self, owner, admin, items):
        iid = items["TEST-SHROUD-01"]["id"]
        s0 = stock_of(owner, iid)
        assert admin.post(f"{B}/stock/correction", json={"item_id": iid, "delta": 1}).status_code == 422
        r = admin.post(f"{B}/stock/correction", json={"item_id": iid, "delta": 2, "reason": "TEST salah hitung"})
        assert r.status_code == 200 and r.json()["stock"] == s0 + 2
        assert admin.post(f"{B}/stock/correction", json={"item_id": iid, "delta": -(s0 + 100), "reason": "TEST minus"}).status_code == 409
        assert admin.post(f"{B}/stock/opname", json={"item_id": iid, "counted": -1}).status_code == 422
        r = admin.post(f"{B}/stock/opname", json={"item_id": iid, "counted": s0, "note": "TEST opname"})
        assert r.status_code == 200 and stock_of(owner, iid) == s0
        m = owner.get(f"{B}/stock/mutations?item_id={iid}").json()
        rows = m if isinstance(m, list) else m.get("items", [])
        kinds = [x["kind"] for x in rows[:5]]
        assert "koreksi" in kinds and "opname" in kinds


# ---- CMS / Media ----
class TestCMS:
    def test_draft_preview_publish(self, admin, anon):
        cms = {d["key"]: d for d in admin.get(f"{B}/cms").json()}
        home = cms["home"]["draft"]
        orig_pub_title = anon.get(f"{B}/public/site").json()["home"]["sections"][0]["title"]
        t = f"TEST Hero {uid()}"
        sec = [dict(s) for s in home["sections"]]
        hero = next(s for s in sec if s["type"] == "hero")
        hero["title"] = t
        assert admin.put(f"{B}/cms/home", json={"data": {"sections": sec}}).status_code == 200
        pub = anon.get(f"{B}/public/site").json()
        assert next(s for s in pub["home"]["sections"] if s["type"] == "hero")["title"] != t
        pv = admin.get(f"{B}/public/site?preview=true").json()
        assert next(s for s in pv["home"]["sections"] if s["type"] == "hero")["title"] == t
        assert anon.get(f"{B}/public/site?preview=true").status_code in (401, 403)
        assert admin.post(f"{B}/cms/home/publish").status_code == 200
        assert next(s for s in anon.get(f"{B}/public/site").json()["home"]["sections"] if s["type"] == "hero")["title"] == t
        revs = admin.get(f"{B}/cms/home/revisions").json()
        assert len(revs) >= 2
        prev = next(r for r in revs if r["kind"] == "publish")
        assert prev.get("previous") is not None
        hero["title"] = orig_pub_title
        admin.put(f"{B}/cms/home", json={"data": {"sections": sec}})
        admin.post(f"{B}/cms/home/publish")

    def test_reject_js_link(self, admin):
        cms = {d["key"]: d for d in admin.get(f"{B}/cms").json()}
        nav = dict(cms["navigation"]["draft"])
        items = [dict(i) for i in nav["items"]]
        items[0]["href"] = "javascript:alert(1)"
        assert admin.put(f"{B}/cms/navigation", json={"data": nav | {"items": items}}).status_code == 400

    def test_reject_js_cta_href(self, admin):
        cms = {d["key"]: d for d in admin.get(f"{B}/cms").json()}
        nav = dict(cms["navigation"]["draft"])
        r = admin.put(f"{B}/cms/navigation", json={"data": nav | {"cta_href": "javascript:alert(1)"}})
        if r.status_code == 200:
            admin.put(f"{B}/cms/navigation", json={"data": cms["navigation"]["draft"]})
        assert r.status_code == 400, "navigation.cta_href accepts javascript: (not in URL_KEYS)"

    def test_media_upload(self, admin):
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (20, 20), (255, 0, 0)).save(buf, "PNG")
        r = admin.post(f"{B}/media", files={"file": ("t.png", buf.getvalue(), "image/png")}, data={"alt": "TEST"})
        assert r.status_code == 200 and r.json()["url"].startswith("/api/media/file/")
        m = r.json()
        assert admin.get(BASE_URL + m["url"]).status_code == 200
        bad = admin.post(f"{B}/media", files={"file": ("t.txt", b"hello", "text/plain")})
        assert bad.status_code == 400
        assert admin.delete(f"{B}/media/{m['id']}").status_code == 200

    def test_gallery_filter(self, admin, anon):
        cms = {d["key"]: d for d in admin.get(f"{B}/cms").json()}
        g = cms["gallery"]["draft"]
        tag = uid()
        items = list(g.get("items", [])) + [
            {"title": f"TEST_ok_{tag}", "image": "", "visible": True, "consent": True, "plate_masked": True},
            {"title": f"TEST_nomask_{tag}", "image": "", "visible": True, "consent": True, "plate_masked": False}]
        admin.put(f"{B}/cms/gallery", json={"data": g | {"items": items}})
        pv = admin.get(f"{B}/public/site?preview=true").json()
        titles = [i.get("title") for i in pv["gallery"]["items"]]
        admin.put(f"{B}/cms/gallery", json={"data": g})
        assert f"TEST_ok_{tag}" in titles and f"TEST_nomask_{tag}" not in titles
