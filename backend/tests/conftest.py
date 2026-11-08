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


def _creds():
    """Test accounts come from env (TEST_OWNER_EMAIL/TEST_OWNER_PASSWORD, ...) or the untracked memory/test_credentials.md."""
    out = {}
    f = Path(__file__).resolve().parents[2] / "memory" / "test_credentials.md"
    lines = f.read_text().splitlines() if f.exists() else []
    for role in ("owner", "admin", "kasir"):
        e, p = os.environ.get(f"TEST_{role.upper()}_EMAIL"), os.environ.get(f"TEST_{role.upper()}_PASSWORD")
        if not (e and p):
            for line in lines:
                if line.lower().startswith(f"- {role}") and "/" in line:
                    e, p = [x.strip() for x in line.split(":", 1)[1].split("(")[0].split(" / ")]
                    break
        out[role] = (e, p)
    return out


CREDS = _creds()


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
