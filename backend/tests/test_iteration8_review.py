"""Iterasi 8 \u2014 perbaikan review: konfigurasi replica set, paket dengan komponen nonaktif, hapus produk/varian atomik."""
import re
from pathlib import Path
import pytest
import requests
from pymongo import MongoClient
from conftest import CREDS, MONGO_URL, TEST_DB, uid, spawn_server, _free_port
from test_iteration8 import B, simple, new_job, mdb

ROOT = Path(__file__).resolve().parents[2]


def test_konfigurasi_replica_set_konsisten():
    if not (ROOT / "docker-compose.yml").exists():
        pytest.skip("Berkas repo lengkap tidak tersedia (mis. di dalam container uji)")
    env = (ROOT / "backend/.env.example").read_text()
    compose = (ROOT / "docker-compose.yml").read_text()
    readme = (ROOT / "README.md").read_text()
    url = re.search(r'^MONGO_URL="?([^"\n]+)"?', env, re.M).group(1)
    assert url == "mongodb://mongo:27017/?replicaSet=rs0"
    assert url in readme
    assert re.search(r"MONGO_URL:\s*" + re.escape(url), compose), "docker-compose harus memaksa MONGO_URL replica set"
    assert '"--replSet", "rs0"' in compose and "host: 'mongo:27017'" in compose


class TestPaketKomponenNonaktif:
    def _pkg(self, owner):
        _, base = simple(owner, stock=5)
        _, alt = simple(owner, stock=5)
        r = owner.post(f"{B}/packages", json={"name": f"TEST PkNA {uid()}", "price": 1000, "components": [{"item_id": base["id"], "qty": 1}],
                                              "options": [{"name": "Ganti", "mode": "replace", "replaces": base["id"], "price": 0,
                                                           "items": [{"item_id": alt["id"], "qty": 1}]}]}).json()
        pk = next(x for x in owner.get(f"{B}/packages").json() if x["id"] == r["id"])
        return pk, pk["options"][0]["id"], base, alt

    def test_komponen_dasar_nonaktif_ditolak_dengan_nama_barang(self, owner, kasir):
        pk, opt, base, alt = self._pkg(owner)
        owner.post(f"{B}/items/{base['id']}/active", json={"active": False})
        r = new_job(kasir, [{"type": "package", "package_id": pk["id"], "option_ids": [], "qty": 1}])
        assert r.status_code == 400 and base["name"] in r.json()["detail"] and base["sku"] in r.json()["detail"] and "nonaktif" in r.text
        o = kasir.post(f"{B}/orders", json={"customer_name": "TEST O", "customer_phone": "081377788899", "delivery": "ambil",
                                            "lines": [{"type": "package", "package_id": pk["id"], "option_ids": [], "qty": 1}]})
        assert o.status_code == 400 and base["name"] in o.json()["detail"]
        ok = new_job(kasir, [{"type": "package", "package_id": pk["id"], "option_ids": [opt], "qty": 1}])
        assert ok.status_code == 200, ok.text
        assert [c["item_id"] for c in ok.json()["lines"][0]["components"]] == [alt["id"]]

    def test_barang_pengganti_nonaktif_ditolak(self, owner, kasir):
        pk, opt, base, alt = self._pkg(owner)
        owner.post(f"{B}/items/{alt['id']}/active", json={"active": False})
        r = new_job(kasir, [{"type": "package", "package_id": pk["id"], "option_ids": [opt], "qty": 1}])
        assert r.status_code == 400 and alt["name"] in r.json()["detail"]
        assert new_job(kasir, [{"type": "package", "package_id": pk["id"], "option_ids": [], "qty": 1}]).status_code == 200


def test_hapus_tanpa_replica_set_ditolak(owner):
    from conftest import REPLSET
    if REPLSET:
        pytest.skip("Hanya relevan pada MongoDB standalone")
    p, it = simple(owner)
    r = owner.delete(f"{B}/products/{p['id']}", params={"confirm": p["name"]})
    assert r.status_code == 503 and mdb().items.find_one({"id": it["id"]})


SNAP = ("products", "items", "deleted_records", "audit_logs", "stock_mutations")


@pytest.mark.parametrize("stage,target", [("after_item_delete", "product"), ("after_variants", "product"), ("before_audit", "product"),
                                          ("after_item_delete", "item"), ("before_audit", "item")])
def test_hapus_gagal_di_tengah_tidak_ada_perubahan(replset, stage, target):
    port, db_name = _free_port(), f"{TEST_DB}_del_{stage}_{target}"
    proc = spawn_server(db_name, port, extra_env={"DELETE_TEST_FAIL_AT": stage})
    base = f"http://127.0.0.1:{port}/api"
    mc = MongoClient(MONGO_URL)
    fdb = mc[db_name]
    try:
        s = requests.Session()
        assert s.post(f"{base}/auth/login", json={"email": CREDS["owner"][0], "password": CREDS["owner"][1]}).status_code == 200
        k = uid().upper()
        r = s.post(f"{base}/products", json={"code": f"DF{k}", "name": f"TEST Del {k}", "variants": [
            {"variant": "Merah", "price": 1, "initial_stock": 2}, {"variant": "Biru", "price": 1}, {"variant": "Ungu", "price": 1}]}).json()
        p = next(x for x in s.get(f"{base}/products?q=DF{k}").json() if x["id"] == r["id"])
        red = next(v for v in p["variants"] if v["variant"] == "Merah")
        s.post(f"{base}/stock/correction", json={"item_id": red["id"], "delta": -2, "reason": "TEST nol"})
        before = {c: list(fdb[c].find({}, {"_id": 0}).sort("id", 1)) for c in SNAP}
        if target == "product":
            out = s.delete(f"{base}/products/{p['id']}", params={"confirm": p["name"]})
        else:
            out = s.delete(f"{base}/items/{red['id']}", params={"confirm": red["name"]})
        assert out.status_code == 500 and "tidak ada data yang terhapus" in out.json()["detail"]
        after = {c: list(fdb[c].find({}, {"_id": 0}).sort("id", 1)) for c in SNAP}
        assert after == before
        assert len(s.get(f"{base}/products?q=DF{k}").json()[0]["variants"]) == 3
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        mc.drop_database(db_name)
        mc.close()
