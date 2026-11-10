import re
import io
import os
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from PIL import Image, ImageOps
from core import (db, iso, new_id, find_list, require, audit, current_user, clean, UPLOAD_DIR, MANAGERS, STAFF)

router = APIRouter(prefix="/api")
KEYS = ["identity", "navigation", "home", "profile", "services", "catalog", "gallery", "contact", "footer", "seo", "pages"]
MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "5"))
URL_RE = re.compile(r"(href|link|url|_image|^image|logo|favicon|photo)$", re.I)
SAFE_URL = re.compile(r"^(https?://|/(?![/\\])|#|mailto:|tel:)", re.I)
TAG = re.compile(r"<[^>]*>")

SECTIONS = [
    {"type": "hero", "enabled": True, "title": "Spesialis Lampu & Kelistrikan Kendaraan",
     "subtitle": "Pemasangan BiLED, LED, shroud, devil eye, dan aksesoris kelistrikan di Bojonegoro.",
     "image": "", "cta_label": "Konsultasi via WhatsApp", "cta_link": "#whatsapp", "cta2_label": "Lihat Paket", "cta2_link": "/layanan"},
    {"type": "features", "enabled": True, "title": "Kenapa memilih kami", "items": [
        {"title": "Pemasangan rapi", "desc": "Isi deskripsi keunggulan dari CMS.", "icon": "wrench"},
        {"title": "Garansi sesuai kebijakan", "desc": "Isi ketentuan garansi dari CMS.", "icon": "shield"},
        {"title": "Konsultasi gratis", "desc": "Tanyakan kebutuhan lampu kendaraan anda.", "icon": "message"}]},
    {"type": "stats", "enabled": False, "title": "", "items": []},
    {"type": "services", "enabled": True, "title": "Layanan Unggulan", "subtitle": ""},
    {"type": "packages", "enabled": True, "title": "Paket Unggulan", "subtitle": ""},
    {"type": "testimonials", "enabled": False, "title": "Kata Pelanggan", "items": []},
    {"type": "gallery", "enabled": True, "title": "Hasil Pekerjaan", "subtitle": ""},
    {"type": "faq", "enabled": True, "title": "Pertanyaan Umum", "items": [
        {"q": "Apakah bisa konsultasi dulu?", "a": "Bisa. Hubungi kami lewat WhatsApp untuk konsultasi."}]},
    {"type": "cta", "enabled": True, "title": "Siap upgrade lampu kendaraan?", "text": "Hubungi bengkel untuk konsultasi dan jadwal pemasangan.", "button_label": "Chat WhatsApp"},
]

DEFAULTS = {
    "identity": {"name": "Predator Autolight Bojonegoro", "logo": "", "favicon": "", "slogan": "Lampu & kelistrikan kendaraan",
                 "short_desc": "Bengkel pemasangan lampu dan aksesoris kelistrikan kendaraan di Bojonegoro.",
                 "accent_color": "#f59e0b", "default_image": ""},
    "navigation": {"items": [
        {"label": "Beranda", "href": "/", "enabled": True}, {"label": "Profil", "href": "/profil", "enabled": True},
        {"label": "Layanan & Paket", "href": "/layanan", "enabled": True}, {"label": "Katalog", "href": "/katalog", "enabled": True},
        {"label": "Galeri", "href": "/galeri", "enabled": True}, {"label": "Kontak", "href": "/kontak", "enabled": True}],
        "cta_label": "Chat WhatsApp", "cta_href": "#whatsapp"},
    "home": {"sections": SECTIONS},
    "profile": {"title": "Tentang Kami", "story": "", "image": "", "highlights": [], "team": []},
    "services": {"items": []},
    "catalog": {"categories": [], "products": []},
    "gallery": {"albums": [], "items": []},
    "contact": {"whatsapp": "", "wa_message": "Halo Predator Autolight, saya ingin konsultasi.", "address": "", "hours": [],
                "map_embed": "", "map_link": "", "phone": "", "email": "", "socials": []},
    "footer": {"text": "", "links": [], "copyright": "Predator Autolight Bojonegoro"},
    "seo": {"pages": [{"page": p, "title": "", "description": "", "og_image": "", "noindex": False}
                      for p in ("home", "profil", "layanan", "katalog", "galeri", "kontak")]},
    "pages": {"items": []},
}

DRAFT_EXTRA = {"services": {"items": [{
    "title": "[CONTOH] Paket BiLED + Shroud", "slug": "contoh-paket-biled", "description": "Contoh struktur paket. Ubah atau hapus sebelum diterbitkan.",
    "image": "", "price": 1500000, "price_text": "Harga contoh, belum resmi",
    "features": [{"text": "BiLED merek [isi merek]"}, {"text": "Shroud jenis [isi jenis]"}, {"text": "Jasa pemasangan"}],
    "addons": [{"name": "Shroud RGB", "price_text": "± Rp350.000 (contoh)"}], "featured": True, "visible": False}]}}


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:80]


