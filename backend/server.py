import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from pymongo import ASCENDING, DESCENDING, IndexModel
from core import db, client, new_id, hash_pw, iso
import auth_routes
import cms_routes
import master_routes
import tx_routes
import report_routes
import wa_routes
import catalog_routes
import reset_routes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("predator")

app = FastAPI(title="Predator Autolight API", docs_url=None if os.environ.get("DISABLE_DOCS") == "true" else "/api/docs",
              openapi_url="/api/openapi.json")
for r in (auth_routes, cms_routes, master_routes, tx_routes, report_routes, wa_routes, catalog_routes, reset_routes):
    app.include_router(r.router)

ORIGINS = [o.strip() for o in os.environ["CORS_ORIGINS"].split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and origin and "*" not in ORIGINS and origin not in ORIGINS:
        return JSONResponse({"detail": "Origin tidak diizinkan"}, status_code=403)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp


INDEXES = {
    "users": [IndexModel([("email", ASCENDING)], unique=True), IndexModel([("id", ASCENDING)], unique=True)],
    "login_attempts": [IndexModel([("identifier", ASCENDING)])],
    "cms": [IndexModel([("key", ASCENDING)], unique=True)],
    "cms_revisions": [IndexModel([("key", ASCENDING), ("created_at", DESCENDING)])],
    "media": [IndexModel([("id", ASCENDING)], unique=True)],
    "items": [IndexModel([("id", ASCENDING)], unique=True), IndexModel([("sku", ASCENDING)], unique=True)],
    "packages": [IndexModel([("id", ASCENDING)], unique=True)],
    "customers": [IndexModel([("id", ASCENDING)], unique=True), IndexModel([("phone", ASCENDING)])],
    "vehicles": [IndexModel([("id", ASCENDING)], unique=True), IndexModel([("plate", ASCENDING)], unique=True)],
    "jobs": [IndexModel([("id", ASCENDING)], unique=True), IndexModel([("status", ASCENDING)]), IndexModel([("vehicle_id", ASCENDING)]),
             IndexModel([("recognized_date", ASCENDING)]), IndexModel([("public_token", ASCENDING)]), IndexModel([("claim.ref_id", ASCENDING)])],
    "sales": [IndexModel([("id", ASCENDING)], unique=True), IndexModel([("idem_key", ASCENDING)], unique=True),
              IndexModel([("recognized_date", ASCENDING)]), IndexModel([("public_token", ASCENDING)])],
    "orders": [IndexModel([("id", ASCENDING)], unique=True), IndexModel([("recognized_date", ASCENDING)]),
               IndexModel([("public_token", ASCENDING)])],
    "payments": [IndexModel([("idem_key", ASCENDING)], unique=True), IndexModel([("ref_id", ASCENDING)]),
                 IndexModel([("date_local", ASCENDING)])],
    "stock_mutations": [IndexModel([("item_id", ASCENDING), ("created_at", DESCENDING)]), IndexModel([("date_local", ASCENDING)])],
    "damaged": [IndexModel([("date_local", ASCENDING)])],
    "expenses": [IndexModel([("date", ASCENDING)])],
    "audit_logs": [IndexModel([("created_at", DESCENDING)])],
    "counters": [IndexModel([("key", ASCENDING)], unique=True)],
    "products": [IndexModel([("id", ASCENDING)], unique=True), IndexModel([("code", ASCENDING)], unique=True)],
    "settings": [IndexModel([("key", ASCENDING)], unique=True)],
    "wa_logs": [IndexModel([("send_key", ASCENDING)], unique=True), IndexModel([("ref_id", ASCENDING)]),
                IndexModel([("created_at", DESCENDING)])],
    "wa_locks": [IndexModel([("key", ASCENDING)], unique=True)],
}


@app.on_event("startup")
async def startup():
    for coll, models in INDEXES.items():
        try:
            await db[coll].create_indexes(models)
        except Exception as e:
            log.error("index %s: %s", coll, e)
    await cms_routes.ensure_cms()
    n = await catalog_routes.migrate_products()
    if n:
        log.info("Migrasi: %s barang lama dipetakan ke produk induk + varian", n)
    # Pesanan COD model lama (COD harga barang) ditandai eksplisit sebagai data lama; tidak ditafsir ulang sebagai COD ongkir.
    m = await tx_routes.migrate_legacy_orders()
    if m:
        log.info("Migrasi: %s pesanan COD lama ditandai legacy_cod", m)
    email, pw = os.environ.get("OWNER_EMAIL"), os.environ.get("OWNER_PASSWORD")
    if email and pw and await db.users.count_documents({}) == 0:
        await db.users.insert_one({"id": new_id(), "email": email.lower(), "name": os.environ.get("OWNER_NAME", "Owner"), "role": "owner",
                                   "active": True, "password_hash": hash_pw(pw), "created_at": iso()})
        log.info("Akun owner pertama dibuat untuk %s", email)


@app.get("/api/health")
async def health():
    await db.command("ping")
    return {"ok": True}


@app.on_event("shutdown")
async def shutdown():
    client.close()
