import os
import re
import uuid
import secrets
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import bcrypt
import jwt
from fastapi import Request, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
TZ = ZoneInfo(os.environ.get("APP_TIMEZONE", "Asia/Jakarta"))
JWT_SECRET = os.environ["JWT_SECRET"]
UPLOAD_DIR = Path(os.environ["UPLOAD_DIR"])
(UPLOAD_DIR / "public").mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "private").mkdir(parents=True, exist_ok=True)
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax")
ROLES = ("owner", "admin", "kasir")
STAFF = ROLES
MANAGERS = ("owner", "admin")


def now():
    return datetime.now(timezone.utc)


def iso():
    return now().isoformat()


def local_date(dt=None):
    return (dt or now()).astimezone(TZ).strftime("%Y-%m-%d")


def new_id():
    return uuid.uuid4().hex


def token():
    return secrets.token_urlsafe(24)


def clean(doc):
    if doc:
        doc.pop("_id", None)
    return doc


async def find_list(coll, q, sort=None, limit=1000):
    cur = db[coll].find(q, {"_id": 0})
    if sort:
        cur = cur.sort(sort)
    return await cur.to_list(limit)


async def get_or_404(coll, id_, msg="Data tidak ditemukan"):
    doc = await db[coll].find_one({"id": id_}, {"_id": 0})
    if not doc:
        raise HTTPException(404, msg)
    return doc


def norm_phone(p):
    d = re.sub(r"\D", "", p or "")
    if d.startswith("0"):
        d = "62" + d[1:]
    elif d.startswith("8"):
        d = "62" + d
    return d


def norm_text(s):
    return " ".join(str(s or "").split())


def text_key(s):
    return norm_text(s).casefold()


def norm_sku(s):
    return re.sub(r"\s+", "", str(s or "")).upper()


async def is_replica_set():
    try:
        return bool((await client.admin.command("hello")).get("setName"))
    except Exception:
        return False


def norm_plate(p):
    return re.sub(r"[^A-Z0-9]", "", (p or "").upper())


def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw, h):
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except ValueError:
        return False