def sanitize(v, key=""):
    if isinstance(v, dict):
        return {k: sanitize(x, k) for k, x in v.items() if isinstance(k, str) and len(k) < 40}
    if isinstance(v, list):
        if len(v) > 200:
            raise HTTPException(400, "Terlalu banyak item")
        return [sanitize(x, key) for x in v]
    if isinstance(v, str):
        v = TAG.sub("", v)[:6000].strip()
        if URL_RE.search(key) and v and not SAFE_URL.match(v):
            raise HTTPException(400, f"Tautan tidak aman/tidak valid: {v[:60]}")
        if key == "map_embed" and v and not v.startswith("https://"):
            raise HTTPException(400, "Tautan embed peta harus https://")
        if key == "slug":
            v = slugify(v)
        if key == "accent_color" and not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            raise HTTPException(400, "Warna harus format #RRGGBB")
        return v
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    raise HTTPException(400, "Format data tidak valid")


async def ensure_cms():
    for k in KEYS:
        if not await db.cms.find_one({"key": k}):
            draft = DRAFT_EXTRA.get(k, DEFAULTS[k])
            await db.cms.insert_one({"key": k, "draft": draft, "published": DEFAULTS[k], "version": 1,
                                     "updated_at": iso(), "updated_by": "sistem", "published_at": iso(), "published_by": "sistem"})


def meta(d):
    return {"key": d["key"], "draft": d["draft"], "published": d["published"], "version": d.get("version", 1),
            "updated_at": d.get("updated_at"), "updated_by": d.get("updated_by"),
            "published_at": d.get("published_at"), "published_by": d.get("published_by"),
            "has_changes": d["draft"] != d["published"]}


async def keep_wa(key, data):
    # Nomor WA admin hanya diubah lewat Pengaturan → WhatsApp (owner), agar hanya ada satu sumber nomor.
    if key == "contact":
        cur = await db.cms.find_one({"key": "contact"})
        data = {**data, "whatsapp": cur["draft"].get("whatsapp", "")}
    return data


class DraftIn(BaseModel):
    data: dict


@router.get("/cms")
async def cms_all(user=Depends(require(*MANAGERS))):
    return [meta(d) for d in await find_list("cms", {})]


@router.put("/cms/{key}")
async def cms_save(key: str, body: DraftIn, user=Depends(require(*MANAGERS))):
    if key not in KEYS:
        raise HTTPException(404, "Bagian tidak dikenal")
    data = await keep_wa(key, sanitize(body.data))
    await db.cms.update_one({"key": key}, {"$set": {"draft": data, "updated_at": iso(), "updated_by": user["name"]}})
    await db.cms_revisions.insert_one({"id": new_id(), "key": key, "kind": "draft", "data": data,
                                       "user_name": user["name"], "user_id": user["id"], "created_at": iso()})
    return meta(await db.cms.find_one({"key": key}))


async def publish_key(key, user):
    d = await db.cms.find_one({"key": key})
    if not d:
        raise HTTPException(404, "Bagian tidak dikenal")
    if d["draft"] == d["published"]:
        return False
    await db.cms_revisions.insert_one({"id": new_id(), "key": key, "kind": "publish", "data": d["draft"], "previous": d["published"],
                                       "user_name": user["name"], "user_id": user["id"], "created_at": iso()})
    await db.cms.update_one({"key": key}, {"$set": {"published": d["draft"], "published_at": iso(), "published_by": user["name"]},
                                           "$inc": {"version": 1}})
    await audit(user, "terbitkan_cms", "cms", key)
    return True


@router.post("/cms/{key}/publish")
async def cms_publish(key: str, user=Depends(require(*MANAGERS))):
    await publish_key(key, user)
    return meta(await db.cms.find_one({"key": key}))


@router.post("/cms-publish-all")
async def cms_publish_all(user=Depends(require(*MANAGERS))):
    done = [k for k in KEYS if await publish_key(k, user)]
    return {"published": done}


@router.post("/cms/{key}/discard")
async def cms_discard(key: str, user=Depends(require(*MANAGERS))):
    d = await db.cms.find_one({"key": key})
    await db.cms.update_one({"key": key}, {"$set": {"draft": d["published"], "updated_at": iso(), "updated_by": user["name"]}})
    return meta(await db.cms.find_one({"key": key}))


@router.get("/cms/{key}/revisions")
async def cms_revisions(key: str, user=Depends(require(*MANAGERS))):
    return await find_list("cms_revisions", {"key": key}, [("created_at", -1)], 50)


