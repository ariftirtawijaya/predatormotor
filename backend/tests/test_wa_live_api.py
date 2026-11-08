"""Live (public URL) API checks for WhatsApp/Fonnte settings + nota preview. Never sends a real message:
send endpoints are only hit while NO token is configured (expect 409). Restores token/number state at the end."""
import json
import os
import uuid
import pytest
import requests
from conftest import BASE_URL

B = BASE_URL + "/api"
TOK = json.load(open(os.environ.get("WA_TOKS", "/tmp/toks.json")))


def sess(role):
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {TOK[role]['access']}"
    return s


@pytest.fixture(scope="module")
def owner():
    s = sess("owner")
    before = s.get(f"{B}/settings/whatsapp").json()
    yield s
    # restore: no token, number back to original draft/published
    s.delete(f"{B}/settings/whatsapp/token")
    s.put(f"{B}/settings/whatsapp/number", json={"number": before["admin_number"]})


# --- RBAC
@pytest.mark.parametrize("role", ["admin", "kasir"])
def test_settings_forbidden_non_owner(role):
    s = sess(role)
    assert s.get(f"{B}/settings/whatsapp").status_code == 403
    assert s.put(f"{B}/settings/whatsapp/token", json={"token": "FAKE-xxxxxxxx"}).status_code == 403
    assert s.get(f"{B}/wa/logs").status_code == 403


# --- token masking
def test_token_save_mask_replace_delete(owner):
    r = owner.put(f"{B}/settings/whatsapp/token", json={"token": "FAKE-api-token-1234"})
    assert r.status_code == 200, r.text
    assert "FAKE-api-token" not in r.text
    assert r.json()["token"]["masked"] == "••••••••1234"
    g = owner.get(f"{B}/settings/whatsapp")
    assert "FAKE-api-token" not in g.text and g.json()["token"]["configured"] is True
    r = owner.put(f"{B}/settings/whatsapp/token", json={"token": "FAKE-api-token-9876"})
    assert r.json()["token"]["masked"] == "••••••••9876"
    assert owner.put(f"{B}/settings/whatsapp/token", json={"token": "short"}).status_code == 422
    assert owner.put(f"{B}/settings/whatsapp/token", json={"token": "has space inside"}).status_code == 400
    d = owner.delete(f"{B}/settings/whatsapp/token")
    assert d.status_code == 200 and d.json()["token"]["configured"] is False


# --- admin number draft/publish
def test_number_normalize_invalid(owner):
    assert owner.put(f"{B}/settings/whatsapp/number", json={"number": "abc"}).status_code == 400
    assert owner.put(f"{B}/settings/whatsapp/number", json={"number": "0812"}).status_code == 400
    r = owner.put(f"{B}/settings/whatsapp/number", json={"number": "0812 3456 7890"})
    assert r.status_code == 200
    d = r.json()
    assert d["admin_number"] == "6281234567890" and d["pending_publish"] is True
    pub = requests.get(f"{B}/public/site").json()
    assert "6281234567890" not in json.dumps(pub)


def test_cms_contact_save_keeps_wa(owner):
    cms = owner.get(f"{B}/cms").json()
    contact = next(x for x in (cms if isinstance(cms, list) else cms.get("sections", cms.values())) if isinstance(x, dict) and x.get("key") == "contact") if not isinstance(cms, dict) or "contact" not in cms else cms["contact"]
    data = dict(contact["draft"], whatsapp="6289999999999")
    r = owner.put(f"{B}/cms/contact", json={"data": data})
    assert r.status_code == 200, r.text
    assert owner.get(f"{B}/settings/whatsapp").json()["admin_number"] == "6281234567890"


def test_send_test_no_token_409(owner):
    r = owner.post(f"{B}/settings/whatsapp/test", json={"send_key": "TESTWA" + uuid.uuid4().hex})
    assert r.status_code == 409 and "Token Fonnte belum diatur" in r.json()["detail"]


# --- nota preview (no cost) + send without token
def test_job_nota_preview_and_send_409():
    s = sess("kasir")
    jobs = s.get(f"{B}/jobs").json()
    jobs = jobs if isinstance(jobs, list) else jobs.get("items", [])
    if not jobs:
        pytest.skip("no jobs")
    j = jobs[0]
    before = s.get(f"{B}/jobs/{j['id']}").json()
    p = s.get(f"{B}/wa/nota/job/{j['id']}")
    assert p.status_code == 200
    m = p.json()["message"].lower()
    assert j["no"].lower() in m and "total" in m and "dibayar" in m
    assert "hpp" not in m and "modal" not in m and "cost" not in m
    r = s.post(f"{B}/wa/nota/job/{j['id']}", json={"send_key": "TESTWA" + uuid.uuid4().hex, "target": ""})
    if p.json()["target"]:
        assert r.status_code == 409 and "Token Fonnte belum diatur" in r.json()["detail"]
    else:
        assert r.status_code == 400
    after = s.get(f"{B}/jobs/{j['id']}").json()
    assert after.get("paid") == before.get("paid") and after.get("status") == before.get("status")


def test_bad_kind_404():
    assert sess("kasir").get(f"{B}/wa/nota/foo/x").status_code == 404
