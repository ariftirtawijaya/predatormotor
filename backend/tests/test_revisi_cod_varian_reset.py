"""Revisi: COD ongkir, master pelanggan pesanan WA, produk+varian & impor Excel, reset data uji (semua di DB tes terisolasi)."""
import io
import random
import requests
from openpyxl import Workbook, load_workbook
from pymongo import MongoClient
from conftest import BASE_URL, CREDS, MONGO_URL, TEST_DB, uid, stock_of, spawn_server, _free_port

B = f"{BASE_URL}/api"


def phone():
    return "0857" + str(random.randint(10000000, 99999999))


def product(owner, variants, name=None):
    r = owner.post(f"{B}/products", json={"name": name or f"TEST Devil Eye {uid()}", "category": "Devil Eye", "brand": "Predator",
                                         "variants": variants})
    assert r.status_code == 200, r.text
    p = next(x for x in owner.get(f"{B}/products?q={r.json()['code']}").json() if x["id"] == r.json()["id"])
    return {v["variant"]: v for v in p["variants"]}


def xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["kode_produk", "nama_produk", "kategori", "merek", "nama_varian", "sku", "harga_jual", "modal", "garansi_hari",
               "stok_minimum", "status", "stok_awal"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def imp(s, content, commit=False):
    return s.post(f"{B}/items/import?commit={str(commit).lower()}", files={"file": ("m.xlsx", content, "application/octet-stream")})


class TestCodOngkir:
    def test_contoh_wajib_jatim(self, owner, kasir):
        v = product(owner, [{"sku": f"TDE-R-{uid()}", "variant": "Merah", "price": 900000, "cost": 500000},
                            {"sku": f"TDE-B-{uid()}", "variant": "Biru", "price": 900000, "cost": 500000}])
        red, blue = v["Merah"]["id"], v["Biru"]["id"]
        owner.post(f"{B}/stock/in", json={"item_id": red, "qty": 3})
        owner.post(f"{B}/stock/in", json={"item_id": blue, "qty": 3})
        c = kasir.post(f"{B}/customers", json={"name": "TEST Budi COD", "phone": phone()}).json()
        assert kasir.post(f"{B}/customers", json={"name": "Lain", "phone": c["phone"]}).status_code == 409
        body = {"customer_id": c["id"], "address": "Jl. Mawar 1, Surabaya", "province": "Jawa Timur", "shipping_cost": 30000,
                "shipping_payer": "cod_kurir", "courier": "SiCepat", "lines": [{"type": "item", "item_id": red, "qty": 1}]}
        o = kasir.post(f"{B}/orders", json=body).json()
        assert o["total"] == 900000 and o["goods_total"] == 900000 and o["shipping_cost"] == 30000 and o["courier"] == "J&T"
        assert o["customer"] == {"id": c["id"], "name": c["name"], "phone": c["phone"]}
        assert kasir.post(f"{B}/orders/{o['id']}/ship", json={}).status_code == 400
        assert kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 30000, "method": "transfer", "purpose": "ongkir"}).status_code == 400
        assert kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 930000, "method": "transfer"}).status_code == 400
        s_red, s_blue = stock_of(owner, red), stock_of(owner, blue)
        p = kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 900000, "method": "transfer", "idem_key": uid()}).json()
        assert p["goods_paid"] == 900000 and p["paid"] == 900000 and p["stock_applied"]
        assert stock_of(owner, red) == s_red - 1 and stock_of(owner, blue) == s_blue
        r = kasir.post(f"{B}/orders/{o['id']}/ship", json={"resi": "JT1"})
        assert r.status_code == 200 and r.json()["ship_status"] == "Dikirim"
        assert stock_of(owner, red) == s_red - 1
        nota = requests.get(f"{B}/public/nota/{o['public_token']}").json()
        assert nota["shipping_payer"] == "cod_kurir" and nota["remaining"] == 0 and nota["total"] == 900000
        msg = kasir.get(f"{B}/wa/nota/order/{o['id']}").json()["message"]
        assert "COD ongkir" in msg and "kurir J&T" in msg and "Total tagihan bengkel: Rp900.000" in msg and "LUNAS" in msg
        assert "bayar di tempat" not in msg
        d = o["date_local"]
        rep = owner.get(f"{B}/reports/summary?start={d}&end={d}").json()
        t = next(x for x in rep["transactions"] if x["id"] == o["id"])
        assert t["total"] == 900000
        assert rep["shipping_cod_courier"] >= 30000 and not any(x["id"] == o["id"] for x in rep["cod_pending"])
        pays = [x for x in owner.get(f"{B}/orders/{o['id']}").json()["payments"]]
        assert sum(x["amount"] for x in pays) == 900000 and all(x["method"] != "cod" for x in pays)
        # Retur: refund hanya dari uang yang diterima bengkel (900rb), ongkir COD tidak dapat direfund
        bad = owner.post(f"{B}/tx/order/{o['id']}/return", json={"items": [{"item_id": red, "qty": 1, "condition": "layak"}],
                                                                 "refund_amount": 930000, "reason": "paket kembali"})
        assert bad.status_code == 400
        ok = owner.post(f"{B}/tx/order/{o['id']}/return", json={"items": [{"item_id": red, "qty": 1, "condition": "layak"}],
                                                                "refund_amount": 900000, "reason": "paket kembali"})
        assert ok.status_code == 200 and ok.json()["refunded"] == 900000 and stock_of(owner, red) == s_red
        assert all(r.get("write_off", 0) == 0 for r in ok.json()["returns"])

    def test_ongkir_di_muka_dicatat_terpisah_dan_luar_jawa(self, kasir, owner):
        v = product(owner, [{"sku": f"TOK-{uid()}", "price": 200000}])[""]
        owner.post(f"{B}/stock/in", json={"item_id": v["id"], "qty": 2})
        base = {"customer_name": "TEST Medan", "customer_phone": phone(), "address": "Medan", "province": "Sumatera Utara",
                "shipping_cost": 45000, "lines": [{"type": "item", "item_id": v["id"], "qty": 1}]}
        assert kasir.post(f"{B}/orders", json=base | {"shipping_payer": "cod_kurir"}).status_code == 400
        assert kasir.post(f"{B}/orders", json=base | {"payment_type": "cod"}).status_code == 400
        o = kasir.post(f"{B}/orders", json=base).json()
        assert o["total"] == 245000 and o["shipping_payer"] == "bengkel"
        kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 200000, "method": "transfer"})
        assert kasir.post(f"{B}/orders/{o['id']}/ship", json={}).status_code == 400
        p = kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 45000, "method": "tunai", "purpose": "ongkir"}).json()
        assert p["ship_paid"] == 45000 and p["goods_paid"] == 200000
        assert kasir.post(f"{B}/orders/{o['id']}/ship", json={}).status_code == 200
        pick = kasir.post(f"{B}/orders", json=base | {"delivery": "ambil", "shipping_payer": "cod_kurir"}).json()
        assert pick["shipping_cost"] == 0 and pick["shipping_payer"] == "none" and pick["total"] == 200000

    def test_pelanggan_lama_snapshot_dan_riwayat(self, kasir, owner):
        v = product(owner, [{"sku": f"TPL-{uid()}", "price": 100000}])[""]
        ph = phone()
        o1 = kasir.post(f"{B}/orders", json={"customer_name": "TEST Sari", "customer_phone": ph, "address": "Jl. Lama", "province": "Jawa Tengah",
                                              "lines": [{"type": "item", "item_id": v["id"], "qty": 1}]}).json()
        cid = o1["customer"]["id"]
        o2 = kasir.post(f"{B}/orders", json={"customer_name": "Nama Lain", "customer_phone": "+62" + ph[1:], "delivery": "ambil",
                                              "lines": [{"type": "item", "item_id": v["id"], "qty": 1}]}).json()
        assert o2["customer"]["id"] == cid and o2["customer"]["name"] == "TEST Sari"
        c = next(x for x in kasir.get(f"{B}/customers?q={ph}").json() if x["id"] == cid)
        assert c["address"] == "Jl. Lama" and c["province"] == "Jawa Tengah"
        kasir.put(f"{B}/customers/{cid}", json={"name": "TEST Sari Baru", "phone": ph})
        assert kasir.get(f"{B}/orders/{o1['id']}").json()["customer"]["name"] == "TEST Sari"
        h = kasir.get(f"{B}/customers/{cid}/history").json()
        assert {o1["id"], o2["id"]} <= {x["id"] for x in h["orders"]} and h["vehicles"] == []


