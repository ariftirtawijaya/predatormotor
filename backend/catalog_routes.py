import io
import os
import re
import json
import hashlib
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError, PyMongoError
from core import (db, client, iso, new_id, find_list, get_or_404, require, audit, strip_cost, move_stock, norm_text, text_key, norm_sku,
                  is_replica_set, STAFF, MANAGERS)

router = APIRouter(prefix="/api")
COLS = ["kode_produk", "nama_produk", "kategori", "merek", "nama_varian", "sku", "harga_jual", "modal", "garansi_hari",
        "stok_minimum", "status", "stok_awal"]
MAX_ROWS = 2000
VARIANT_FIELDS = ("variant", "price", "cost", "warranty_days", "min_stock", "active")


def display_name(product_name, variant):
    return f"{product_name} – {variant}" if variant else product_name


def slug_code(s):
    return re.sub(r"[^A-Z0-9]+", "-", (s or "").upper()).strip("-")[:30] or "PRODUK"


def auto_sku(code, variant=""):
    return norm_sku(f"{code}-{slug_code(variant)}" if variant else code)[:40]


async def unique_code(base, session=None):
    code, n = base, 1
    while await db.products.find_one({"code": code}, session=session):
        n += 1
        code = f"{base}-{n}"
    return code


async def unique_sku(base, session=None):
    sku, n = base, 1
    while await db.items.find_one({"sku": sku}, session=session):
        n += 1
        sku = f"{base[:36]}-{n}"
    return sku


class VariantIn(BaseModel):
    sku: str = Field(default="", max_length=40)
    variant: str = Field(default="", max_length=60)
    cost: int = Field(default=0, ge=0)
    price: int = Field(default=0, ge=0)
    active: bool = True
    min_stock: int = Field(default=0, ge=0)
    warranty_days: int = Field(default=0, ge=0)
    initial_stock: int = Field(default=0, ge=0)


class NewVariantIn(VariantIn):
    standard_name: str = Field(default="", max_length=60)


class ProductIn(BaseModel):
    code: str = Field(default="", max_length=30)
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="", max_length=60)
    brand: str = Field(default="", max_length=60)
    active: bool = True


class ProductCreate(ProductIn):
    sku: str = Field(default="", max_length=40)
    price: int = Field(default=0, ge=0)
    cost: int = Field(default=0, ge=0)
    min_stock: int = Field(default=0, ge=0)
    warranty_days: int = Field(default=0, ge=0)
    initial_stock: int = Field(default=0, ge=0)
    variants: list[VariantIn] = Field(default=[], max_length=100)


class ItemIn(BaseModel):
    """Kompatibilitas: membuat produk + satu varian, atau menambah varian bila product_id diisi."""
    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(default="", max_length=120)
    product_id: str | None = None
    category: str = ""
    brand: str = ""
    variant: str = ""
    cost: int = Field(default=0, ge=0)
    price: int = Field(default=0, ge=0)
    active: bool = True
    min_stock: int = Field(default=0, ge=0)
    warranty_days: int = Field(default=0, ge=0)
    initial_stock: int = Field(default=0, ge=0)


async def check_sku(sku, iid=None, session=None):
    if await db.items.find_one({"sku": sku, **({"id": {"$ne": iid}} if iid else {})}, session=session):
        raise HTTPException(400, f"SKU {sku} sudah dipakai")


