"""Hapus Paket & Pengguna atomik: data utama + deleted_records + audit log berhasil/batal bersama."""
import pytest
import requests
from pymongo import MongoClient
from conftest import CREDS, MONGO_URL, TEST_DB, REPLSET, uid, spawn_server, _free_port
from test_iteration8 import B, simple, mdb


def _login(base, email, pw):
    s = requests.Session()
    assert s.post(f"{base}/auth/login", json={"email": email, "password": pw}).status_code == 200
    return s


def test_hapus_paket_pengguna_tanpa_replica_set_ditolak(owner):
    if REPLSET:
        pytest.skip("Hanya relevan pada MongoDB standalone")
    _, it = simple(owner)
    pname = f"TEST PkSA {uid()}"
    pk = owner.post(f"{B}/packages", json={"name": pname, "price": 1, "components": [{"item_id": it["id"], "qty": 1}]}).json()
    r = owner.delete(f"{B}/packages/{pk['id']}", params={"confirm": pname})
    assert r.status_code == 503 and "replica set" in r.json()["detail"] and mdb().packages.find_one({"id": pk["id"]})
    u = owner.post(f"{B}/users", json={"email": f"test.{uid()}@predator.local", "name": f"TEST U {uid()}", "role": "kasir", "password": "Rahasia-123"}).json()
    r = owner.delete(f"{B}/users/{u['id']}", params={"confirm": u["name"]})
    assert r.status_code == 503 and mdb().users.find_one({"id": u["id"]})


def test_hapus_owner_lain_boleh_tapi_diri_sendiri_tidak(owner, replset):
    me = owner.get(f"{B}/auth/me").json()
    o2 = owner.post(f"{B}/users", json={"email": f"test.{uid()}@predator.local", "name": f"TEST Owner {uid()}", "role": "owner", "password": "Rahasia-123"}).json()
    assert owner.delete(f"{B}/users/{me['id']}", params={"confirm": me["name"]}).status_code == 409
    assert owner.delete(f"{B}/users/{o2['id']}", params={"confirm": o2["name"]}).status_code == 200
    assert mdb().deleted_records.find_one({"ref_id": o2["id"], "ref_type": "user"})
    assert mdb().audit_logs.find_one({"action": "hapus_pengguna", "ref_id": o2["id"]})


@pytest.mark.parametrize("stage", ["after_main_delete", "before_audit"])
def test_hapus_paket_dan_pengguna_gagal_di_tengah(replset, stage):
    port, db_name = _free_port(), f"{TEST_DB}_delpu_{stage}"
    proc = spawn_server(db_name, port, extra_env={"DELETE_TEST_FAIL_AT": stage})
    base = f"http://127.0.0.1:{port}/api"
    mc = MongoClient(MONGO_URL)
    fdb = mc[db_name]
    try:
        s = _login(base, *CREDS["owner"])
        item = next(i for i in s.get(f"{base}/items").json() if i["sku"] == "TEST-RELAY-01")
        pname = f"TEST PkF {uid()}"
        pk = s.post(f"{base}/packages", json={"name": pname, "price": 1, "components": [{"item_id": item["id"], "qty": 1}]}).json()
        pk["name"] = pname
        u = s.post(f"{base}/users", json={"email": f"test.{uid()}@predator.local", "name": f"TEST UF {uid()}", "role": "kasir",
                                          "password": "Rahasia-123"}).json()
        before_pk = fdb.packages.find_one({"id": pk["id"]}, {"_id": 0})
        before_u = fdb.users.find_one({"id": u["id"]}, {"_id": 0})
        n_arch, n_audit = fdb.deleted_records.count_documents({}), fdb.audit_logs.count_documents({})
        for url, name in ((f"{base}/packages/{pk['id']}", pk["name"]), (f"{base}/users/{u['id']}", u["name"])):
            r = s.delete(url, params={"confirm": name})
            assert r.status_code == 500 and "tidak ada data yang terhapus" in r.json()["detail"], r.text
        assert fdb.packages.find_one({"id": pk["id"]}, {"_id": 0}) == before_pk
        assert fdb.users.find_one({"id": u["id"]}, {"_id": 0}) == before_u
        assert fdb.deleted_records.count_documents({}) == n_arch and not fdb.deleted_records.find_one({"ref_id": {"$in": [pk["id"], u["id"]]}})
        assert fdb.audit_logs.count_documents({}) == n_audit
        assert not fdb.audit_logs.find_one({"action": {"$in": ["hapus_paket", "hapus_pengguna"]}})
        assert _login(base, u["email"], "Rahasia-123")
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        mc.drop_database(db_name)
        mc.close()
