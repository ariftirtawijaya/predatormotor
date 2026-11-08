import os
import re
import base64
import hashlib
import logging
from datetime import datetime, timedelta
import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError
from core import db, iso, now, new_id, require, audit, find_list, get_or_404, clean, COLL, STAFF, TZ, JWT_SECRET
from cms_routes import publish_key

router = APIRouter(prefix="/api")
log = logging.getLogger("predator.wa")
FONNTE_URL = "https://api.fonnte.com/send"
# Token Fonnte dienkripsi dengan kunci turunan JWT_SECRET; jika JWT_SECRET diganti, token wajib diisi ulang.
FERNET = Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"predator-fonnte-token:" + JWT_SECRET.encode()).digest()))
ORIGINS = [o.strip().rstrip("/") for o in os.environ["CORS_ORIGINS"].split(",") if o.strip()]
KIND_LABEL = {"job": "Pekerjaan Bengkel", "sale": "Penjualan Langsung", "order": "Pesanan WhatsApp"}
ACTIVE = ("mengirim", "antre", "tidak_pasti")
LOCK_TTL = 60
TAG = re.compile(r"<[^>]*>")


def normalize_wa(raw):
    s = re.sub(r"[\s\-().]", "", raw or "")
    if s.startswith("+"):
        s = s[1:]
    if not s.isdigit():
        raise HTTPException(400, "Nomor WhatsApp hanya boleh berisi angka (format 08…, 62…, atau +62…)")
    if s.startswith("0"):
        s = "62" + s[1:]
    if not re.fullmatch(r"628\d{7,11}", s):
        raise HTTPException(400, "Nomor WhatsApp Indonesia tidak valid. Gunakan format 08…, 62…, atau +62…")
    return s


def rp(n):
    return "Rp" + f"{int(n or 0):,}".replace(",", ".")


def fmt_dt(s):
    if not s:
        return "-"
    if len(s) == 10:
        return datetime.fromisoformat(s).strftime("%d/%m/%Y")
    return datetime.fromisoformat(s).astimezone(TZ).strftime("%d/%m/%Y %H:%M") + " WIB"


def safe_reason(v, tok=""):
    s = TAG.sub("", str(v or ""))[:200].strip()
    return s.replace(tok, "***") if tok else s


# ---------- Pengaturan tersimpan ----------
async def settings_doc():
    return await db.settings.find_one({"key": "fonnte"}, {"_id": 0}) or {}


async def get_token():
    d = await settings_doc()
    if not d.get("token_enc"):
        raise HTTPException(409, "Token Fonnte belum diatur. Owner perlu mengisinya di Pengaturan → WhatsApp.")
    try:
        return FERNET.decrypt(d["token_enc"].encode()).decode()
    except InvalidToken:
        raise HTTPException(409, "Token Fonnte tersimpan tidak dapat dibaca (kunci server berubah). Owner perlu mengisi ulang token.")


async def contact():
    return await db.cms.find_one({"key": "contact"}, {"_id": 0})


def without_wa(d):
    return {k: v for k, v in (d or {}).items() if k != "whatsapp"}


async def settings_view():
    d, c = await settings_doc(), await contact()
    readable = True
    if d.get("token_enc"):
        try:
            FERNET.decrypt(d["token_enc"].encode())
        except InvalidToken:
            readable = False
    draft, pub = c["draft"].get("whatsapp", ""), c["published"].get("whatsapp", "")
    return {"token": {"configured": bool(d.get("token_enc")), "readable": readable,
                      "masked": f"••••••••{d['token_last4']}" if d.get("token_enc") else "",
                      "updated_at": d.get("token_updated_at"), "updated_by": d.get("token_updated_by")},
            "admin_number": draft, "published_number": pub, "pending_publish": draft != pub,
            "contact_other_changes": without_wa(c["draft"]) != without_wa(c["published"])}


class TokenIn(BaseModel):
    token: str = Field(min_length=8, max_length=200)


class NumberIn(BaseModel):
    number: str = Field(max_length=30)


class SendKeyIn(BaseModel):
    send_key: str = Field(min_length=8, max_length=80)


@router.get("/settings/whatsapp")
async def get_settings(user=Depends(require("owner"))):
    return await settings_view()