async def add_variant(p, v, user, session=None):
    variant = norm_text(v.get("variant"))
    sku = norm_sku(v.get("sku"))
    if sku:
        await check_sku(sku, session=session)
    else:
        sku = await unique_sku(auto_sku(p["code"], variant), session)
    if await db.items.find_one({"product_id": p["id"], "variant_key": text_key(variant)}, session=session):
        raise HTTPException(400, f"Varian '{variant or 'Standar'}' sudah ada di produk {p['name']}")
    d = {"id": new_id(), "product_id": p["id"], "product_name": p["name"], "variant": variant, "variant_key": text_key(variant), "sku": sku,
         "name": display_name(p["name"], variant), "category": p["category"], "brand": p["brand"], "unit": "pcs", "stock": 0,
         "cost": v.get("cost", 0), "price": v.get("price", 0), "active": v.get("active", True), "min_stock": v.get("min_stock", 0),
         "warranty_days": v.get("warranty_days", 0), "created_at": iso()}
    await db.items.insert_one(d, session=session)
    d.pop("_id", None)
    if v.get("initial_stock"):
        await move_stock(d["id"], v["initial_stock"], "stok_awal", "Stok awal", user, "item", d["id"], sku, session=session)
    await audit(user, "buat_varian", "item", d["id"], after={"sku": sku, "name": d["name"], "price": d["price"]}, session=session)
    return d


async def new_product(body, user, allow_same_name=False, session=None):
    name = norm_text(body["name"])
    if not allow_same_name and await db.products.find_one({"name_key": text_key(name)}, session=session):
        raise HTTPException(400, f"Produk '{name}' sudah ada. Tambahkan varian ke produk tersebut.")
    code = norm_sku(body.get("code"))
    if code and await db.products.find_one({"code": code}, session=session):
        raise HTTPException(400, f"Kode produk {code} sudah dipakai")
    p = {"id": new_id(), "code": code or await unique_code(slug_code(name), session), "name": name, "name_key": text_key(name),
         "category": norm_text(body.get("category")), "brand": norm_text(body.get("brand")), "active": body.get("active", True), "created_at": iso()}
    await db.products.insert_one(p, session=session)
    p.pop("_id", None)
    await audit(user, "buat_produk", "product", p["id"], after={"code": p["code"], "name": name}, session=session)
    return p


@router.get("/products")
async def list_products(q: str = "", user=Depends(require(*STAFF))):
    f = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        ids = [i["product_id"] for i in await find_list("items", {"$or": [{"sku": rx}, {"variant": rx}]}, limit=3000)]
        f = {"$or": [{"name": rx}, {"code": rx}, {"brand": rx}, {"category": rx}, {"id": {"$in": ids}}]}
    prods = await find_list("products", f, [("name", 1)], 3000)
    items = await find_list("items", {"product_id": {"$in": [p["id"] for p in prods]}}, [("variant", 1)], 20000)
    by = {}
    for i in items:
        by.setdefault(i["product_id"], []).append(i)
    for p in prods:
        p["variants"] = by.get(p["id"], [])
        p["stock_total"] = sum(v["stock"] for v in p["variants"])
        p["simple"] = len(p["variants"]) == 1 and not p["variants"][0]["variant"]
    return strip_cost(prods, user)


@router.post("/products")
async def create_product(body: ProductCreate, user=Depends(require(*MANAGERS))):
    variants = [v.model_dump() for v in body.variants]
    if len(variants) == 1 and not norm_text(variants[0]["variant"]):
        variants = [variants[0] | {"variant": ""}]
    elif not variants:
        variants = [{k: getattr(body, k) for k in ("sku", "price", "cost", "min_stock", "warranty_days", "initial_stock")} | {"variant": "", "active": True}]
    elif any(not norm_text(v["variant"]) for v in variants):
        raise HTTPException(400, "Setiap varian wajib diberi nama (mis. Merah, 2 warna). Untuk produk tanpa pilihan, hapus semua baris varian.")
    skus = [norm_sku(v["sku"]) for v in variants if norm_sku(v["sku"])]
    keys = [text_key(v["variant"]) for v in variants]
    if len(set(skus)) != len(skus) or len(set(keys)) != len(keys):
        raise HTTPException(400, "SKU dan nama varian dalam satu produk tidak boleh kembar")
    for s in skus:
        await check_sku(s)
    p = await new_product(body.model_dump(), user)
    for v in variants:
        await add_variant(p, v, user)
    return p