def make_token(uid, kind, minutes):
    payload = {"sub": uid, "type": kind, "exp": now() + timedelta(minutes=minutes)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def public_user(u):
    return {k: u.get(k) for k in ("id", "email", "name", "role", "active", "created_at")}


async def current_user(request: Request):
    tok = request.cookies.get("access_token")
    auth = request.headers.get("Authorization", "")
    if not tok and auth.startswith("Bearer "):
        tok = auth[7:]
    if not tok:
        raise HTTPException(401, "Belum login")
    try:
        p = jwt.decode(tok, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sesi berakhir")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token tidak valid")
    if p.get("type") != "access":
        raise HTTPException(401, "Token tidak valid")
    u = await db.users.find_one({"id": p["sub"]}, {"_id": 0, "password_hash": 0})
    if not u or not u.get("active", True):
        raise HTTPException(401, "Akun tidak aktif")
    return u


def require(*roles):
    async def dep(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Anda tidak memiliki izin untuk tindakan ini")
        return user
    return dep


COST_KEYS = {"cost", "cost_total", "hpp"}


def strip_cost(obj, user):
    if user["role"] == "owner":
        return obj
    if isinstance(obj, list):
        return [strip_cost(x, user) for x in obj]
    if isinstance(obj, dict):
        return {k: strip_cost(v, user) for k, v in obj.items() if k not in COST_KEYS}
    return obj


async def audit(user, action, ref_type, ref_id=None, before=None, after=None, reason=None, session=None):
    await db.audit_logs.insert_one({
        "id": new_id(), "user_id": user["id"] if user else None,
        "user_name": user["name"] if user else "sistem", "role": user["role"] if user else None,
        "action": action, "ref_type": ref_type, "ref_id": ref_id,
        "before": before, "after": after, "reason": reason, "created_at": iso(),
    }, session=session)


async def next_number(prefix):
    d = now().astimezone(TZ).strftime("%y%m%d")
    c = await db.counters.find_one_and_update(
        {"key": f"{prefix}-{d}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return f"{prefix}-{d}-{c['seq']:03d}"


async def move_stock(item_id, delta, kind, reason, user, ref_type=None, ref_id=None, ref_no=None, session=None):
    if delta == 0:
        return None
    q = {"id": item_id}
    if delta < 0:
        q["stock"] = {"$gte": -delta}
    after = await db.items.find_one_and_update(q, {"$inc": {"stock": delta}}, return_document=ReturnDocument.AFTER, session=session)
    if not after:
        it = await db.items.find_one({"id": item_id}, session=session)
        if not it:
            raise HTTPException(404, "Barang tidak ditemukan")
        raise HTTPException(409, f"Stok {it['name']} tidak cukup (tersisa {it.get('stock', 0)} pcs, butuh {-delta})")
    await db.stock_mutations.insert_one({
        "id": new_id(), "item_id": item_id, "sku": after.get("sku"), "item_name": after.get("name"),
        "kind": kind, "qty_before": after["stock"] - delta, "qty_after": after["stock"], "delta": delta,
        "reason": reason, "ref_type": ref_type, "ref_id": ref_id, "ref_no": ref_no,
        "user_id": user["id"] if user else None, "user_name": user["name"] if user else "sistem",
        "created_at": iso(), "date_local": local_date(),
    }, session=session)
    return after


async def move_many(pairs, kind, reason, user, ref_type=None, ref_id=None, ref_no=None):
    agg = {}
    for item_id, delta in pairs:
        if item_id:
            agg[item_id] = agg.get(item_id, 0) + delta
    done = []
    try:
        for item_id, delta in agg.items():
            await move_stock(item_id, delta, kind, reason, user, ref_type, ref_id, ref_no)
            done.append((item_id, delta))
    except HTTPException:
        for item_id, delta in done:
            await move_stock(item_id, -delta, "pembatalan_otomatis", f"Batal otomatis: {reason}", user, ref_type, ref_id, ref_no)
        raise
    return done


async def add_payment(ref_type, doc, amount, method, kind, user, idem_key=None, note=None, direction="in", purpose=None):
    if amount <= 0:
        raise HTTPException(400, "Jumlah harus lebih dari 0")
    if method not in ("tunai", "transfer", "cod"):
        raise HTTPException(400, "Metode pembayaran tidak valid")
    p = {
        "id": new_id(), "ref_type": ref_type, "ref_id": doc["id"], "ref_no": doc["no"],
        "amount": int(amount), "method": method, "kind": kind, "direction": direction, "note": note,
        "idem_key": idem_key or new_id(), "user_id": user["id"], "user_name": user["name"], "purpose": purpose,
        "created_at": iso(), "date_local": local_date(),
    }
    try:
        await db.payments.insert_one(p)
    except DuplicateKeyError:
        return None
    await recompute_paid(ref_type, doc["id"])
    return clean(p)


COLL = {"job": "jobs", "sale": "sales", "order": "orders"}


async def recompute_paid(ref_type, ref_id):
    rows = await find_list("payments", {"ref_type": ref_type, "ref_id": ref_id})
    paid = sum(r["amount"] for r in rows if r["direction"] == "in")
    refunded = sum(r["amount"] for r in rows if r["direction"] == "out")
    upd = {"paid": paid, "refunded": refunded}
    if ref_type == "order":
        upd["ship_paid"] = sum(r["amount"] for r in rows if r["direction"] == "in" and r.get("purpose") == "ongkir")
        upd["goods_paid"] = paid - upd["ship_paid"]
    await db[COLL[ref_type]].update_one({"id": ref_id}, {"$set": upd})
    return paid, refunded


async def record_damage(item_id, name, qty, source, reason, user, affects_stock, ref_type=None, ref_id=None, ref_no=None, condition=None):
    if affects_stock:
        await move_stock(item_id, -qty, "rusak", reason, user, ref_type, ref_id, ref_no)
    d = {
        "id": new_id(), "item_id": item_id, "item_name": name, "qty": qty, "source": source,
        "affects_stock": affects_stock, "reason": reason, "condition": condition,
        "ref_type": ref_type, "ref_id": ref_id, "ref_no": ref_no,
        "user_id": user["id"], "user_name": user["name"], "created_at": iso(), "date_local": local_date(),
    }
    await db.damaged.insert_one(d)
    return clean(d)