@router.put("/settings/whatsapp/token")
async def save_token(body: TokenIn, user=Depends(require("owner"))):
    tok = body.token.strip()
    if re.search(r"\s", tok):
        raise HTTPException(400, "Token tidak boleh mengandung spasi")
    await db.settings.update_one({"key": "fonnte"}, {"$set": {
        "key": "fonnte", "token_enc": FERNET.encrypt(tok.encode()).decode(), "token_last4": tok[-4:],
        "token_updated_at": iso(), "token_updated_by": user["name"]}}, upsert=True)
    await audit(user, "ubah_token_fonnte", "settings", "fonnte")
    return await settings_view()


@router.delete("/settings/whatsapp/token")
async def delete_token(user=Depends(require("owner"))):
    await db.settings.update_one({"key": "fonnte"}, {"$set": {"token_enc": "", "token_last4": "", "token_updated_at": iso(),
                                                              "token_updated_by": user["name"]}})
    await audit(user, "hapus_token_fonnte", "settings", "fonnte")
    return await settings_view()


@router.put("/settings/whatsapp/number")
async def save_number(body: NumberIn, user=Depends(require("owner"))):
    num = normalize_wa(body.number) if body.number.strip() else ""
    c = await contact()
    old = c["draft"].get("whatsapp", "")
    draft = {**c["draft"], "whatsapp": num}
    await db.cms.update_one({"key": "contact"}, {"$set": {"draft": draft, "updated_at": iso(), "updated_by": user["name"]}})
    await db.cms_revisions.insert_one({"id": new_id(), "key": "contact", "kind": "draft", "data": draft,
                                       "user_name": user["name"], "user_id": user["id"], "created_at": iso()})
    await audit(user, "ubah_nomor_wa_admin", "settings", "contact", before={"whatsapp": old}, after={"whatsapp": num})
    return await settings_view()


@router.post("/settings/whatsapp/publish-number")
async def publish_number(user=Depends(require("owner"))):
    await publish_key("contact", user)
    return await settings_view()


# ---------- Pengiriman ke Fonnte ----------
async def fonnte_send(tok, target, message):
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            r = await client.post(FONNTE_URL, headers={"Authorization": tok}, data={
                "target": target, "message": message, "countryCode": "0", "connectOnly": "true", "preview": "false"})
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return {"status": "gagal", "reason": "Tidak dapat terhubung ke server Fonnte. Pesan belum terkirim."}
    except httpx.HTTPError as e:
        log.warning("Fonnte tidak merespons dengan benar: %s", type(e).__name__)
        return {"status": "tidak_pasti", "reason": "Fonnte tidak memberi respons (timeout/koneksi terputus). Pesan mungkin sudah masuk antrean — cek dashboard Fonnte sebelum mengirim ulang."}
    if r.status_code >= 500:
        return {"status": "tidak_pasti", "reason": f"Server Fonnte error (HTTP {r.status_code}). Cek dashboard Fonnte sebelum mengirim ulang."}
    try:
        data = r.json()
    except ValueError:
        return {"status": "gagal" if r.status_code >= 400 else "tidak_pasti", "reason": f"Respons Fonnte tidak dapat dibaca (HTTP {r.status_code})."}
    accepted = data.get("status", data.get("Status")) is True
    ids = data.get("id") or []
    return {"status": "antre" if accepted else "ditolak", "request_id": data.get("requestid"),
            "message_ids": [str(x) for x in (ids if isinstance(ids, list) else [ids])],
            "detail": safe_reason(data.get("detail"), tok) if accepted else None,
            "reason": None if accepted else (safe_reason(data.get("reason") or data.get("detail"), tok) or "Ditolak Fonnte")}


async def take_lock(key):
    await db.wa_locks.delete_many({"key": key, "created_at": {"$lt": (now() - timedelta(seconds=LOCK_TTL)).isoformat()}})
    try:
        await db.wa_locks.insert_one({"key": key, "created_at": iso()})
    except DuplicateKeyError:
        raise HTTPException(409, "Pesan untuk transaksi ini sedang dikirim. Tunggu sebentar lalu muat ulang riwayat.")