@router.put("/products/{pid}")
async def update_product_route(pid: str, body: ProductIn, user=Depends(require(*MANAGERS))):
    return await update_product(pid, body, user)


async def update_product(pid, body, user, session=None):
    old = await db.products.find_one({"id": pid}, {"_id": 0}, session=session)
    if not old:
        raise HTTPException(404, "Produk tidak ditemukan")
    name = norm_text(body.name)
    if await db.products.find_one({"id": {"$ne": pid}, "name_key": text_key(name)}, session=session):
        raise HTTPException(400, f"Produk '{name}' sudah ada")
    code = norm_sku(body.code) or old["code"]
    if await db.products.find_one({"id": {"$ne": pid}, "code": code}, session=session):
        raise HTTPException(400, f"Kode produk {code} sudah dipakai")
    upd = {"code": code, "name": name, "name_key": text_key(name), "category": norm_text(body.category), "brand": norm_text(body.brand),
           "active": body.active}
    await db.products.update_one({"id": pid}, {"$set": upd}, session=session)
    async for i in db.items.find({"product_id": pid}, {"_id": 0, "id": 1, "variant": 1}, session=session):
        await db.items.update_one({"id": i["id"]}, {"$set": {"product_name": name, "name": display_name(name, i["variant"]),
                                                             "category": upd["category"], "brand": upd["brand"]}}, session=session)
    await audit(user, "ubah_produk", "product", pid, before={k: old.get(k) for k in upd}, after=upd, session=session)
    return await db.products.find_one({"id": pid}, {"_id": 0}, session=session)


@router.post("/products/{pid}/variants")
async def create_variant(pid: str, body: NewVariantIn, user=Depends(require(*MANAGERS))):
    p = await get_or_404("products", pid, "Produk tidak ditemukan")
    variant = norm_text(body.variant)
    if not variant:
        raise HTTPException(400, "Varian baru wajib diberi nama (mis. Merah, 2 warna)")
    if norm_sku(body.sku):
        await check_sku(norm_sku(body.sku))
    standard = await db.items.find_one({"product_id": pid, "variant_key": ""}, {"_id": 0})
    if standard:
        std_name = norm_text(body.standard_name)
        if not std_name:
            raise HTTPException(400, f"Produk ini masih produk sederhana. Beri nama varian untuk barang lama (SKU {standard['sku']}) terlebih dahulu.")
        if text_key(std_name) == text_key(variant):
            raise HTTPException(400, "Nama varian barang lama dan varian baru tidak boleh sama")
        if await db.items.find_one({"product_id": pid, "variant_key": text_key(std_name)}):
            raise HTTPException(400, f"Varian '{std_name}' sudah ada")
    if await db.items.find_one({"product_id": pid, "variant_key": text_key(variant)}):
        raise HTTPException(400, f"Varian '{variant}' sudah ada di produk {p['name']}")
    if standard:
        await db.items.update_one({"id": standard["id"]}, {"$set": {"variant": std_name, "variant_key": text_key(std_name),
                                                                    "name": display_name(p["name"], std_name)}})
        await audit(user, "produk_sederhana_jadi_varian", "item", standard["id"], before={"variant": "", "name": standard["name"]},
                    after={"variant": std_name, "sku": standard["sku"], "stock": standard["stock"]})
    return strip_cost(await add_variant(p, body.model_dump(), user), user)


@router.post("/items")
async def create_item(body: ItemIn, user=Depends(require(*MANAGERS))):
    if body.product_id:
        p = await get_or_404("products", body.product_id, "Produk tidak ditemukan")
    else:
        if not body.name.strip():
            raise HTTPException(400, "Nama produk wajib diisi")
        await check_sku(norm_sku(body.sku))
        p = await db.products.find_one({"name_key": text_key(body.name), "brand": norm_text(body.brand)}, {"_id": 0})
        p = p or await new_product(body.model_dump(), user, allow_same_name=True)
    d = await add_variant(p, body.model_dump(), user)
    return await get_or_404("items", d["id"])


