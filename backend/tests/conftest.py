import os
import uuid
import pytest
import requests
from pathlib import Path


def _base():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        for line in Path("/app/frontend/.env").read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                url = line.split("=", 1)[1].strip()
    return url.rstrip("/")


BASE_URL = _base()
CREDS = {
    "owner": ("ainkarip@gmail.com", "PredatorOwner#2026"),
    "admin": ("admin.test@predator.local", "AdminUji#2026"),
    "kasir": ("kasir.test@predator.local", "KasirUji#2026"),
}


def login(role):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": CREDS[role][0], "password": CREDS[role][1]})
    if r.status_code != 200:
        pytest.skip(f"login {role} failed {r.status_code} {r.text}")
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
