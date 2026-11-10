"""Iterasi 8: impor Excel atomik (transaksi), hapus data khusus owner, produk sederhana/varian, opsi paket tambah/ganti."""
import io
import random
import threading
import requests
from openpyxl import Workbook
from pymongo import MongoClient
from conftest import BASE_URL, CREDS, MONGO_URL, TEST_DB, uid, stock_of, spawn_server, _free_port

B = f"{BASE_URL}/api"
HEAD = ["kode_produk", "nama_produk", "kategori", "merek", "nama_varian", "sku", "harga_jual", "modal", "garansi_hari",
        "stok_minimum", "status", "stok_awal"]


def xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(HEAD)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def files(c):
    return {"file": ("m.xlsx", c, "application/octet-stream")}


def preview(s, c, base=B):
    return s.post(f"{base}/items/import?commit=false", files=files(c))


def commit(s, c, h, base=B):
    return s.post(f"{base}/items/import?commit=true&plan_hash={h}", files=files(c))


def phone():
    return "0813" + str(random.randint(10000000, 99999999))


def mdb():
    return MongoClient(MONGO_URL)[TEST_DB]


def counts(d=None):
    d = d if d is not None else mdb()
    return {k: d[k].count_documents({}) for k in ("products", "items", "stock_mutations", "audit_logs")}


def simple(owner, stock=0, price=100000, **kw):
    k = uid().upper()
    r = owner.post(f"{B}/products", json={"code": f"SP{k}", "name": f"TEST Simple {k}", "price": price, "cost": 50000,
                                         "initial_stock": stock, **kw})
    assert r.status_code == 200, r.text
    p = next(x for x in owner.get(f"{B}/products?q=SP{k}").json() if x["id"] == r.json()["id"])
    return p, p["variants"][0]


def new_job(s, lines):
    r = s.post(f"{B}/jobs", json={"customer": {"name": f"TEST_{uid()}", "phone": phone()},
                                  "vehicle": {"plate": "TS" + uid()[:6].upper(), "brand": "Honda", "model": "Vario"}, "lines": lines})
    return r