class TestVarian:
    def test_seed_lama_termigrasi(self, owner, items):
        it = items["TEST-BILED-01"]
        assert it["product_id"] and it["migrated_from_flat"] and it["name"].startswith(it["product_name"])

    def test_varian_di_paket_dan_kasir(self, owner, kasir):
        v = product(owner, [{"sku": f"TBL1-{uid()}", "variant": "1 warna", "price": 950000}, {"sku": f"TBL2-{uid()}", "variant": "2 warna", "price": 1150000}])
        one, two = v["1 warna"]["id"], v["2 warna"]["id"]
        owner.post(f"{B}/stock/in", json={"item_id": two, "qty": 4})
        pk = owner.post(f"{B}/packages", json={"name": f"TEST Paket BiLED 2W {uid()}", "price": 1500000, "components": [{"item_id": two, "qty": 2}]}).json()
        s1, s2 = stock_of(owner, one), stock_of(owner, two)
        r = kasir.post(f"{B}/sales", json={"lines": [{"item_id": two, "qty": 1}], "method": "tunai", "cash_received": 1150000, "idem_key": uid()})
        assert r.status_code == 200, r.text
        assert stock_of(owner, two) == s2 - 1 and stock_of(owner, one) == s1
        o = kasir.post(f"{B}/orders", json={"customer_name": "TEST Paket", "customer_phone": phone(), "delivery": "ambil",
                                             "lines": [{"type": "package", "package_id": pk["id"], "option_ids": []}]}).json()
        kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": o["goods_total"], "method": "transfer"})
        assert stock_of(owner, two) == s2 - 3 and stock_of(owner, one) == s1
        muts = owner.get(f"{B}/stock/mutations?item_id={two}").json()
        assert muts[0]["item_name"].endswith("2 warna")

    def test_template_dan_impor_ulang(self, owner, admin, kasir):
        t = owner.get(f"{B}/items/import/template")
        wb = load_workbook(io.BytesIO(t.content))
        assert wb.sheetnames == ["Data", "Panduan"] and sum(1 for r in wb["Data"].iter_rows(values_only=True) if r[0] == "DE360") == 6
        assert kasir.get(f"{B}/items/import/template").status_code == 403
        k = uid().upper()
        rows = [[f"P{k}", f"TEST Impor {k}", "Devil Eye", "X", "Merah", f"I{k}-R", 175000, 100000, 90, 2, "aktif", 5],
                [f"P{k}", f"TEST Impor {k}", "Devil Eye", "X", "Biru", f"I{k}-B", 175000, 100000, 90, 2, "aktif", 5],
                [f"S{k}", f"TEST Relay {k}", "Kelistrikan", "", "", f"I{k}-S", 85000, 40000, 0, 0, "", 3]]
        f = xlsx(rows)
        assert imp(kasir, f).status_code == 403
        pv = imp(admin, f).json()
        assert pv["summary"]["variants_new"] == 3 and pv["summary"]["products_new"] == 2 and not pv["errors"]
        assert "cost" not in pv["rows"][0]
        assert not owner.get(f"{B}/items?q=I{k}").json()
        c = imp(admin, f, True).json()
        assert c["committed"]
        its = {i["sku"]: i for i in owner.get(f"{B}/items?q=I{k}").json()}
        assert its[f"I{k}-R"]["stock"] == 5 and its[f"I{k}-S"]["stock"] == 3 and its[f"I{k}-R"]["name"] == f"TEST Impor {k} – Merah"
        again = imp(admin, f, True).json()
        assert again["summary"]["variants_same"] == 3 and again["summary"]["variants_new"] == 0
        rows[0][6], rows[0][11] = 199000, 50
        upd = imp(admin, xlsx(rows), True).json()
        assert upd["summary"]["variants_update"] == 1 and "diabaikan" in upd["rows"][0]["stock_note"]
        its = {i["sku"]: i for i in owner.get(f"{B}/items?q=I{k}").json()}
        assert its[f"I{k}-R"]["stock"] == 5 and its[f"I{k}-R"]["price"] == 199000
        prods = [p for p in owner.get(f"{B}/products?q=P{k}").json() if p["code"] == f"P{k}"]
        assert len(prods) == 1 and len(prods[0]["variants"]) == 2

    def test_impor_validasi_baris(self, admin):
        k = uid().upper()
        bad = xlsx([[f"Q{k}", "TEST Q", "", "", "A", f"Q{k}-1", 1000, 0, 0, 0, "aktif", 0],
                    [f"Q{k}", "TEST Q", "", "", "B", f"Q{k}-1", 1000, 0, 0, 0, "aktif", 0],
                    [f"Q{k}", "TEST Q", "", "", "C", f"Q{k}-3", "", 0, 0, 0, "aktif", 0],
                    [f"Q{k}", "TEST Q", "", "", "D", "TEST-BILED-01", 1000, 0, 0, 0, "aktif", 0],
                    [f"Z{k}", "TEST Q", "", "", "", f"Q{k}-5", 1000, 0, 0, 0, "aktif", 0]])
        r = imp(admin, bad).json()
        rows = {e["row"] for e in r["errors"]}
        assert {3, 4, 5} <= rows
        assert imp(admin, bad, True).status_code == 400
        assert imp(admin, b"bukan excel").status_code == 400


