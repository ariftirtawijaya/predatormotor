"""Integrasi Fonnte (in-process pada database tes terisolasi; API Fonnte di-mock dengan respx — tidak ada pesan nyata)."""
import asyncio
import json
from urllib.parse import parse_qs
import httpx
import pytest
import respx
from fastapi import HTTPException
from conftest import CREDS, TEST_DB, APP_DB, PUBLIC_SITE_URL, uid

import server
from core import db, iso, new_id
from wa_routes import normalize_wa, FONNTE_URL, FERNET

LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)
run = LOOP.run_until_complete
TOKEN = "TESTtokenFonnte-" + uid()
QUEUED = {"status": True, "detail": "success! message in queue", "id": ["80367170"], "process": "pending",
          "requestid": 2937124, "target": ["6281234567890"]}
COOKIES = {}


def client(ck=None):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test", cookies=ck)


def cookies(role):
    if role not in COOKIES:
        async def go():
            async with client() as c:
                return await c.post("/api/auth/login", json={"email": CREDS[role][0], "password": CREDS[role][1]})
        r = run(go())
        if r.status_code != 200:
            pytest.fail(f"Login uji {role} gagal: HTTP {r.status_code} {r.text}")
        COOKIES[role] = {"access_token": r.cookies["access_token"]}
    return COOKIES[role]


def call(role, method, path, **kw):
    ck = cookies(role)

    async def go():
        async with client(ck) as c:
            return await c.request(method, f"/api{path}", **kw)
    return run(go())


def preview(kind, tid, role="kasir"):
    r = call(role, "GET", f"/wa/nota/{kind}/{tid}")
    assert r.status_code == 200, r.text
    return r.json()


def send(kind, tid, role="kasir", **body):
    h = preview(kind, tid, role)["message_hash"]
    return call(role, "POST", f"/wa/nota/{kind}/{tid}", json={"send_key": "TESTWA-" + uid(), "message_hash": h} | body)


def fonnte(mock, **kw):
    return mock.post(FONNTE_URL).mock(**kw)


def make_tx(coll, phone="081234567890", **extra):
    d = {"id": new_id(), "no": f"TEST-WA-{uid()}", "status": "Masuk", "created_at": iso(), "public_token": "tok" + uid() * 3,
         "lines": [{"lid": "l1", "name": "BiLED Test", "detail": "Merek X", "qty": 2, "unit_price": 750000, "subtotal": 1500000,
                    "options": [], "removed": False, "components": [{"item_id": "x", "cost": 123457, "qty": 1}], "cost_total": 246914},
                   {"lid": "l2", "name": "Baris terhapus", "qty": 1, "unit_price": 5, "subtotal": 5, "removed": True, "components": []}],
         "subtotal": 1500000, "discount": {"amount": 100000, "status": "approved"}, "discount_amount": 100000, "total": 1400000,
         "hpp": 246914, "paid": 500000, "refunded": 0}
    if coll == "sales":
        d |= {"customer_name": "", "customer_phone": phone, "status": "Lunas"}
    else:
        d |= {"customer": {"name": "TEST Pelanggan", "phone": phone}}
    d |= extra
    run(db[coll].insert_one(d))
    d.pop("_id", None)
    return d


def snapshot(coll, tid):
    d = run(db[coll].find_one({"id": tid}, {"_id": 0}))
    return {k: d.get(k) for k in ("status", "ship_status", "paid", "refunded", "total", "lines", "stock_applied")}


def set_token():
    r = call("owner", "PUT", "/settings/whatsapp/token", json={"token": TOKEN})
    assert r.status_code == 200, r.text


def test_runs_on_isolated_database():
    assert db.name == TEST_DB and db.name != APP_DB and db.name.startswith("predator_pytest_")
    assert FONNTE_URL.startswith("http://127.0.0.1:9/")


# ---------- Normalisasi ----------
@pytest.mark.parametrize("raw", ["081234567890", "6281234567890", "+6281234567890", "+62 812-3456-7890", "0812 3456 7890"])
def test_normalize_valid(raw):
    assert normalize_wa(raw) == "6281234567890"


@pytest.mark.parametrize("raw", ["", "12345", "0812abc", "+15551234567", "62021234567", "0812", "62812345678901234"])
def test_normalize_invalid(raw):
    with pytest.raises(HTTPException):
        normalize_wa(raw)