class VariantPatch(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    variant: str = Field(default="", max_length=60)
    cost: int | None = Field(default=None, ge=0)
    price: int = Field(default=0, ge=0)
    active: bool = True
    min_stock: int = Field(default=0, ge=0)
    warranty_days: int = Field(default=0, ge=0)


@router.put("/items/{iid}")
async def update_item(iid: str, body: VariantPatch, user=Depends(require(*MANAGERS))):
    old = await get_or_404("items", iid)
    sku = norm_sku(body.sku)
    await check_sku(sku, iid)
    variant = norm_text(body.variant)
    siblings = await db.items.count_documents({"product_id": old.get("product_id"), "id": {"$ne": iid}})
    if not variant and siblings:
        raise HTTPException(400, "Produk ini punya beberapa varian; setiap varian wajib diberi nama")
    if await db.items.find_one({"product_id": old.get("product_id"), "variant_key": text_key(variant), "id": {"$ne": iid}}):
        raise HTTPException(400, f"Varian '{variant or 'Standar'}' sudah ada")
    upd = body.model_dump(exclude={"cost"} if body.cost is None else set())
    upd |= {"sku": sku, "variant": variant, "variant_key": text_key(variant), "name": display_name(old.get("product_name") or old["name"], variant)}
    await db.items.update_one({"id": iid}, {"$set": upd})
    await audit(user, "ubah_varian", "item", iid, before={k: old.get(k) for k in upd}, after=upd)
    return strip_cost(await get_or_404("items", iid), user)


# ---------- Migrasi ----------
async def backfill_keys():
    """Idempoten: isi name_key/variant_key (dinormalisasi: spasi & huruf besar/kecil) untuk indeks unik."""
    async for p in db.products.find({"name_key": {"$exists": False}}, {"_id": 0, "id": 1, "name": 1}):
        await db.products.update_one({"id": p["id"]}, {"$set": {"name_key": text_key(p["name"])}})
    async for i in db.items.find({"product_id": {"$exists": True}, "variant_key": {"$exists": False}}, {"_id": 0, "id": 1, "variant": 1}):
        await db.items.update_one({"id": i["id"]}, {"$set": {"variant_key": text_key(i.get("variant"))}})


async def migrate_products():
    """Idempoten: barang tanpa product_id dikelompokkan per (nama, merek) menjadi produk induk; id barang tidak berubah."""
    legacy = await find_list("items", {"product_id": {"$exists": False}}, [("created_at", 1)], 100000)
    groups = {}
    for i in legacy:
        groups.setdefault((text_key(i["name"]), text_key(i.get("brand"))), []).append(i)
    for rows in groups.values():
        first = rows[0]
        name = norm_text(first["name"])
        if await db.products.find_one({"name_key": text_key(name)}):
            name = f"{name} ({first.get('brand') or first['sku']})"
        p = {"id": new_id(), "code": await unique_code(slug_code(first["name"])), "name": name, "name_key": text_key(name),
             "category": first.get("category", ""), "brand": first.get("brand", ""), "active": any(r.get("active") for r in rows),
             "created_at": iso(), "migrated": True}
        await db.products.insert_one(p)
        seen = set()
        for r in rows:
            v = norm_text(r.get("variant"))
            if text_key(v) in seen or (not v and len(rows) > 1):
                v = f"{v} ({r['sku']})".strip()
            seen.add(text_key(v))
            await db.items.update_one({"id": r["id"]}, {"$set": {"product_id": p["id"], "product_name": p["name"], "variant": v,
                                                                 "variant_key": text_key(v), "name": display_name(p["name"], v),
                                                                 "migrated_from_flat": True}})
    if legacy:
        await db.migrations.insert_one({"key": "products_v1", "items": len(legacy), "products": len(groups), "at": iso()})
    return len(legacy)


# ---------- Template & impor Excel ----------
GUIDE = [
    ("kode_produk", "Wajib. Penanda produk induk; baris dengan kode sama = varian dari produk yang sama (mis. DE360)."),
    ("nama_produk", "Wajib. Nama produk induk, sama untuk semua barisnya. Satu nama produk hanya boleh memakai satu kode."),
    ("kategori", "Opsional. Sama untuk semua baris satu produk."),
    ("merek", "Opsional. Sama untuk semua baris satu produk."),
    ("nama_varian", "Kosongkan untuk produk sederhana (tanpa pilihan, cukup satu baris). Isi untuk produk bervarian, mis. Merah, 2 warna."),
    ("sku", "Opsional & unik. Kosong = dibuat otomatis dari kode_produk (+ nama_varian)."),
    ("harga_jual", "Wajib. Angka rupiah per pcs, tanpa titik (mis. 350000)."),
    ("modal", "Opsional. Angka rupiah per pcs. Hanya terlihat oleh owner."),
    ("garansi_hari", "Opsional. 0 = tanpa garansi."),
    ("stok_minimum", "Opsional. Batas peringatan stok menipis."),
    ("status", "aktif / nonaktif (kosong = aktif)."),
    ("stok_awal", "Hanya untuk varian BARU. Untuk varian yang sudah ada, stok tidak diubah — pakai Barang masuk / Opname."),
]
SAMPLES = [
    ["DE360", "Devil Eye 360", "Devil Eye", "Predator", v, f"DE360-{c}", 175000, 110000, 90, 2, "aktif", 0]
    for v, c in (("Merah", "RED"), ("Kuning", "YLW"), ("Ice Blue", "ICE"), ("Ungu", "PRP"), ("Biru", "BLU"), ("Orange", "ORG"))
] + [
    ["BILED-X1", "BiLED X1 3 Inch", "BiLED", "Merek X", v, f"BLX1-{n}W", p, m, 365, 1, "aktif", 0]
    for v, n, p, m in (("1 warna", 1, 950000, 650000), ("2 warna", 2, 1150000, 800000), ("3 warna", 3, 1350000, 950000))
] + [["KBL-RELAY", "Kabel Relay Set", "Kelistrikan", "", "", "", 85000, 45000, 0, 5, "aktif", 0]]


@router.get("/items/import/template")
async def import_template(user=Depends(require(*MANAGERS))):
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(COLS)
    for r in SAMPLES:
        ws.append(r)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="FDE68A")
    for col, w in zip("ABCDEFGHIJKL", (14, 24, 14, 12, 14, 14, 12, 12, 13, 13, 10, 10)):
        ws.column_dimensions[col].width = w
    g = wb.create_sheet("Panduan")
    g.append(["Kolom", "Keterangan"])
    for row in GUIDE:
        g.append(list(row))
    g.append([])
    g.append(["Catatan", "Satu baris = satu varian. Hapus baris contoh sebelum mengimpor data asli. Impor ulang file yang sama tidak menggandakan stok. "
                         "Impor disimpan seluruhnya atau tidak sama sekali."])
    g.column_dimensions["A"].width, g.column_dimensions["B"].width = 16, 110
    g["A1"].font = g["B1"].font = Font(bold=True)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": 'attachment; filename="template-master-barang.xlsx"'})


