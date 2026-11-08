from datetime import timedelta
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel, Field
import jwt
from core import (db, now, iso, new_id, hash_pw, verify_pw, make_token, public_user, current_user,
                  require, audit, find_list, JWT_SECRET, COOKIE_SECURE, COOKIE_SAMESITE, ROLES)

router = APIRouter(prefix="/api")
ACCESS_MIN = 30
REFRESH_MIN = 60 * 24 * 7


class LoginIn(BaseModel):
    email: str
    password: str


class UserIn(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=80)
    role: str
    password: str = Field(min_length=8, max_length=128)


class UserPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class PwIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


def set_cookies(resp, uid):
    opts = dict(httponly=True, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, path="/")
    resp.set_cookie("access_token", make_token(uid, "access", ACCESS_MIN), max_age=ACCESS_MIN * 60, **opts)
    resp.set_cookie("refresh_token", make_token(uid, "refresh", REFRESH_MIN), max_age=REFRESH_MIN * 60, **opts)


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.strip().lower()
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    ident = f"{ip}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("count", 0) >= 5 and att.get("until") and att["until"] > iso():
        raise HTTPException(429, "Terlalu banyak percobaan gagal. Coba lagi 15 menit lagi.")
    u = await db.users.find_one({"email": email})
    if not u or not verify_pw(body.password, u["password_hash"]) or not u.get("active", True):
        cnt = (att or {}).get("count", 0) + 1
        if att and att.get("until") and att["until"] <= iso() and att.get("count", 0) >= 5:
            cnt = 1
        await db.login_attempts.update_one(
            {"identifier": ident},
            {"$set": {"count": cnt, "until": (now() + timedelta(minutes=15)).isoformat()}}, upsert=True)
        raise HTTPException(401, "Email atau password salah")
    await db.login_attempts.delete_many({"identifier": ident})
    set_cookies(response, u["id"])
    return public_user(u)


@router.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    tok = request.cookies.get("refresh_token")
    if not tok:
        raise HTTPException(401, "Belum login")
    try:
        p = jwt.decode(tok, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Sesi berakhir")
    if p.get("type") != "refresh":
        raise HTTPException(401, "Token tidak valid")
    u = await db.users.find_one({"id": p["sub"]})
    if not u or not u.get("active", True):
        raise HTTPException(401, "Akun tidak aktif")
    set_cookies(response, u["id"])
    return public_user(u)


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/auth/me")
async def me(user=Depends(current_user)):
    return public_user(user)


@router.post("/auth/change-password")
async def change_password(body: PwIn, user=Depends(current_user)):
    u = await db.users.find_one({"id": user["id"]})
    if not verify_pw(body.old_password, u["password_hash"]):
        raise HTTPException(400, "Password lama salah")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_pw(body.new_password)}})
    await audit(user, "ganti_password", "user", user["id"])
    return {"ok": True}


@router.get("/users")
async def list_users(user=Depends(require("owner"))):
    return [public_user(u) for u in await find_list("users", {}, [("created_at", 1)])]


@router.post("/users")
async def create_user(body: UserIn, user=Depends(require("owner"))):
    if body.role not in ROLES:
        raise HTTPException(400, "Peran tidak valid")
    email = body.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email sudah dipakai")
    u = {"id": new_id(), "email": email, "name": body.name.strip(), "role": body.role, "active": True,
         "password_hash": hash_pw(body.password), "created_at": iso()}
    await db.users.insert_one(u)
    await audit(user, "buat_pengguna", "user", u["id"], after=public_user(u))
    return public_user(u)


@router.patch("/users/{uid}")
async def update_user(uid: str, body: UserPatch, user=Depends(require("owner"))):
    u = await db.users.find_one({"id": uid}, {"_id": 0})
    if not u:
        raise HTTPException(404, "Pengguna tidak ditemukan")
    upd = {}
    if body.name:
        upd["name"] = body.name.strip()
    if body.role:
        if body.role not in ROLES:
            raise HTTPException(400, "Peran tidak valid")
        upd["role"] = body.role
    if body.active is not None:
        upd["active"] = body.active
    if body.password:
        upd["password_hash"] = hash_pw(body.password)
    if uid == user["id"] and (upd.get("role", "owner") != "owner" or upd.get("active") is False):
        raise HTTPException(400, "Tidak dapat menurunkan atau menonaktifkan akun sendiri")
    await db.users.update_one({"id": uid}, {"$set": upd})
    await audit(user, "ubah_pengguna", "user", uid, before=public_user(u),
                after={k: v for k, v in upd.items() if k != "password_hash"} | ({"password": "diubah"} if body.password else {}))
    return {"ok": True}


@router.get("/audit")
async def list_audit(ref_type: str | None = None, limit: int = 300, user=Depends(require("owner"))):
    q = {"ref_type": ref_type} if ref_type else {}
    return await find_list("audit_logs", q, [("created_at", -1)], min(limit, 2000))
