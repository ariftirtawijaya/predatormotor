"""Tes LIVE opsional terhadap server yang sudah berjalan (preview/VPS). TIDAK termasuk suite default.

Hanya membaca data: tidak menyimpan/menghapus token, tidak mengubah nomor, tidak mengirim pesan.
Jalankan manual:
  LIVE_BASE_URL=https://domain-anda LIVE_OWNER_EMAIL=... LIVE_OWNER_PASSWORD=... \
  LIVE_KASIR_EMAIL=... LIVE_KASIR_PASSWORD=... python -m pytest tests_live -q -n 0
"""
import os
import pytest
import requests

BASE = (os.environ.get("LIVE_BASE_URL") or "").rstrip("/")
NEED = ("LIVE_BASE_URL", "LIVE_OWNER_EMAIL", "LIVE_OWNER_PASSWORD", "LIVE_KASIR_EMAIL", "LIVE_KASIR_PASSWORD")
pytestmark = pytest.mark.skipif(any(not os.environ.get(k) for k in NEED), reason="Set " + ", ".join(NEED) + " untuk tes live")


def login(role):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": os.environ[f"LIVE_{role}_EMAIL"], "password": os.environ[f"LIVE_{role}_PASSWORD"]})
    if r.status_code != 200:
        pytest.fail(f"Login live {role} gagal: HTTP {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="module")
def owner():
    return login("OWNER")


@pytest.fixture(scope="module")
def kasir():
    return login("KASIR")


def test_settings_owner_only_and_masked(owner, kasir):
    assert kasir.get(f"{BASE}/api/settings/whatsapp").status_code == 403
    assert kasir.get(f"{BASE}/api/wa/logs").status_code == 403
    r = owner.get(f"{BASE}/api/settings/whatsapp")
    assert r.status_code == 200
    t = r.json()["token"]
    assert set(t) == {"configured", "readable", "masked", "updated_at", "updated_by"}
    assert not t["configured"] or t["masked"].startswith("••••••••")


def test_preview_without_origin_has_site_link(kasir):
    jobs = kasir.get(f"{BASE}/api/jobs").json()
    if not jobs:
        pytest.skip("Belum ada nota pekerjaan")
    p = kasir.get(f"{BASE}/api/wa/nota/job/{jobs[0]['id']}")
    assert p.status_code == 200 and len(p.json()["message_hash"]) == 64
    m = p.json()["message"]
    assert "/nota/" in m and "modal" not in m.lower() and "hpp" not in m.lower()


def test_bad_kind_404(kasir):
    assert kasir.get(f"{BASE}/api/wa/nota/foo/x").status_code == 404