def _num(v, field, required=False):
    if v is None or str(v).strip() == "":
        if required:
            raise ValueError(f"{field} wajib diisi")
        return 0
    try:
        f = float(str(v).replace(".", "").replace(",", "")) if isinstance(v, str) else float(v)
    except ValueError:
        raise ValueError(f"{field} harus angka")
    if f < 0 or f != int(f):
        raise ValueError(f"{field} harus bilangan bulat ≥ 0")
    return int(f)


def parse_sheet(content):
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        raise HTTPException(400, "File bukan Excel .xlsx yang valid")
    ws = wb["Data"] if "Data" in wb.sheetnames else wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(400, "Sheet kosong")
    head = [str(c or "").strip().lower() for c in rows[0]]
    missing = [c for c in COLS if c not in head]
    if missing:
        raise HTTPException(400, f"Kolom wajib tidak ada: {', '.join(missing)}. Gunakan template terbaru.")
    idx = {c: head.index(c) for c in COLS}
    out = []
    for n, r in enumerate(rows[1:], start=2):
        if not any(x not in (None, "") for x in r):
            continue
        out.append((n, {c: (r[idx[c]] if idx[c] < len(r) else None) for c in COLS}))
    if len(out) > MAX_ROWS:
        raise HTTPException(400, f"Maksimal {MAX_ROWS} baris per impor")
    return out