# ---------- Hak akses & token tersamar ----------
class TestSettings:
    def test_only_owner(self):
        for role in ("admin", "kasir"):
            for m, p, kw in (("GET", "/settings/whatsapp", {}), ("PUT", "/settings/whatsapp/token", {"json": {"token": "abcdefghij"}}),
                             ("DELETE", "/settings/whatsapp/token", {}), ("PUT", "/settings/whatsapp/number", {"json": {"number": "081200000000"}}),
                             ("POST", "/settings/whatsapp/test", {"json": {"send_key": "TESTWA-x-" + uid()}}),
                             ("POST", "/settings/whatsapp/publish-number", {}), ("GET", "/wa/logs", {})):
                assert call(role, m, p, **kw).status_code == 403, (role, m, p)

    def test_token_masked_never_returned(self):
        set_token()
        r = call("owner", "GET", "/settings/whatsapp")
        assert r.status_code == 200
        assert TOKEN not in r.text
        t = r.json()["token"]
        assert t["configured"] and t["readable"] and t["masked"].endswith(TOKEN[-4:]) and t["masked"].startswith("••••")
        doc = run(db.settings.find_one({"key": "fonnte"}))
        assert TOKEN not in json.dumps(doc, default=str)
        assert FERNET.decrypt(doc["token_enc"].encode()).decode() == TOKEN
        for coll in ("audit_logs", "cms_revisions", "cms"):
            rows = run(db[coll].find({}, {"_id": 0}).to_list(5000))
            assert TOKEN not in json.dumps(rows, default=str), coll

    def test_token_replace_and_delete(self):
        set_token()
        r = call("owner", "PUT", "/settings/whatsapp/token", json={"token": "GANTItoken-9999"})
        assert r.json()["token"]["masked"].endswith("9999")
        r = call("owner", "DELETE", "/settings/whatsapp/token")
        assert r.json()["token"]["configured"] is False
        assert call("owner", "PUT", "/settings/whatsapp/token", json={"token": "ada spasi token"}).status_code == 400
        assert call("owner", "PUT", "/settings/whatsapp/token", json={"token": "short"}).status_code == 422
        set_token()

    def test_number_draft_publish_single_source(self):
        before = call("owner", "GET", "/settings/whatsapp").json()["published_number"]
        assert call("owner", "PUT", "/settings/whatsapp/number", json={"number": "abc"}).status_code == 400
        r = call("owner", "PUT", "/settings/whatsapp/number", json={"number": "+62 811-2223-334"})
        s = r.json()
        assert s["admin_number"] == "628112223334" and s["published_number"] == before and s["pending_publish"]
        assert call("owner", "GET", "/public/site").json()["contact"]["whatsapp"] == before
        # Admin menyimpan CMS Kontak dengan nomor lain → nomor tidak berubah (hanya lewat Pengaturan).
        c = call("admin", "GET", "/cms").json()
        draft = next(x for x in c if x["key"] == "contact")["draft"]
        assert call("admin", "PUT", "/cms/contact", json={"data": {**draft, "whatsapp": "6289999999999"}}).status_code == 200
        assert call("owner", "GET", "/settings/whatsapp").json()["admin_number"] == "628112223334"
        r = call("owner", "POST", "/settings/whatsapp/publish-number")
        assert r.json()["published_number"] == "628112223334" and not r.json()["pending_publish"]
        assert call("owner", "GET", "/public/site").json()["contact"]["whatsapp"] == "628112223334"

    def test_test_message_to_admin_number(self):
        set_token()
        call("owner", "PUT", "/settings/whatsapp/number", json={"number": "081122233344"})
        with respx.mock(assert_all_called=False) as m:
            route = fonnte(m, return_value=httpx.Response(200, json=QUEUED))
            key = "TESTWA-test-" + uid()
            r = call("owner", "POST", "/settings/whatsapp/test", json={"send_key": key})
            r2 = call("owner", "POST", "/settings/whatsapp/test", json={"send_key": key})
        assert r.status_code == 200 and r.json()["status"] == "antre" and r.json()["request_id"] == 2937124
        assert r2.json()["duplicate"] is True and route.call_count == 1
        form = parse_qs(route.calls[0].request.content.decode())
        assert form["target"] == ["6281122233344"] and route.calls[0].request.headers["authorization"] == TOKEN
        assert TOKEN not in r.text


