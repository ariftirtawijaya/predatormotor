"""Suite tes default: berjalan pada server uvicorn KHUSUS TES dengan database MongoDB sementara.

Setiap worker pytest membuat database `predator_pytest_*` baru, akun uji dengan password acak,
folder unggahan sementara, dan JWT_SECRET acak. Database aplikasi (DB_NAME di backend/.env) tidak
pernah disentuh; API Fonnte dialihkan ke alamat buntu sehingga tidak ada pesan nyata yang terkirim.
"""
import os
import atexit
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
import pytest
import requests
from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parents[1]
_app_env = dotenv_values(BACKEND / ".env") if (BACKEND / ".env").exists() else {}
MONGO_URL = os.environ.get("TEST_MONGO_URL") or os.environ.get("MONGO_URL") or _app_env.get("MONGO_URL")
APP_DB = _app_env.get("DB_NAME") or os.environ.get("DB_NAME")
if not MONGO_URL:
    raise RuntimeError("MONGO_URL tidak ditemukan (isi backend/.env atau set TEST_MONGO_URL) — tes butuh MongoDB yang berjalan.")

WORKER = os.environ.get("PYTEST_XDIST_WORKER", "main")
TEST_DB = f"predator_pytest_{WORKER}_{uuid.uuid4().hex[:8]}"
if TEST_DB == APP_DB:
    raise RuntimeError("Database tes tidak boleh sama dengan database aplikasi")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = _free_port()
BASE_URL = f"http://127.0.0.1:{PORT}"
PUBLIC_SITE_URL = "https://nota.predator.test"
CREDS = {"owner": ("owner.pytest@predator.local", "Own-" + secrets.token_urlsafe(12)),
         "admin": ("admin.test@predator.local", "Adm-" + secrets.token_urlsafe(12)),
         "kasir": ("kasir.test@predator.local", "Ksr-" + secrets.token_urlsafe(12))}
UPLOAD_DIR = tempfile.mkdtemp(prefix="predator-pytest-")
atexit.register(shutil.rmtree, UPLOAD_DIR, True)
TEST_ENV = {
    "MONGO_URL": MONGO_URL, "DB_NAME": TEST_DB, "JWT_SECRET": secrets.token_hex(32), "UPLOAD_DIR": UPLOAD_DIR,
    "CORS_ORIGINS": BASE_URL, "COOKIE_SECURE": "false", "COOKIE_SAMESITE": "lax", "APP_TIMEZONE": "Asia/Jakarta",
    "MAX_UPLOAD_MB": "5", "DISABLE_DOCS": "true", "OWNER_EMAIL": CREDS["owner"][0], "OWNER_PASSWORD": CREDS["owner"][1],
    "OWNER_NAME": "Owner Uji", "PUBLIC_SITE_URL": PUBLIC_SITE_URL, "FONNTE_API_URL": "http://127.0.0.1:9/fonnte-diblokir-saat-tes",
}
# Diset sebelum modul backend diimpor oleh tes in-process; load_dotenv tidak menimpa nilai yang sudah ada.
os.environ.update(TEST_ENV)


def _wait(proc, log):
    for _ in range(120):
        if proc.poll() is not None:
            break
        try:
            if requests.get(f"{BASE_URL}/api/health", timeout=1).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.25)
    pytest.exit(f"Server tes gagal berjalan:\n{Path(log).read_text()[-3000:]}", returncode=3)


@pytest.fixture(scope="session", autouse=True)
def test_server():
    log = os.path.join(UPLOAD_DIR, "server.log")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(PORT)],
                            cwd=BACKEND, env=os.environ.copy(), stdout=open(log, "w"), stderr=subprocess.STDOUT)
    try:
        _wait(proc, log)
        seed = subprocess.run([sys.executable, "seed_demo.py"], cwd=BACKEND, capture_output=True, text=True,
                              env={**os.environ, "ALLOW_DEMO_SEED": "true", "DEMO_ADMIN_PASSWORD": CREDS["admin"][1],
                                   "DEMO_KASIR_PASSWORD": CREDS["kasir"][1]})
        if seed.returncode != 0:
            pytest.exit(f"seed_demo.py gagal:\n{seed.stdout}\n{seed.stderr}", returncode=3)
        yield
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        from pymongo import MongoClient
        c = MongoClient(MONGO_URL)
        c.drop_database(TEST_DB)
        c.close()
        shutil.rmtree(UPLOAD_DIR, ignore_errors=True)


def login(role):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": CREDS[role][0], "password": CREDS[role][1]})
    if r.status_code != 200:
        pytest.fail(f"Login uji {role} ({CREDS[role][0]}) gagal: HTTP {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="session")
def owner():
    return login("owner")


@pytest.fixture(scope="session")
def admin():
    return login("admin")


@pytest.fixture(scope="session")
def kasir():
    return login("kasir")


@pytest.fixture(scope="session")
def anon():
    return requests.Session()


@pytest.fixture(scope="session")
def items(owner):
    r = owner.get(f"{BASE_URL}/api/items")
    return {i["sku"]: i for i in r.json()}


@pytest.fixture(scope="session")
def pkg(owner):
    return next(p for p in owner.get(f"{BASE_URL}/api/packages").json() if p["name"] == "[TEST] Paket BiLED + Shroud")


def uid():
    return uuid.uuid4().hex[:10]


def stock_of(s, iid):
    return next(i for i in s.get(f"{BASE_URL}/api/items").json() if i["id"] == iid)["stock"]


def ensure_stock(owner, iid, need):
    cur = stock_of(owner, iid)
    if cur < need:
        owner.post(f"{BASE_URL}/api/stock/in", json={"item_id": iid, "qty": need - cur + 5, "note": "TEST topup"})