def _parse_row(r):
    s = lambda k: norm_text(r[k])  # noqa: E731
    code, pname = norm_sku(r["kode_produk"]), s("nama_produk")
    if not code or not pname:
        raise ValueError("kode_produk dan nama_produk wajib diisi")
    status = s("status").lower() or "aktif"
    if status not in ("aktif", "nonaktif"):
        raise ValueError("status harus aktif atau nonaktif")
    variant = s("nama_varian")
    return {"code": code, "name": pname, "category": s("kategori"), "brand": s("merek")}, {
        "sku": norm_sku(r["sku"]) or auto_sku(code, variant), "sku_auto": not norm_sku(r["sku"]), "variant": variant,
        "price": _num(r["harga_jual"], "harga_jual", True), "cost": _num(r["modal"], "modal"),
        "warranty_days": _num(r["garansi_hari"], "garansi_hari"), "min_stock": _num(r["stok_minimum"], "stok_minimum"),
        "active": status == "aktif", "initial_stock": _num(r["stok_awal"], "stok_awal")}


def _vname(v):
    return f"'{v}'" if v else "tanpa nama (produk sederhana)"


async def plan_import(rows, session=None):
    """Validasi seluruh file sebagai satu kesatuan (antarbaris & terhadap database) lalu susun rencana."""
    errors, prods, seen_sku, name_owner = [], {}, {}, {}
    err = lambda n, m: errors.append({"row": n, "message": m})  # noqa: E731
    for n, r in rows:
        try:
            head, v = _parse_row(r)
        except ValueError as e:
            err(n, str(e))
            continue
        code, nk = head["code"], text_key(head["name"])
        if nk in name_owner and name_owner[nk][0] != code:
            err(n, f"Nama produk '{head['name']}' sudah dipakai kode {name_owner[nk][0]} (baris {name_owner[nk][1]}). Satu nama produk hanya boleh satu kode.")
            continue
        g = prods.get(code)
        if g and (text_key(g["name"]), text_key(g["category"]), text_key(g["brand"])) != (nk, text_key(head["category"]), text_key(head["brand"])):
            err(n, f"Nama/kategori/merek produk {code} berbeda dengan baris {g['row']}. Semua baris satu kode harus sama.")
            continue
        if v["sku"] in seen_sku:
            err(n, f"SKU {v['sku']} ganda di file (juga baris {seen_sku[v['sku']]})" + (" — SKU otomatis; isi kolom sku" if v["sku_auto"] else ""))
            continue
        if g and any(text_key(x["variant"]) == text_key(v["variant"]) for x in g["variants"]):
            err(n, f"Varian {_vname(v['variant'])} ganda pada produk {code}")
            continue
        if g and (not v["variant"] or any(not x["variant"] for x in g["variants"])):
            err(n, f"Produk {code} punya lebih dari satu baris: setiap baris wajib diisi nama_varian (kosong hanya untuk produk sederhana satu baris)")
            continue
        seen_sku[v["sku"]] = n
        name_owner.setdefault(nk, (code, n))
        g = prods.setdefault(code, head | {"row": n, "variants": []})
        g["variants"].append(v | {"row": n})
    plan = []
    for code, g in prods.items():
        ex = await db.products.find_one({"code": code}, {"_id": 0}, session=session)
        other = await db.products.find_one({"name_key": text_key(g["name"]), "code": {"$ne": code}}, {"_id": 0}, session=session)
        if other:
            err(g["row"], f"Produk '{g['name']}' sudah ada dengan kode {other['code']}. Pakai kode itu agar tidak dobel.")
            continue
        g["existing"] = ex
        current = {i["id"]: i async for i in db.items.find({"product_id": ex["id"]}, {"_id": 0}, session=session)} if ex else {}
        final, bad = {k: i["variant"] for k, i in current.items()}, False
        for v in g["variants"]:
            cur = await db.items.find_one({"sku": v["sku"]}, {"_id": 0}, session=session)
            if cur and (not ex or cur.get("product_id") != ex["id"]):
                err(v["row"], f"SKU {v['sku']} sudah dipakai produk lain ({cur['name']})" + (" — SKU otomatis; isi kolom sku" if v["sku_auto"] else ""))
                bad = True
                continue
            v["item_id"] = cur["id"] if cur else None
            final[cur["id"] if cur else f"new-{v['row']}"] = v["variant"]
        if bad:
            continue
        keys = {}
        for k, name in final.items():
            keys.setdefault(text_key(name), []).append(k)
        rowof = {v["item_id"] or f"new-{v['row']}": v["row"] for v in g["variants"]}
        for vk, ks in keys.items():
            if len(ks) > 1:
                n = max(rowof.get(k, g["row"]) for k in ks)
                err(n, f"Varian {_vname(final[ks[0]])} sudah ada di produk {code} dengan SKU lain")
                bad = True
        if len(final) > 1 and "" in keys and not bad:
            err(g["row"], f"Produk {code} akan punya beberapa varian, jadi setiap varian wajib bernama. "
                          f"Produk sederhana yang sudah ada: tambahkan varian lewat Master Barang (barang lama menjadi varian pertama).")
            bad = True
        if bad:
            continue
        changed_head = bool(ex) and (ex["name"], ex.get("category", ""), ex.get("brand", "")) != (g["name"], g["category"], g["brand"])
        for v in g["variants"]:
            cur = current.get(v["item_id"]) if v["item_id"] else None
            if cur:
                v["action"] = "perbarui" if changed_head or any(cur.get(k) != v[k] for k in VARIANT_FIELDS) else "tetap"
                v["stock_note"] = "stok_awal diabaikan (stok tidak ditimpa)" if v["initial_stock"] else ""
            else:
                v["action"], v["stock_note"] = "baru", ""
            plan.append({"row": v["row"], "product_code": code, "product_name": g["name"], "product_action": "perbarui" if ex else "baru",
                         **{k: v.get(k) for k in ("sku", "variant", "price", "cost", "initial_stock", "action", "stock_note", "item_id")}})
    plan.sort(key=lambda p: p["row"])
    return prods, plan, sorted(errors, key=lambda e: e["row"])


