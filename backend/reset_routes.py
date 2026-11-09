import shutil
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from core import db, iso, new_id, require, verify_pw, UPLOAD_DIR
from cms_routes import DEFAULTS, KEYS

router = APIRouter(prefix="/api")
CONFIRM_TEXT = "RESET SEMUA DATA"
# Semua data bisnis + data turunan. Struktur (indeks) dipertahankan; CMS diisi ulang dengan struktur kosong.
WIPE = ["customers", "vehicles", "products", "items", "packages", "stock_mutations", "jobs", "sales", "orders", "payments",
        "damaged", "expenses", "wa_logs", "wa_locks", "cms_revisions", "media", "counters", "audit_logs", "login_attempts", "migrations",
        "deleted_records", "locks"]
LABELS = {"customers": "Pelanggan", "vehicles": "Kendaraan", "products": "Produk induk", "items": "Varian barang", "packages": "Paket",
          "stock_mutations": "Mutasi stok", "jobs": "Pekerjaan bengkel", "sales": "Penjualan langsung", "orders": "Pesanan WhatsApp",
          "payments": "Pembayaran & refund", "damaged": "Barang rusak", "expenses": "Biaya", "wa_logs": "Riwayat kirim WA",
          "cms_revisions": "Revisi CMS", "media": "Media unggahan", "audit_logs": "Audit log", "deleted_records": "Arsip data terhapus",
          "users": "Akun lain (admin/kasir/owner lain)"}


def upload_files():
    return [p for sub in ("public", "private") for p in (UPLOAD_DIR / sub).glob("**/*") if p.is_file()]


async def counts(owner_id):
    out = {k: await db[k].count_documents({}) for k in WIPE}
    out["users"] = await db.users.count_documents({"id": {"$ne": owner_id}})
    out["upload_files"] = len(upload_files())
    s = await db.settings.find_one({"key": "fonnte"}) or {}
    out["fonnte_token"] = int(bool(s.get("token_enc")))
    return out


@router.get("/admin/reset/summary")
async def reset_summary(user=Depends(require("owner"))):
    c = await counts(user["id"])
    others = await db.users.find({"id": {"$ne": user["id"]}}, {"_id": 0, "email": 1, "role": 1, "name": 1}).to_list(500)
    return {"counts": c, "labels": LABELS, "other_users": others, "confirm_text": CONFIRM_TEXT,
            "keep": {"email": user["email"], "name": user["name"]}}


class ResetIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    confirm_text: str
    backup_done: bool


async def verify_clean(owner_id):
    c = await counts(owner_id)
    issues = [f"{LABELS.get(k, k)} masih {v}" for k, v in c.items() if v and k not in ("audit_logs", "locks")]
    if await db.users.count_documents({}) != 1:
        issues.append("Jumlah akun bukan 1")
    cms = await db.cms.find({}, {"_id": 0}).to_list(50)
    if sorted(d["key"] for d in cms) != sorted(KEYS):
        issues.append("Struktur CMS tidak lengkap")
    if any("[TEST]" in str(d) or "[CONTOH]" in str(d) for d in cms):
        issues.append("Masih ada konten contoh di CMS")
    if any(d["key"] == "contact" and (d["draft"].get("whatsapp") or d["published"].get("whatsapp")) for d in cms):
        issues.append("Nomor WhatsApp admin masih terisi")
    return {"ok": not issues, "issues": issues, "counts_after": c}


@router.post("/admin/reset")
async def reset_all(body: ResetIn, user=Depends(require("owner"))):
    me = await db.users.find_one({"id": user["id"]})
    if not verify_pw(body.password, me["password_hash"]):
        raise HTTPException(403, "Password owner salah")
    if body.confirm_text.strip() != CONFIRM_TEXT:
        raise HTTPException(400, f"Ketik persis: {CONFIRM_TEXT}")
    if not body.backup_done:
        raise HTTPException(400, "Centang konfirmasi bahwa backup sudah dibuat")
    before = await counts(user["id"])
    await db.users.delete_many({"id": {"$ne": user["id"]}})
    for k in WIPE:
        await db[k].delete_many({})
    await db.settings.delete_many({})
    await db.cms.delete_many({})
    stamp = iso()
    for k in KEYS:
        await db.cms.insert_one({"key": k, "draft": DEFAULTS[k], "published": DEFAULTS[k], "version": 1, "updated_at": stamp,
                                 "updated_by": user["name"], "published_at": stamp, "published_by": user["name"]})
    for sub in ("public", "private"):
        shutil.rmtree(UPLOAD_DIR / sub, ignore_errors=True)
        (UPLOAD_DIR / sub).mkdir(parents=True, exist_ok=True)
    check = await verify_clean(user["id"])
    await db.audit_logs.insert_one({"id": new_id(), "user_id": user["id"], "user_name": user["name"], "role": "owner",
                                    "action": "reset_seluruh_data", "ref_type": "system", "ref_id": None, "before": before,
                                    "after": {"ok": check["ok"]}, "reason": "Reset data uji dari panel", "created_at": iso()})
    return {"deleted": before, "verification": check}