def test_reset_seluruh_data_server_terpisah():
    port, db_name = _free_port(), f"{TEST_DB}_reset"
    mc = MongoClient(MONGO_URL)
    rdb = mc[db_name]
    # Data lama sebelum server start: barang tanpa produk induk & pesanan COD barang model lama
    rdb.items.insert_one({"id": "legacy-1", "sku": "OLD-1", "name": "Lampu Lama", "variant": "Kuning", "category": "", "brand": "",
                          "cost": 1, "price": 2, "stock": 4, "active": True, "created_at": "2025-01-01T00:00:00+00:00"})
    rdb.orders.insert_one({"id": "legacy-o", "no": "WA-OLD", "payment_type": "cod", "ship_status": "Dikirim", "total": 10, "paid": 0,
                           "customer": {"name": "x", "phone": "62"}, "lines": [], "created_at": "2025-01-01T00:00:00+00:00"})
    proc = spawn_server(db_name, port)
    base = f"http://127.0.0.1:{port}/api"
    try:
        assert rdb.items.find_one({"id": "legacy-1"})["name"] == "Lampu Lama – Kuning"
        assert rdb.orders.find_one({"id": "legacy-o"})["legacy_cod"] is True and "cod_model" not in rdb.orders.find_one({"id": "legacy-o"})
        def login(role):
            s = requests.Session()
            r = s.post(f"{base}/auth/login", json={"email": CREDS[role][0], "password": CREDS[role][1]})
            assert r.status_code == 200, r.text
            return s
        own, adm = login("owner"), login("admin")
        assert adm.get(f"{base}/admin/reset/summary").status_code == 403
        assert adm.post(f"{base}/admin/reset", json={"password": CREDS["admin"][1], "confirm_text": "RESET SEMUA DATA", "backup_done": True}).status_code == 403
        own.put(f"{base}/settings/whatsapp/token", json={"token": "TOKEN-RESET-123456"})
        own.put(f"{base}/settings/whatsapp/number", json={"number": "081234567890"})
        own.post(f"{base}/customers", json={"name": "TEST R", "phone": phone()})
        s = own.get(f"{base}/admin/reset/summary").json()
        assert s["counts"]["users"] == 2 and s["counts"]["items"] >= 5 and s["counts"]["fonnte_token"] == 1
        ok = {"password": CREDS["owner"][1], "confirm_text": "RESET SEMUA DATA", "backup_done": True}
        assert own.post(f"{base}/admin/reset", json=ok | {"password": "salah"}).status_code == 403
        assert own.post(f"{base}/admin/reset", json=ok | {"confirm_text": "reset"}).status_code == 400
        assert own.post(f"{base}/admin/reset", json=ok | {"backup_done": False}).status_code == 400
        r = own.post(f"{base}/admin/reset", json=ok).json()
        assert r["verification"]["ok"], r["verification"]
        assert rdb.users.count_documents({}) == 1
        assert requests.post(f"{base}/auth/login", json={"email": CREDS["admin"][0], "password": CREDS["admin"][1]}).status_code == 401
        assert adm.get(f"{base}/items").status_code == 401
        own2 = login("owner")
        assert own2.get(f"{base}/items").json() == [] and own2.get(f"{base}/products").json() == []
        assert own2.get(f"{base}/settings/whatsapp").json()["token"]["configured"] is False
        rep = own2.get(f"{base}/reports/summary?start=2000-01-01&end=2100-01-01").json()
        assert rep["omzet_total"] == 0 and rep["received_total"] == 0 and rep["inventory_value"] == 0 and not rep["low_stock"]
        site = requests.get(f"{base}/public/site").text
        assert "[TEST]" not in site and "[CONTOH]" not in site
        assert own2.get(f"{base}/cms").status_code == 200
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        mc.drop_database(db_name)
        mc.close()