def plan_hash(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, default=str).encode()).hexdigest()


def _summary(plan):
    return {"products_new": len({p["product_code"] for p in plan if p["product_action"] == "baru"}),
            "products_existing": len({p["product_code"] for p in plan if p["product_action"] == "perbarui"}),
            "variants_new": sum(p["action"] == "baru" for p in plan), "variants_update": sum(p["action"] == "perbarui" for p in plan),
            "variants_same": sum(p["action"] == "tetap" for p in plan),
            "initial_stock_total": sum(p["initial_stock"] for p in plan if p["action"] == "baru")}


class ImportAbort(Exception):
    def __init__(self, code, msg, errors=None):
        self.code, self.msg, self.errors = code, msg, errors or []


def _fault_after():
    v = os.environ.get("IMPORT_TEST_FAIL_AFTER")
    return int(v) if v and os.environ.get("DB_NAME", "").startswith("predator_pytest_") else 0


async def apply_import(prods, plan, user, session):
    await db.locks.update_one({"key": "items_import"}, {"$set": {"at": iso(), "by": user["id"]}}, upsert=True, session=session)
    rows = {p["row"]: p for p in plan}
    writes, fail_after = 0, _fault_after()
    for code, g in prods.items():
        p = g.get("existing")
        if p:
            if (p["name"], p.get("category", ""), p.get("brand", "")) != (g["name"], g["category"], g["brand"]):
                p = await update_product(p["id"], ProductIn(code=code, name=g["name"], category=g["category"], brand=g["brand"], active=p["active"]),
                                         user, session=session)
        else:
            p = await new_product(g, user, session=session)
        for v in g["variants"]:
            action = rows[v["row"]]["action"]
            if action == "baru":
                await add_variant(p, v, user, session)
            elif action == "perbarui":
                await db.items.update_one({"id": v["item_id"]}, {"$set": {k: v[k] for k in VARIANT_FIELDS} | {
                    "variant_key": text_key(v["variant"]), "name": display_name(p["name"], v["variant"])}}, session=session)
            else:
                continue
            writes += 1
            if fail_after and writes >= fail_after:
                raise RuntimeError("Kegagalan buatan (uji) di tengah impor")
    await audit(user, "impor_barang_excel", "item", None, after=_summary(plan), session=session)