# ---------- 1. Impor Excel ----------
class TestImportValidation:
    def test_nama_sama_kode_beda_ditolak_sejak_pratinjau(self, owner):
        k = uid().upper()
        c = xlsx([[f"A{k}", f"TEST Lampu {k}", "", "", "", f"A{k}-1", 1000, 0, 0, 0, "aktif", 3],
                  [f"B{k}", f"  test   LAMPU {k.lower()} ", "", "", "", f"B{k}-1", 1000, 0, 0, 0, "aktif", 3]])
        before = counts()
        r = preview(owner, c).json()
        assert [e["row"] for e in r["errors"]] == [3] and "sudah dipakai kode" in r["errors"][0]["message"]
        assert commit(owner, c, r["plan_hash"]).status_code == 400
        assert counts()["items"] == before["items"] and counts()["products"] == before["products"]

    def test_konflik_antarbaris_dan_database(self, owner):
        k = uid().upper()
        p, it = simple(owner)
        c = xlsx([[f"C{k}", "TEST C", "Kat", "", "Merah", f"C{k}-1", 1000, 0, 0, 0, "aktif", 0],
                  [f"C{k}", "TEST C", "Kat Lain", "", "Biru", f"C{k}-2", 1000, 0, 0, 0, "aktif", 0],
                  [f"C{k}", "TEST C", "Kat", "", " merah ", f"C{k}-3", 1000, 0, 0, 0, "aktif", 0],
                  [f"D{k}", p["name"].upper(), "", "", "", f"D{k}-1", 1000, 0, 0, 0, "aktif", 0],
                  [f"E{k}", "TEST E", "", "", "", it["sku"].lower(), 1000, 0, 0, 0, "aktif", 0],
                  [f"F{k}", "TEST F", "", "", "", f"F{k}-1", 1000, 0, 0, 0, "aktif", 0],
                  [f"F{k}", "TEST F", "", "", "Biru", f"F{k}-2", 1000, 0, 0, 0, "aktif", 0]])
        r = preview(owner, c).json()
        msgs = {e["row"]: e["message"] for e in r["errors"]}
        assert set(msgs) == {3, 4, 5, 6, 8}, msgs
        assert "berbeda dengan baris 2" in msgs[3] and "ganda" in msgs[4] and p["code"] in msgs[5]
        assert "dipakai produk lain" in msgs[6] and "nama_varian" in msgs[8]

    def test_produk_sederhana_sku_otomatis_dan_impor_ulang(self, owner, replset):
        k = uid().upper()
        c = xlsx([[f"G{k}", f"TEST G {k}", "Kelistrikan", "", "", "", 85000, 40000, 0, 0, "", 4],
                  [f"H{k}", f"TEST H {k}", "", "", "Merah", "", 1000, 0, 0, 0, "", 2],
                  [f"H{k}", f"TEST H {k}", "", "", "Ice Blue", "", 1000, 0, 0, 0, "", 2]])
        r = preview(owner, c).json()
        assert not r["errors"] and r["transactions_ready"] and r["summary"]["variants_new"] == 3
        assert {x["sku"] for x in r["rows"]} == {f"G{k}", f"H{k}-MERAH", f"H{k}-ICE-BLUE"}
        done = commit(owner, c, r["plan_hash"]).json()
        assert done["committed"]
        its = {i["sku"]: i for i in owner.get(f"{B}/items?q={k}").json()}
        assert its[f"G{k}"]["stock"] == 4 and its[f"G{k}"]["variant"] == "" and its[f"G{k}"]["name"] == f"TEST G {k}"
        muts = len(owner.get(f"{B}/stock/mutations?item_id={its[f'G{k}']['id']}").json())
        r2 = preview(owner, c).json()
        assert r2["summary"]["variants_same"] == 3 and r2["summary"]["variants_new"] == 0
        assert commit(owner, c, r2["plan_hash"]).json()["committed"]
        its2 = {i["sku"]: i for i in owner.get(f"{B}/items?q={k}").json()}
        assert len(its2) == 3 and its2[f"G{k}"]["stock"] == 4
        assert len(owner.get(f"{B}/stock/mutations?item_id={its[f'G{k}']['id']}").json()) == muts

    def test_data_berubah_setelah_pratinjau(self, owner, replset):
        k = uid().upper()
        c = xlsx([[f"J{k}", f"TEST J {k}", "", "", "", f"J{k}", 1000, 0, 0, 0, "", 1]])
        h = preview(owner, c).json()["plan_hash"]
        assert owner.post(f"{B}/products", json={"code": f"J{k}", "name": f"TEST J {k}", "sku": f"JX{k}", "price": 1}).status_code == 200
        r = commit(owner, c, h)
        assert r.status_code in (400, 409), r.text
        assert len([i for i in owner.get(f"{B}/items?q=J{k}").json() if i["sku"] == f"J{k}"]) == 0

    def test_dua_impor_bersamaan_tidak_ganda(self, owner, replset):
        k = uid().upper()
        c = xlsx([[f"K{k}", f"TEST K {k}", "", "", v, "", 1000, 0, 0, 0, "", 5] for v in ("A", "B", "C", "D")])
        h = preview(owner, c).json()["plan_hash"]
        res = []
        ts = [threading.Thread(target=lambda: res.append(commit(owner, c, h).status_code)) for _ in range(3)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert res.count(200) == 1, res
        its = owner.get(f"{B}/items?q=K{k}").json()
        assert len(its) == 4 and all(i["stock"] == 5 for i in its)
        assert mdb().stock_mutations.count_documents({"item_id": {"$in": [i["id"] for i in its]}}) == 4

    def test_tanpa_replica_set_tidak_menyimpan(self, owner):
        k = uid().upper()
        c = xlsx([[f"L{k}", f"TEST L {k}", "", "", "", "", 1000, 0, 0, 0, "", 1]])
        r = preview(owner, c).json()
        if r["transactions_ready"]:
            return
        assert commit(owner, c, r["plan_hash"]).status_code == 503 and not owner.get(f"{B}/items?q=L{k}").json()


def test_impor_gagal_di_tengah_tanpa_data_parsial(replset):
    port, db_name = _free_port(), f"{TEST_DB}_fault"
    proc = spawn_server(db_name, port, extra_env={"IMPORT_TEST_FAIL_AFTER": "4"})
    base = f"http://127.0.0.1:{port}/api"
    mc = MongoClient(MONGO_URL)
    fdb = mc[db_name]
    try:
        s = requests.Session()
        assert s.post(f"{base}/auth/login", json={"email": CREDS["owner"][0], "password": CREDS["owner"][1]}).status_code == 200
        ex = next(i for i in s.get(f"{base}/items").json() if i["sku"] == "TEST-RELAY-01")
        exp = next(p for p in s.get(f"{base}/products").json() if p["id"] == ex["product_id"])
        c = xlsx([["M1", "TEST M1", "", "", "Merah", "M1-R", 1000, 0, 0, 0, "", 5],
                  ["M1", "TEST M1", "", "", "Biru", "M1-B", 1000, 0, 0, 0, "", 5],
                  ["M2", "TEST M2", "", "", "", "M2", 1000, 0, 0, 0, "", 7],
                  [exp["code"], exp["name"], exp["category"], exp["brand"], ex["variant"], ex["sku"], 99999, 0, 0, 0, "", 50]])
        before = counts(fdb)
        before_ex = fdb.items.find_one({"id": ex["id"]}, {"_id": 0})
        r = preview(s, c, base).json()
        assert not r["errors"], r["errors"]
        out = commit(s, c, r["plan_hash"], base)
        assert out.status_code == 500 and "tidak ada data" in out.json()["detail"].lower()
        assert counts(fdb) == before
        assert fdb.items.find_one({"id": ex["id"]}, {"_id": 0}) == before_ex
        assert not fdb.products.find_one({"code": {"$in": ["M1", "M2"]}})
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        mc.drop_database(db_name)
        mc.close()


# ---------- 2. Hapus data khusus owner ----------
class TestDelete:
    def test_hapus_produk_belum_dipakai_dan_izin(self, owner, admin, kasir, replset):
        p, it = simple(owner)
        assert admin.get(f"{B}/admin/delete-check/product/{p['id']}").status_code == 403
        assert admin.delete(f"{B}/products/{p['id']}", params={"confirm": p["name"]}).status_code == 403
        assert kasir.delete(f"{B}/items/{it['id']}", params={"confirm": it["name"]}).status_code == 403
        chk = owner.get(f"{B}/admin/delete-check/product/{p['id']}").json()
        assert chk["can_delete"] and chk["variant_count"] == 1
        assert owner.delete(f"{B}/products/{p['id']}", params={"confirm": "salah"}).status_code == 400
        assert owner.delete(f"{B}/products/{p['id']}", params={"confirm": p["name"]}).json()["variants_deleted"] == 1
        assert not mdb().items.find_one({"id": it["id"]}) and mdb().deleted_records.find_one({"ref_id": it["id"]})
        assert mdb().audit_logs.find_one({"action": "hapus_produk", "ref_id": p["id"]})

    def test_stok_tersisa_ditolak_lalu_nol_boleh_mutasi_tetap(self, owner, replset):
        p, it = simple(owner, stock=4)
        chk = owner.get(f"{B}/admin/delete-check/product/{p['id']}").json()
        assert not chk["can_delete"] and any("stok 4 pcs" in r for r in chk["reasons"])
        assert owner.delete(f"{B}/products/{p['id']}", params={"confirm": p["name"]}).status_code == 409
        owner.post(f"{B}/stock/correction", json={"item_id": it["id"], "delta": -4, "reason": "TEST nol-kan"})
        assert owner.delete(f"{B}/products/{p['id']}", params={"confirm": p["name"]}).status_code == 200
        assert mdb().stock_mutations.count_documents({"item_id": it["id"]}) == 2

    def test_dipakai_paket_lalu_paket_dihapus(self, owner, replset):
        _, base = simple(owner)
        p2, alt = simple(owner)
        pk = owner.post(f"{B}/packages", json={"name": f"TEST Pk {uid()}", "price": 1000, "components": [{"item_id": base["id"], "qty": 1}],
                                               "options": [{"name": "Ganti", "mode": "replace", "replaces": base["id"], "price": 10,
                                                            "items": [{"item_id": alt["id"], "qty": 1}]}]}).json()
        name = owner.get(f"{B}/packages").json()
        pname = next(x["name"] for x in name if x["id"] == pk["id"])
        chk = owner.get(f"{B}/admin/delete-check/product/{p2['id']}").json()
        assert not chk["can_delete"] and chk["packages"][0]["can_delete"] and any(f"Paket {pname}" in r for r in chk["reasons"])
        assert owner.delete(f"{B}/packages/{pk['id']}", params={"confirm": pname}).status_code == 200
        assert owner.delete(f"{B}/products/{p2['id']}", params={"confirm": p2["name"]}).status_code == 200

    def test_dipakai_transaksi_semua_status(self, owner, kasir):
        _, a = simple(owner, stock=5)
        p_b, b = simple(owner, stock=5)
        p_c, c = simple(owner, stock=5)
        assert kasir.post(f"{B}/sales", json={"lines": [{"item_id": a["id"], "qty": 1}], "method": "tunai", "idem_key": uid() + uid()}).status_code == 200
        j = new_job(kasir, [{"type": "item", "item_id": b["id"], "qty": 1}]).json()
        assert owner.post(f"{B}/jobs/{j['id']}/cancel", json={"reason": "TEST batal"}).status_code == 200
        o = kasir.post(f"{B}/orders", json={"customer_name": "TEST O", "customer_phone": phone(), "delivery": "ambil",
                                            "lines": [{"type": "item", "item_id": c["id"], "qty": 1}]})
        assert o.status_code == 200, o.text
        for it, word in ((a, "penjualan langsung"), (b, "nota pekerjaan"), (c, "pesanan WhatsApp")):
            owner.post(f"{B}/stock/correction", json={"item_id": it["id"], "delta": -stock_of(owner, it["id"]), "reason": "TEST nol"})
            chk = owner.get(f"{B}/admin/delete-check/item/{it['id']}").json()
            assert not chk["can_delete"] and any(word in r for r in chk["reasons"]), chk
        assert owner.delete(f"{B}/products/{p_b['id']}", params={"confirm": p_b["name"]}).status_code == 409
        assert owner.post(f"{B}/items/{a['id']}/active", json={"active": False}).status_code == 200
        r = kasir.post(f"{B}/sales", json={"lines": [{"item_id": a["id"], "qty": 1}], "method": "tunai", "idem_key": uid() + uid()})
        assert r.status_code == 400 and "nonaktif" in r.text

    def test_paket_dipakai_tidak_bisa_dihapus_hanya_nonaktif(self, owner, kasir, pkg):
        j = new_job(kasir, [{"type": "package", "package_id": pkg["id"], "option_ids": [], "qty": 1}]).json()
        assert j["id"]
        chk = owner.get(f"{B}/admin/delete-check/package/{pkg['id']}").json()
        assert not chk["can_delete"] and "Nonaktifkan" in chk["reasons"][0]
        assert owner.delete(f"{B}/packages/{pkg['id']}", params={"confirm": pkg["name"]}).status_code == 409

    def test_hapus_varian_terakhir_diarahkan_ke_hapus_produk(self, owner, replset):
        k = uid().upper()
        r = owner.post(f"{B}/products", json={"code": f"V{k}", "name": f"TEST V {k}", "variants": [
            {"variant": "Merah", "price": 1}, {"variant": "Biru", "price": 1}]}).json()
        vs = {v["variant"]: v for v in next(x for x in owner.get(f"{B}/products?q=V{k}").json() if x["id"] == r["id"])["variants"]}
        assert owner.delete(f"{B}/items/{vs['Merah']['id']}", params={"confirm": vs["Merah"]["name"]}).status_code == 200
        chk = owner.get(f"{B}/admin/delete-check/item/{vs['Biru']['id']}").json()
        assert not chk["can_delete"] and "Hapus Produk" in chk["reasons"][-1]

    def test_pengguna(self, owner, admin, replset):
        mk = lambda: owner.post(f"{B}/users", json={"email": f"test.{uid()}@predator.local", "name": f"TEST User {uid()}", "role": "kasir",  # noqa: E731
                                                    "password": "Rahasia-123"}).json()
        u = mk()
        assert admin.delete(f"{B}/users/{u['id']}", params={"confirm": u["name"]}).status_code == 403
        assert owner.delete(f"{B}/users/{u['id']}", params={"confirm": u["name"]}).status_code == 200
        u2 = mk()
        s = requests.Session()
        assert s.post(f"{B}/auth/login", json={"email": u2["email"], "password": "Rahasia-123"}).status_code == 200
        assert new_job(s, []).status_code == 200
        chk = owner.get(f"{B}/admin/delete-check/user/{u2['id']}").json()
        assert not chk["can_delete"] and any("tercatat pada 1 transaksi" in r for r in chk["reasons"])
        assert owner.delete(f"{B}/users/{u2['id']}", params={"confirm": u2["name"]}).status_code == 409
        owner.patch(f"{B}/users/{u2['id']}", json={"active": False})
        assert s.get(f"{B}/jobs").status_code == 401
        assert requests.post(f"{B}/auth/login", json={"email": u2["email"], "password": "Rahasia-123"}).status_code == 401
        me = owner.get(f"{B}/auth/me").json()
        chk = owner.get(f"{B}/admin/delete-check/user/{me['id']}").json()
        assert not chk["can_delete"] and any("sedang anda pakai" in r for r in chk["reasons"])


# ---------- 4. Produk sederhana & varian ----------
class TestSimpleProduct:
    def test_produk_sederhana_di_kasir_paket_pesanan(self, owner, kasir):
        p, it = simple(owner, stock=10, price=85000)
        assert p["simple"] and it["sku"] == p["code"] and it["name"] == p["name"]
        s = kasir.post(f"{B}/sales", json={"lines": [{"item_id": it["id"], "qty": 2}], "method": "tunai", "idem_key": uid() + uid()}).json()
        assert s["total"] == 170000 and s["lines"][0]["name"] == p["name"] and stock_of(owner, it["id"]) == 8
        pk = owner.post(f"{B}/packages", json={"name": f"TEST PkS {uid()}", "price": 200000, "components": [{"item_id": it["id"], "qty": 1}]}).json()
        j = new_job(kasir, [{"type": "package", "package_id": pk["id"], "option_ids": [], "qty": 1}]).json()
        kasir.post(f"{B}/jobs/{j['id']}/complete")
        assert stock_of(owner, it["id"]) == 7
        o = kasir.post(f"{B}/orders", json={"customer_name": "TEST O", "customer_phone": phone(), "delivery": "ambil",
                                            "lines": [{"type": "item", "item_id": it["id"], "qty": 1}]}).json()
        kasir.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": 85000, "method": "transfer", "idem_key": uid()})
        assert stock_of(owner, it["id"]) == 6
        muts = owner.get(f"{B}/stock/mutations?item_id={it['id']}").json()
        assert sorted(m["kind"] for m in muts) == ["keluar_pekerjaan", "keluar_penjualan", "keluar_pesanan_wa", "stok_awal"]
        assert all(m["sku"] == it["sku"] for m in muts)

    def test_varian_wajib_nama_dan_tanpa_stok_ganda(self, owner):
        k = uid().upper()
        bad = owner.post(f"{B}/products", json={"name": f"TEST W {k}", "variants": [{"variant": "", "price": 1}, {"variant": "Biru", "price": 1}]})
        assert bad.status_code == 400
        r = owner.post(f"{B}/products", json={"code": f"W{k}", "name": f"TEST W {k}", "price": 999, "initial_stock": 9, "variants": [
            {"variant": "Merah", "price": 175000, "initial_stock": 2}, {"variant": "Ungu", "price": 180000, "initial_stock": 3}]}).json()
        p = next(x for x in owner.get(f"{B}/products?q=W{k}").json() if x["id"] == r["id"])
        assert p["stock_total"] == 5 and len(p["variants"]) == 2 and not p["simple"]
        assert {v["sku"] for v in p["variants"]} == {f"W{k}-MERAH", f"W{k}-UNGU"}

    def test_produk_sederhana_diberi_varian_kemudian(self, owner, kasir):
        p, it = simple(owner, stock=6)
        pk = owner.post(f"{B}/packages", json={"name": f"TEST PkV {uid()}", "price": 1000, "components": [{"item_id": it["id"], "qty": 1}]}).json()
        s = kasir.post(f"{B}/sales", json={"lines": [{"item_id": it["id"], "qty": 1}], "method": "tunai", "idem_key": uid() + uid()}).json()
        r = owner.post(f"{B}/products/{p['id']}/variants", json={"variant": "Biru", "price": 1})
        assert r.status_code == 400 and "barang lama" in r.text
        r = owner.post(f"{B}/products/{p['id']}/variants", json={"variant": "Biru", "price": 1, "standard_name": "Merah"})
        assert r.status_code == 200, r.text
        vs = {v["variant"]: v for v in next(x for x in owner.get(f"{B}/products?q={p['code']}").json() if x["id"] == p["id"])["variants"]}
        assert vs["Merah"]["id"] == it["id"] and vs["Merah"]["sku"] == it["sku"] and vs["Merah"]["stock"] == 5
        assert vs["Biru"]["sku"] == f"{p['code']}-BIRU" and vs["Biru"]["stock"] == 0
        assert next(x for x in owner.get(f"{B}/packages").json() if x["id"] == pk["id"])["components"][0]["item_id"] == it["id"]
        assert kasir.get(f"{B}/sales/{s['id']}").json()["lines"][0]["name"] == p["name"]


# ---------- 5. Opsi paket ----------
class TestPackageOptions:
    def _setup(self, owner):
        _, biled = simple(owner, stock=10)
        _, classic = simple(owner, stock=10)
        _, rgb = simple(owner, stock=10)
        _, relay = simple(owner, stock=10)
        _, rgb2 = simple(owner, stock=10)
        body = {"name": f"TEST Paket Shroud {uid()}", "price": 1500000, "warranty_days": 30,
                "components": [{"item_id": biled["id"], "qty": 2}, {"item_id": classic["id"], "qty": 2}],
                "options": [{"name": "Upgrade Shroud RGB", "mode": "replace", "replaces": classic["id"], "price": 350000,
                             "items": [{"item_id": rgb["id"], "qty": 2}]},
                            {"name": "Upgrade Shroud RGB Pro", "mode": "replace", "replaces": classic["id"], "price": 500000,
                             "items": [{"item_id": rgb2["id"], "qty": 2}]},
                            {"name": "Tambah Relay", "mode": "add", "price": 50000, "items": [{"item_id": relay["id"], "qty": 1}]}]}
        r = owner.post(f"{B}/packages", json=body)
        assert r.status_code == 200, r.text
        pk = next(x for x in owner.get(f"{B}/packages").json() if x["id"] == r.json()["id"])
        return pk, {o["name"]: o["id"] for o in pk["options"]}, biled, classic, rgb, relay

    def test_ganti_komponen_rp1850000_dan_stok_shroud(self, owner, kasir):
        pk, o, biled, classic, rgb, relay = self._setup(owner)
        j = new_job(kasir, [{"type": "package", "package_id": pk["id"], "option_ids": [o["Upgrade Shroud RGB"]], "qty": 1}]).json()
        assert j["total"] == 1850000
        comp = {c["item_id"]: c["qty"] for c in j["lines"][0]["components"]}
        assert comp == {biled["id"]: 2, rgb["id"]: 2}
        assert j["lines"][0]["options"][0]["mode"] == "replace" and j["lines"][0]["options"][0]["replaces_name"] == classic["name"]
        kasir.post(f"{B}/jobs/{j['id']}/complete")
        assert (stock_of(owner, biled["id"]), stock_of(owner, classic["id"]), stock_of(owner, rgb["id"])) == (8, 10, 8)
        owner.put(f"{B}/packages/{pk['id']}", json={"name": pk["name"], "price": 2000000, "components": [{"item_id": biled["id"], "qty": 1}], "options": []})
        old = kasir.get(f"{B}/jobs/{j['id']}").json()
        assert old["total"] == 1850000 and len(old["lines"][0]["components"]) == 2

    def test_tambah_barang_dan_opsi_bertentangan(self, owner, kasir):
        pk, o, biled, classic, rgb, relay = self._setup(owner)
        r = new_job(kasir, [{"type": "package", "package_id": pk["id"], "option_ids": [o["Upgrade Shroud RGB"], o["Upgrade Shroud RGB Pro"]], "qty": 1}])
        assert r.status_code == 400 and "bertentangan" in r.text
        o2 = kasir.post(f"{B}/orders", json={"customer_name": "TEST O", "customer_phone": phone(), "delivery": "ambil", "lines": [
            {"type": "package", "package_id": pk["id"], "option_ids": [o["Tambah Relay"], o["Upgrade Shroud RGB"]], "qty": 1}]}).json()
        assert o2["total"] == 1900000
        kasir.post(f"{B}/tx/order/{o2['id']}/payments", json={"amount": 1900000, "method": "transfer", "idem_key": uid()})
        assert (stock_of(owner, classic["id"]), stock_of(owner, rgb["id"]), stock_of(owner, relay["id"]), stock_of(owner, biled["id"])) == (10, 8, 9, 8)

    def test_validasi_definisi_paket(self, owner):
        _, a = simple(owner)
        _, b = simple(owner)
        r = owner.post(f"{B}/packages", json={"name": "TEST X", "price": 1000, "components": [{"item_id": a["id"], "qty": 1}],
                                              "options": [{"name": "Ganti", "mode": "replace", "replaces": b["id"], "price": 0, "items": [{"item_id": b["id"], "qty": 1}]}]})
        assert r.status_code == 400 and "komponen dasar" in r.text
        pk = owner.post(f"{B}/packages", json={"name": "TEST NonAktif", "price": 1000, "components": [{"item_id": a["id"], "qty": 1}]}).json()
        owner.post(f"{B}/packages/{pk['id']}/active", json={"active": False})
        r = new_job(owner, [{"type": "package", "package_id": pk["id"], "option_ids": [], "qty": 1}])
        assert r.status_code == 400 and "nonaktif" in r.text