async def deliver(entry, tok, message):
    """Satu kali panggilan Fonnte tanpa kirim ulang otomatis; hasil dicatat di wa_logs."""
    try:
        await db.wa_logs.insert_one(dict(entry, status="mengirim"))
    except DuplicateKeyError:
        return {**clean(await db.wa_logs.find_one({"send_key": entry["send_key"]})), "duplicate": True}
    res = await fonnte_send(tok, entry["target"], message)
    res["finished_at"] = iso()
    await db.wa_logs.update_one({"id": entry["id"]}, {"$set": res})
    return clean(await db.wa_logs.find_one({"id": entry["id"]}))


def base_entry(user, kind, send_key, target, **kw):
    return {"id": new_id(), "kind": kind, "send_key": send_key, "target": target, "user_id": user["id"],
            "user_name": user["name"], "role": user["role"], "created_at": iso(), "request_id": None,
            "message_ids": [], "reason": None, "detail": None, "resend": False, "resend_reason": None,
            "ref_type": None, "ref_id": None, "ref_no": None} | kw


async def shop_name():
    d = await db.cms.find_one({"key": "identity"}, {"_id": 0, "published": 1})
    return (d or {}).get("published", {}).get("name") or "Predator Autolight"


@router.post("/settings/whatsapp/test")
async def send_test(body: SendKeyIn, user=Depends(require("owner"))):
    ex = await db.wa_logs.find_one({"send_key": body.send_key}, {"_id": 0})
    if ex:
        return ex | {"duplicate": True}
    c = await contact()
    target = c["draft"].get("whatsapp", "")
    if not target:
        raise HTTPException(400, "Isi dan simpan nomor WhatsApp admin terlebih dahulu")
    tok = await get_token()
    msg = (f"Pesan percobaan dari sistem {await shop_name()}.\nDikirim oleh {user['name']} pada {fmt_dt(iso())}.\n"
           "Jika pesan ini masuk, integrasi Fonnte sudah berfungsi.")
    await take_lock("test")
    try:
        return await deliver(base_entry(user, "test", body.send_key, target), tok, msg)
    finally:
        await db.wa_locks.delete_one({"key": "test"})


# ---------- Nota ----------
def stored_phone(doc):
    return (doc.get("customer") or {}).get("phone") or doc.get("customer_phone") or ""


def line_text(i, l):
    out = [f"{i}. {l['name']}" + (f" ({l['detail']})" if l.get("detail") else "")]
    if l.get("options"):
        out.append("   Termasuk: " + ", ".join(o["name"] for o in l["options"]))
    out.append(f"   {l['qty']} x {rp(l['unit_price'])} = {rp(l['subtotal'])}")
    if l.get("warranty_replacement"):
        out.append("   (Pengganti garansi)")
    if l.get("warranty_until"):
        out.append(f"   Garansi s/d {fmt_dt(l['warranty_until'])}")
    return out


async def nota_message(kind, doc, origin):
    pays = await find_list("payments", {"ref_type": kind, "ref_id": doc["id"]}, [("created_at", 1)])
    status = doc.get("ship_status") if kind == "order" else doc.get("status")
    cancelled = status == "Batal"
    name = (doc.get("customer") or {}).get("name") or doc.get("customer_name") or ""
    veh = doc.get("vehicle") or {}
    rows = [f"*{await shop_name()}*", f"Nota {KIND_LABEL[kind]}: *{doc['no']}*", f"Tanggal: {fmt_dt(doc['created_at'])}"]
    if name:
        rows.append(f"Pelanggan: {name}")
    if veh.get("plate"):
        rows.append("Kendaraan: " + " ".join(x for x in (veh.get("plate"), veh.get("brand"), veh.get("model")) if x))
    if kind != "sale" and status:
        rows.append(f"Status: {'DIBATALKAN' if cancelled else status}")
    rows += ["", "Rincian:"]
    for i, l in enumerate([l for l in doc.get("lines", []) if not l.get("removed")], 1):
        rows += line_text(i, l)
    rows += ["", f"Subtotal: {rp(doc['subtotal'])}"]
    if doc.get("discount_amount"):
        rows.append(f"Diskon: -{rp(doc['discount_amount'])}")
    if doc.get("shipping_cost"):
        rows.append(f"Ongkir: {rp(doc['shipping_cost'])}")
    rows.append(f"*Total: {rp(doc['total'])}*")
    ins = [p for p in pays if p["direction"] == "in"]
    if ins:
        rows += ["", "Pembayaran:"] + [f"- {fmt_dt(p['created_at'])} · {p['kind']} · {p['method']}: {rp(p['amount'])}" for p in ins]
    rows.append(f"Total dibayar: {rp(doc['paid'])}")
    if doc.get("refunded"):
        rows.append(f"Dikembalikan: {rp(doc['refunded'])}")
    if not cancelled:
        rem = max(doc["total"] - doc["paid"], 0)
        rows.append(f"*Sisa tagihan: {rp(rem)}*" if rem else "*Status pembayaran: LUNAS*")
    if kind == "order" and doc.get("payment_type") == "cod" and not cancelled:
        rows.append("Pembayaran: COD (bayar di tempat)")
    if origin and doc.get("public_token"):
        rows += ["", f"Lihat nota: {origin}/nota/{doc['public_token']}"]
    rows += ["", "Terima kasih."]
    return "\n".join(rows)