@router.post("/cms-revisions/{rid}/restore")
async def cms_restore(rid: str, user=Depends(require(*MANAGERS))):
    r = await db.cms_revisions.find_one({"id": rid})
    if not r:
        raise HTTPException(404, "Revisi tidak ditemukan")
    await db.cms.update_one({"key": r["key"]}, {"$set": {"draft": await keep_wa(r["key"], r["data"]), "updated_at": iso(), "updated_by": user["name"]}})
    await audit(user, "pulihkan_revisi_cms", "cms", r["key"], reason=f"revisi {r['created_at']}")
    return meta(await db.cms.find_one({"key": r["key"]}))


def public_filter(site):
    s = dict(site)
    s["services"] = {"items": [i for i in site["services"].get("items", []) if i.get("visible")]}
    cat = site["catalog"]
    s["catalog"] = {"categories": cat.get("categories", []), "products": [p for p in cat.get("products", []) if p.get("visible")]}
    gal = site["gallery"]
    s["gallery"] = {"albums": gal.get("albums", []), "items": [g for g in gal.get("items", [])
                                                              if g.get("visible") and g.get("consent") and g.get("plate_masked")]}
    s["pages"] = {"items": [p for p in site["pages"].get("items", []) if p.get("visible")]}
    for p in s["catalog"]["products"]:
        p.pop("item_ref", None)
    return s


@router.get("/public/site")
async def public_site(request: Request, preview: bool = False):
    field = "published"
    if preview:
        user = await current_user(request)
        if user["role"] not in MANAGERS:
            raise HTTPException(403, "Pratinjau hanya untuk admin/owner")
        field = "draft"
    docs = await find_list("cms", {})
    site = {d["key"]: d[field] for d in docs}
    out = public_filter(site)
    out["preview"] = preview
    return out


# ---------- Media ----------
FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "ICO": "ico"}


@router.post("/media")
async def upload_media(file: UploadFile = File(...), alt: str = Form(""), private: bool = Form(False), user=Depends(require(*STAFF))):
    if user["role"] == "kasir" and not private:
        raise HTTPException(403, "Kasir hanya boleh mengunggah foto internal")
    raw = await file.read(MAX_MB * 1024 * 1024 + 1)
    if len(raw) > MAX_MB * 1024 * 1024:
        raise HTTPException(400, f"Ukuran file maksimal {MAX_MB} MB")
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        img = Image.open(io.BytesIO(raw))
        fmt = img.format
    except Exception:
        raise HTTPException(400, "File bukan gambar yang valid")
    if fmt not in FORMATS:
        raise HTTPException(400, "Format harus JPG, PNG, WEBP, atau ICO")
    ext = FORMATS[fmt]
    name = f"{new_id()}.{ext}"
    folder = UPLOAD_DIR / ("private" if private else "public")
    if fmt != "ICO":
        img = ImageOps.exif_transpose(img)
        img.thumbnail((2000, 2000))
        if fmt == "JPEG" and img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(folder / name, format=fmt, quality=85, optimize=True)
    else:
        (folder / name).write_bytes(raw)
    w, h = img.size
    m = {"id": new_id(), "file": name, "url": f"/api/media/{'private' if private else 'file'}/{name}", "private": private,
         "alt": TAG.sub("", alt)[:200], "original_name": TAG.sub("", file.filename or "")[:120], "width": w, "height": h,
         "size": (folder / name).stat().st_size, "uploaded_by": user["name"], "created_at": iso()}
    await db.media.insert_one(m)
    return clean(m)


@router.get("/media")
async def list_media(user=Depends(require(*MANAGERS))):
    return await find_list("media", {"private": False}, [("created_at", -1)], 1000)


class AltIn(BaseModel):
    alt: str


@router.patch("/media/{mid}")
async def update_media(mid: str, body: AltIn, user=Depends(require(*MANAGERS))):
    await db.media.update_one({"id": mid}, {"$set": {"alt": TAG.sub("", body.alt)[:200]}})
    return {"ok": True}


@router.delete("/media/{mid}")
async def delete_media(mid: str, user=Depends(require(*MANAGERS))):
    m = await db.media.find_one({"id": mid})
    if not m:
        raise HTTPException(404, "Media tidak ditemukan")
    await db.media.delete_one({"id": mid})
    p = UPLOAD_DIR / ("private" if m["private"] else "public") / m["file"]
    if p.exists():
        p.unlink()
    await audit(user, "hapus_media", "media", mid, before={"file": m["file"]})
    return {"ok": True}


def safe_path(folder, name):
    if not re.fullmatch(r"[a-f0-9]{32}\.(jpg|png|webp|ico)", name):
        raise HTTPException(404, "File tidak ditemukan")
    p = UPLOAD_DIR / folder / name
    if not p.exists():
        raise HTTPException(404, "File tidak ditemukan")
    return p


@router.get("/media/file/{name}")
async def media_file(name: str):
    return FileResponse(safe_path("public", name), headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/media/private/{name}")
async def media_private(name: str, user=Depends(require(*STAFF))):
    return FileResponse(safe_path("private", name), headers={"Cache-Control": "private, max-age=3600"})