@router.post("/items/import")
async def import_items(commit: bool = False, plan_hash_in: str = Query("", alias="plan_hash"), file: UploadFile = File(...), user=Depends(require(*MANAGERS))):
    content = await file.read()
    if len(content) > 3 * 1024 * 1024:
        raise HTTPException(400, "File terlalu besar (maks 3 MB)")
    rows = parse_sheet(content)
    prods, plan, errors = await plan_import(rows)
    res = {"summary": _summary(plan), "errors": errors, "rows": strip_cost(plan, user), "plan_hash": plan_hash(plan), "committed": False,
           "transactions_ready": await is_replica_set()}
    if not commit:
        return res
    if errors:
        return JSONResponse({"detail": "Masih ada baris yang salah. Perbaiki file lalu pratinjau ulang. Tidak ada data yang disimpan.", "errors": errors}, 400)
    if not res["transactions_ready"]:
        raise HTTPException(503, "Penyimpanan impor membutuhkan MongoDB mode replica set (transaksi). Tidak ada data yang disimpan. Lihat README bagian Impor Excel.")
    if not plan_hash_in:
        raise HTTPException(400, "Lakukan pratinjau terlebih dahulu")

    async def run(session):
        p2, plan2, errors2 = await plan_import(rows, session)
        if errors2:
            raise ImportAbort(409, "Data barang berubah sejak pratinjau dan file kini bentrok. Tidak ada data yang disimpan; pratinjau ulang.", errors2)
        if plan_hash(plan2) != plan_hash_in:
            raise ImportAbort(409, "Data barang berubah sejak pratinjau (mungkin ada impor/perubahan lain). Tidak ada data yang disimpan; pratinjau ulang.")
        await apply_import(p2, plan2, user, session)
        return plan2

    try:
        async with await client.start_session() as s:
            plan2 = await s.with_transaction(run)
    except ImportAbort as e:
        return JSONResponse({"detail": e.msg, "errors": e.errors}, e.code)
    except HTTPException as e:
        raise HTTPException(409 if e.status_code == 400 else e.status_code, f"{e.detail}. Tidak ada data yang disimpan; pratinjau ulang.")
    except DuplicateKeyError:
        raise HTTPException(409, "Bentrok dengan impor/perubahan lain yang berjalan bersamaan. Tidak ada data yang disimpan; pratinjau ulang.")
    except (PyMongoError, RuntimeError):
        raise HTTPException(500, "Impor gagal di tengah proses. Seluruh perubahan dibatalkan — tidak ada data yang disimpan.")
    return res | {"rows": strip_cost(plan2, user), "summary": _summary(plan2), "committed": True}