# ---------- Pengiriman nota ----------
class TestNota:
    def test_preview_without_origin_equals_sent_message(self):
        set_token()
        job = make_tx("jobs", vehicle={"plate": "S1234AB", "brand": "Honda", "model": "Vario"})
        p = preview("job", job["id"])
        link = f"{PUBLIC_SITE_URL}/nota/{job['public_token']}"
        assert f"Lihat nota: {link}" in p["message"]
        with respx.mock(assert_all_called=False) as m:
            route = fonnte(m, return_value=httpx.Response(200, json=QUEUED))
            r = call("kasir", "POST", f"/wa/nota/job/{job['id']}", json={"send_key": "TESTWA-" + uid(), "message_hash": p["message_hash"]})
        assert r.status_code == 200, r.text
        assert parse_qs(route.calls[0].request.content.decode())["message"][0] == p["message"]

    def test_stale_or_missing_preview_rejected(self):
        set_token()
        job = make_tx("jobs")
        p = preview("job", job["id"])
        run(db.jobs.update_one({"id": job["id"]}, {"$set": {"paid": 1400000}}))
        with respx.mock(assert_all_called=False) as m:
            route = fonnte(m, return_value=httpx.Response(200, json=QUEUED))
            r = call("kasir", "POST", f"/wa/nota/job/{job['id']}", json={"send_key": "TESTWA-" + uid(), "message_hash": p["message_hash"]})
            r2 = call("kasir", "POST", f"/wa/nota/job/{job['id']}", json={"send_key": "TESTWA-" + uid()})
        assert r.status_code == 409 and "berubah" in r.json()["detail"]
        assert r2.status_code == 422 and route.call_count == 0
        assert "LUNAS" in preview("job", job["id"])["message"]

    def test_job_queued_content_and_no_side_effects(self):
        set_token()
        job = make_tx("jobs", vehicle={"plate": "S1234AB", "brand": "Honda", "model": "Vario"})
        snap = snapshot("jobs", job["id"])
        with respx.mock(assert_all_called=False) as m:
            route = fonnte(m, return_value=httpx.Response(200, json=QUEUED))
            r = send("job", job["id"])
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "antre" and r.json()["message_ids"] == ["80367170"]
        req = route.calls[0].request
        assert req.headers["authorization"] == TOKEN and not req.headers["authorization"].startswith("Bearer")
        form = parse_qs(req.content.decode())
        assert form["target"] == ["6281234567890"] and form["countryCode"] == ["0"]
        msg = form["message"][0]
        for s in (job["no"], "BiLED Test", "2 x Rp750.000 = Rp1.500.000", "Diskon: -Rp100.000", "Total: Rp1.400.000",
                  "Total dibayar: Rp500.000", "Sisa tagihan: Rp900.000", "S1234AB"):
            assert s in msg, s
        for s in ("Baris terhapus", "123.457", "246.914", "hpp", "cost", "modal"):
            assert s not in msg, s
        assert snapshot("jobs", job["id"]) == snap
        log = run(db.wa_logs.find_one({"ref_id": job["id"]}, {"_id": 0}))
        assert log["user_name"] and log["target"] == "6281234567890" and log["request_id"] == 2937124 and log["ref_no"] == job["no"]
        assert TOKEN not in json.dumps(log, default=str)

    def test_rejected_reason_and_no_side_effects(self):
        set_token()
        order = make_tx("orders", ship_status="Baru", payment_type="prepaid", shipping_cost=20000, status=None)
        snap = snapshot("orders", order["id"])
        with respx.mock(assert_all_called=False) as m:
            fonnte(m, return_value=httpx.Response(200, json={"status": False, "reason": "device disconnected"}))
            r = send("order", order["id"])
        assert r.status_code == 200 and r.json()["status"] == "ditolak" and r.json()["reason"] == "device disconnected"
        assert snapshot("orders", order["id"]) == snap
        # Gagal/ditolak tidak memblokir pengiriman biasa berikutnya
        with respx.mock(assert_all_called=False) as m:
            fonnte(m, return_value=httpx.Response(200, json=QUEUED))
            r = send("order", order["id"])
        assert r.json()["status"] == "antre" and r.json()["resend"] is False

    def test_timeout_uncertain_no_auto_retry(self):
        set_token()
        job = make_tx("jobs")
        with respx.mock(assert_all_called=False) as m:
            route = fonnte(m, side_effect=httpx.ReadTimeout("timeout"))
            r = send("job", job["id"])
        assert r.json()["status"] == "tidak_pasti" and route.call_count == 1
        # status tidak pasti → wajib kirim ulang yang disengaja
        assert send("job", job["id"]).status_code == 409

    def test_connect_error_failed(self):
        set_token()
        job = make_tx("jobs")
        with respx.mock(assert_all_called=False) as m:
            route = fonnte(m, side_effect=httpx.ConnectError("down"))
            r = send("job", job["id"])
        assert r.json()["status"] == "gagal" and route.call_count == 1 and "belum terkirim" in r.json()["reason"]

    def test_unmocked_call_never_leaves_machine(self):
        set_token()
        r = send("job", make_tx("jobs")["id"])
        assert r.status_code == 200 and r.json()["status"] == "gagal"

    def test_double_click_and_resend(self):
        set_token()
        job = make_tx("jobs")
        h = preview("job", job["id"])["message_hash"]
        key = "TESTWA-" + uid()
        with respx.mock(assert_all_called=False) as m:
            route = fonnte(m, return_value=httpx.Response(200, json=QUEUED))
            r1 = call("kasir", "POST", f"/wa/nota/job/{job['id']}", json={"send_key": key, "message_hash": h})
            r2 = call("kasir", "POST", f"/wa/nota/job/{job['id']}", json={"send_key": key, "message_hash": h})
            r3 = send("job", job["id"])
            r4 = send("job", job["id"], resend=True)
            r5 = send("job", job["id"], resend=True, resend_reason="pelanggan minta lagi")
        assert r1.json()["status"] == "antre" and r2.json()["duplicate"] is True and r2.json()["id"] == r1.json()["id"]
        assert r3.status_code == 409 and r4.status_code == 400
        assert r5.status_code == 200 and r5.json()["resend"] is True and r5.json()["resend_reason"] == "pelanggan minta lagi"
        assert route.call_count == 2
        assert run(db.wa_logs.count_documents({"ref_id": job["id"]})) == 2

    def test_concurrent_clicks_single_send(self):
        set_token()
        job = make_tx("jobs")
        h = preview("job", job["id"])["message_hash"]
        ck = cookies("kasir")

        async def burst():
            async def slow(request):
                await asyncio.sleep(0.3)
                return httpx.Response(200, json=QUEUED)
            with respx.mock(assert_all_called=False) as m:
                route = fonnte(m, side_effect=slow)
                async with client(ck) as c:
                    rs = await asyncio.gather(*[c.post(f"/api/wa/nota/job/{job['id']}",
                                                       json={"send_key": "TESTWA-" + uid(), "message_hash": h}) for _ in range(5)])
                return rs, route.call_count
        rs, n = run(burst())
        assert n == 1 and sorted(r.status_code for r in rs) == [200, 409, 409, 409, 409]

    def test_sale_without_phone_needs_target(self):
        set_token()
        sale = make_tx("sales", phone="")
        prev = preview("sale", sale["id"])
        assert prev["target_editable"] is True and prev["target"] == "" and "LUNAS" not in prev["message"]
        assert send("sale", sale["id"]).status_code == 400
        assert send("sale", sale["id"], target="12345").status_code == 400
        with respx.mock(assert_all_called=False) as m:
            route = fonnte(m, return_value=httpx.Response(200, json=QUEUED))
            r = send("sale", sale["id"], target="+62 857-1111-2222")
        assert r.status_code == 200 and parse_qs(route.calls[0].request.content.decode())["target"] == ["6285711112222"]

    def test_job_without_phone_rejected_and_no_token(self):
        job = make_tx("jobs", phone="")
        assert send("job", job["id"]).status_code == 400
        call("owner", "DELETE", "/settings/whatsapp/token")
        job2 = make_tx("jobs")
        with respx.mock(assert_all_called=False) as m:
            route = fonnte(m, return_value=httpx.Response(200, json=QUEUED))
            r = send("job", job2["id"])
        assert r.status_code == 409 and "Token Fonnte belum diatur" in r.json()["detail"] and route.call_count == 0
        set_token()

    def test_logs_owner_view(self):
        r = call("owner", "GET", "/wa/logs")
        assert r.status_code == 200 and isinstance(r.json(), list) and r.json()
        assert TOKEN not in r.text