def req_origin(request: Request):
    o = (request.headers.get("origin") or "").rstrip("/")
    return o if o and ("*" in ORIGINS or o in ORIGINS) else ""


def check_kind(kind):
    if kind not in COLL:
        raise HTTPException(404, "Jenis transaksi tidak dikenal")


@router.get("/wa/nota/{kind}/{tid}")
async def nota_preview(kind: str, tid: str, request: Request, user=Depends(require(*STAFF))):
    check_kind(kind)
    doc = await get_or_404(COLL[kind], tid, "Transaksi tidak ditemukan")
    phone = stored_phone(doc)
    d = await settings_doc()
    return {"target": phone, "target_editable": kind == "sale" and not phone, "message": await nota_message(kind, doc, req_origin(request)),
            "token_configured": bool(d.get("token_enc")),
            "logs": await find_list("wa_logs", {"ref_type": kind, "ref_id": tid}, [("created_at", -1)], 50)}


class NotaSendIn(SendKeyIn):
    target: str = Field(default="", max_length=30)
    resend: bool = False
    resend_reason: str = Field(default="", max_length=200)


@router.post("/wa/nota/{kind}/{tid}")
async def nota_send(kind: str, tid: str, body: NotaSendIn, request: Request, user=Depends(require(*STAFF))):
    check_kind(kind)
    ex = await db.wa_logs.find_one({"send_key": body.send_key}, {"_id": 0})
    if ex:
        return ex | {"duplicate": True}
    doc = await get_or_404(COLL[kind], tid, "Transaksi tidak ditemukan")
    phone = stored_phone(doc)
    if not phone and kind != "sale":
        raise HTTPException(400, "Transaksi ini tidak menyimpan nomor WhatsApp pelanggan")
    if not phone and not body.target.strip():
        raise HTTPException(400, "Masukkan nomor WhatsApp penerima nota")
    target = normalize_wa(phone or body.target)
    if body.resend and len(body.resend_reason.strip()) < 3:
        raise HTTPException(400, "Tuliskan alasan kirim ulang (minimal 3 huruf)")
    tok = await get_token()
    lock = f"nota:{kind}:{tid}"
    await take_lock(lock)
    try:
        prior = await db.wa_logs.find_one({"ref_type": kind, "ref_id": tid, "status": {"$in": list(ACTIVE)}}, {"_id": 0})
        if prior and not body.resend:
            raise HTTPException(409, "Nota ini sudah pernah dikirim. Gunakan tombol Kirim Ulang jika memang perlu mengirim lagi.")
        entry = base_entry(user, "nota", body.send_key, target, ref_type=kind, ref_id=tid, ref_no=doc["no"],
                           resend=bool(prior) and body.resend, resend_reason=body.resend_reason.strip() or None)
        return await deliver(entry, tok, await nota_message(kind, doc, req_origin(request)))
    finally:
        await db.wa_locks.delete_one({"key": lock})


@router.get("/wa/logs")
async def wa_logs(ref_id: str | None = None, user=Depends(require("owner"))):
    return await find_list("wa_logs", {"ref_id": ref_id} if ref_id else {}, [("created_at", -1)], 300)
