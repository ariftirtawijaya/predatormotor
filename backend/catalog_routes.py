import io
import re
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from core import db, iso, new_id, find_list, get_or_404, require, audit, strip_cost, move_stock, STAFF, MANAGERS

router = APIRouter(prefix="/api")
COLS = ["kode_produk", "nama_produk", "kategori", "merek", "nama_varian", "sku", "harga_jual", "modal", "garansi_hari",
        "stok_minimum", "status", "stok_awal"]
MAX_ROWS = 2000


def display_name(product_name, variant):
    return f"{product_name} – {variant}" if variant else product_name


def slug_code(s):
    return re.sub(r"[^A-Z0-9]+", "-", (s or "").upper()).strip("-")[:30] or "PRODUK"


async def unique_code(base):
    code, n = base, 1
    while await db.products.find_one({"code": code}):
        n += 1
        code = f"{base}-{n}"
    return code


class VariantIn(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    variant: str = Field(default="", max_length=60)
    cost: int = Field(default=0, ge=0)
    price: int = Field(default=0, ge=0)
    active: bool = True
    min_stock: int = Field(default=0, ge=0)
    warranty_days: int = Field(default=0, ge=0)
    initial_stock: int = Field(default=0, ge=0)


class ProductIn(BaseModel):
    code: str = Field(default="", max_length=30)
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="", max_length=60)
    brand: str = Field(default="", max_length=60)
    active: bool = True


class ProductCreate(ProductIn):
    variants: list[VariantIn] = Field(min_length=1, max_length=100)


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


async def check_sku(sku, iid=None):
    if await db.items.find_one({"sku": sku, **({"id": {"$ne": iid}} if iid else {})}):
        raise HTTPException(400, f"SKU {sku} sudah dipakai")


async def add_variant(p, v, user):
    sku = v["sku"].strip().upper()
    await check_sku(sku)
    variant = v.get("variant", "").strip()
    if await db.items.find_one({"product_id": p["id"], "variant": variant}):
        raise HTTPException(400, f"Varian '{variant or 'Standar'}' sudah ada di produk {p['name']}")
    d = {"id": new_id(), "product_id": p["id"], "product_name": p["name"], "variant": variant, "sku": sku,
         "name": display_name(p["name"], variant), "category": p["category"], "brand": p["brand"], "unit": "pcs", "stock": 0,
         "cost": v.get("cost", 0), "price": v.get("price", 0), "active": v.get("active", True), "min_stock": v.get("min_stock", 0),
         "warranty_days": v.get("warranty_days", 0), "created_at": iso()}
    await db.items.insert_one(d)
    d.pop("_id", None)
    if v.get("initial_stock"):
        await move_stock(d["id"], v["initial_stock"], "stok_awal", "Stok awal", user, "item", d["id"], sku)
    await audit(user, "buat_varian", "item", d["id"], after={"sku": sku, "name": d["name"], "price": d["price"]})
    return d


async def new_product(body, user, allow_same_name=False):
    name = body["name"].strip()
    if not allow_same_name and await db.products.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}):
        raise HTTPException(400, f"Produk '{name}' sudah ada. Tambahkan varian ke produk tersebut.")
    code = (body.get("code") or "").strip().upper()
    if code and await db.products.find_one({"code": code}):
        raise HTTPException(400, f"Kode produk {code} sudah dipakai")
    p = {"id": new_id(), "code": code or await unique_code(slug_code(name)), "name": name, "category": body.get("category", "").strip(),
         "brand": body.get("brand", "").strip(), "active": body.get("active", True), "created_at": iso()}
    await db.products.insert_one(p)
    p.pop("_id", None)
    await audit(user, "buat_produk", "product", p["id"], after={"code": p["code"], "name": name})
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
    return strip_cost(prods, user)


@router.post("/products")
async def create_product(body: ProductCreate, user=Depends(require(*MANAGERS))):
    skus = [v.sku.strip().upper() for v in body.variants]
    names = [v.variant.strip().lower() for v in body.variants]
    if len(set(skus)) != len(skus) or len(set(names)) != len(names):
        raise HTTPException(400, "SKU dan nama varian dalam satu produk tidak boleh kembar")
    for s in skus:
        await check_sku(s)
    p = await new_product(body.model_dump(), user)
    for v in body.variants:
        await add_variant(p, v.model_dump(), user)
    return p


@router.put("/products/{pid}")
async def update_product(pid: str, body: ProductIn, user=Depends(require(*MANAGERS))):
    old = await get_or_404("products", pid, "Produk tidak ditemukan")
    name = body.name.strip()
    if await db.products.find_one({"id": {"$ne": pid}, "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}):
        raise HTTPException(400, f"Produk '{name}' sudah ada")
    code = body.code.strip().upper() or old["code"]
    if await db.products.find_one({"id": {"$ne": pid}, "code": code}):
        raise HTTPException(400, f"Kode produk {code} sudah dipakai")
    upd = {"code": code, "name": name, "category": body.category.strip(), "brand": body.brand.strip(), "active": body.active}
    await db.products.update_one({"id": pid}, {"$set": upd})
    for i in await find_list("items", {"product_id": pid}):
        await db.items.update_one({"id": i["id"]}, {"$set": {"product_name": name, "name": display_name(name, i["variant"]),
                                                             "category": upd["category"], "brand": upd["brand"]}})
    await audit(user, "ubah_produk", "product", pid, before={k: old.get(k) for k in upd}, after=upd)
    return await get_or_404("products", pid)


@router.post("/products/{pid}/variants")
async def create_variant(pid: str, body: VariantIn, user=Depends(require(*MANAGERS))):
    p = await get_or_404("products", pid, "Produk tidak ditemukan")
    return strip_cost(await add_variant(p, body.model_dump(), user), user)


@router.post("/items")
async def create_item(body: ItemIn, user=Depends(require(*MANAGERS))):
    if body.product_id:
        p = await get_or_404("products", body.product_id, "Produk tidak ditemukan")
    else:
        if not body.name.strip():
            raise HTTPException(400, "Nama produk wajib diisi")
        await check_sku(body.sku.strip().upper())
        p = await db.products.find_one({"name": {"$regex": f"^{re.escape(body.name.strip())}$", "$options": "i"}, "brand": body.brand.strip()},
                                       {"_id": 0})
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
    sku = body.sku.strip().upper()
    await check_sku(sku, iid)
    variant = body.variant.strip()
    if await db.items.find_one({"product_id": old.get("product_id"), "variant": variant, "id": {"$ne": iid}}):
        raise HTTPException(400, f"Varian '{variant or 'Standar'}' sudah ada")
    upd = body.model_dump(exclude={"cost"} if body.cost is None else set())
    upd |= {"sku": sku, "variant": variant, "name": display_name(old.get("product_name") or old["name"], variant)}
    await db.items.update_one({"id": iid}, {"$set": upd})
    await audit(user, "ubah_varian", "item", iid, before={k: old.get(k) for k in upd}, after=upd)
    return strip_cost(await get_or_404("items", iid), user)


# ---------- Migrasi barang lama (kolom teks `variant`) ----------
async def migrate_products():
    """Idempoten: barang tanpa product_id dikelompokkan per (nama, merek) menjadi produk induk; id barang tidak berubah."""
    legacy = await find_list("items", {"product_id": {"$exists": False}}, [("created_at", 1)], 100000)
    groups = {}
    for i in legacy:
        groups.setdefault((i["name"].strip().lower(), (i.get("brand") or "").strip().lower()), []).append(i)
    for rows in groups.values():
        first = rows[0]
        p = {"id": new_id(), "code": await unique_code(slug_code(first["name"])), "name": first["name"].strip(),
             "category": first.get("category", ""), "brand": first.get("brand", ""), "active": any(r.get("active") for r in rows),
             "created_at": iso(), "migrated": True}
        await db.products.insert_one(p)
        seen = set()
        for r in rows:
            v = (r.get("variant") or "").strip()
            if v.lower() in seen:
                v = f"{v} ({r['sku']})".strip()
            seen.add(v.lower())
            await db.items.update_one({"id": r["id"]}, {"$set": {"product_id": p["id"], "product_name": p["name"], "variant": v,
                                                                 "name": display_name(p["name"], v), "migrated_from_flat": True}})
    if legacy:
        await db.migrations.insert_one({"key": "products_v1", "items": len(legacy), "products": len(groups), "at": iso()})
    return len(legacy)


# ---------- Template & impor Excel ----------
GUIDE = [
    ("kode_produk", "Wajib. Penanda produk induk; baris dengan kode sama = varian dari produk yang sama (mis. DE360)."),
    ("nama_produk", "Wajib. Nama produk induk, sama untuk semua barisnya."),
    ("kategori", "Opsional. Sama untuk semua baris satu produk."),
    ("merek", "Opsional. Sama untuk semua baris satu produk."),
    ("nama_varian", "Kosongkan jika produk tanpa pilihan (varian Standar). Contoh: Merah, 2 warna."),
    ("sku", "Wajib & unik untuk setiap varian fisik."),
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
] + [["KBL-RELAY", "Kabel Relay Set", "Kelistrikan", "", "", "KBL-RELAY", 85000, 45000, 0, 5, "aktif", 0]]


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
    g.append(["Catatan", "Satu baris = satu varian. Hapus baris contoh sebelum mengimpor data asli. Impor ulang file yang sama tidak menggandakan stok."])
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


async def plan_import(rows):
    errors, plan, prods = [], [], {}
    seen_sku = {}
    for n, r in rows:
        s = lambda k: str(r[k] or "").strip()  # noqa: E731
        try:
            code, pname, sku = s("kode_produk").upper(), s("nama_produk"), s("sku").upper()
            if not code or not pname or not sku:
                raise ValueError("kode_produk, nama_produk, dan sku wajib diisi")
            status = s("status").lower() or "aktif"
            if status not in ("aktif", "nonaktif"):
                raise ValueError("status harus aktif atau nonaktif")
            v = {"sku": sku, "variant": s("nama_varian"), "price": _num(r["harga_jual"], "harga_jual", True),
                 "cost": _num(r["modal"], "modal"), "warranty_days": _num(r["garansi_hari"], "garansi_hari"),
                 "min_stock": _num(r["stok_minimum"], "stok_minimum"), "active": status == "aktif",
                 "initial_stock": _num(r["stok_awal"], "stok_awal")}
        except ValueError as e:
            errors.append({"row": n, "message": str(e)})
            continue
        if sku in seen_sku:
            errors.append({"row": n, "message": f"SKU {sku} ganda di file (juga baris {seen_sku[sku]})"})
            continue
        seen_sku[sku] = n
        g = prods.setdefault(code, {"code": code, "name": pname, "category": s("kategori"), "brand": s("merek"), "row": n, "variants": []})
        if (g["name"], g["category"], g["brand"]) != (pname, s("kategori"), s("merek")):
            errors.append({"row": n, "message": f"Nama/kategori/merek produk {code} berbeda dengan baris {g['row']}"})
            continue
        if any(x["variant"].lower() == v["variant"].lower() for x in g["variants"]):
            errors.append({"row": n, "message": f"Varian '{v['variant'] or 'Standar'}' ganda pada produk {code}"})
            continue
        g["variants"].append(v | {"row": n})
    for code, g in prods.items():
        ex = await db.products.find_one({"code": code}, {"_id": 0})
        if not ex:
            same = await db.products.find_one({"name": {"$regex": f"^{re.escape(g['name'])}$", "$options": "i"}}, {"_id": 0})
            if same:
                errors.append({"row": g["row"], "message": f"Produk '{g['name']}' sudah ada dengan kode {same['code']}. Pakai kode itu agar tidak dobel."})
                continue
        g["existing"] = ex
        for v in g["variants"]:
            cur = await db.items.find_one({"sku": v["sku"]}, {"_id": 0})
            if cur and (not ex or cur.get("product_id") != ex["id"]):
                errors.append({"row": v["row"], "message": f"SKU {v['sku']} sudah dipakai produk lain ({cur['name']})"})
                continue
            if not cur and ex and await db.items.find_one({"product_id": ex["id"], "variant": v["variant"]}):
                errors.append({"row": v["row"], "message": f"Varian '{v['variant'] or 'Standar'}' sudah ada di {code} dengan SKU lain"})
                continue
            if cur:
                fields = ("variant", "price", "cost", "warranty_days", "min_stock", "active")
                v["action"] = "perbarui" if any(cur.get(k) != v[k] for k in fields) else "tetap"
                v["item_id"] = cur["id"]
                v["stock_note"] = "stok_awal diabaikan (stok tidak ditimpa)" if v["initial_stock"] else ""
            else:
                v["action"] = "baru"
            plan.append({"row": v["row"], "product_code": code, "product_name": g["name"], "product_action": "perbarui" if ex else "baru",
                         **{k: v.get(k) for k in ("sku", "variant", "price", "cost", "initial_stock", "action", "stock_note", "item_id")}})
    return prods, plan, sorted(errors, key=lambda e: e["row"])


@router.post("/items/import")
async def import_items(commit: bool = False, file: UploadFile = File(...), user=Depends(require(*MANAGERS))):
    content = await file.read()
    if len(content) > 3 * 1024 * 1024:
        raise HTTPException(400, "File terlalu besar (maks 3 MB)")
    prods, plan, errors = await plan_import(parse_sheet(content))
    summary = {"products_new": len({p["product_code"] for p in plan if p["product_action"] == "baru"}),
               "products_existing": len({p["product_code"] for p in plan if p["product_action"] == "perbarui"}),
               "variants_new": sum(p["action"] == "baru" for p in plan), "variants_update": sum(p["action"] == "perbarui" for p in plan),
               "variants_same": sum(p["action"] == "tetap" for p in plan),
               "initial_stock_total": sum(p["initial_stock"] for p in plan if p["action"] == "baru")}
    res = {"summary": summary, "errors": errors, "rows": strip_cost(plan, user), "committed": False}
    if not commit:
        return res
    if errors:
        raise HTTPException(400, "Masih ada baris yang salah. Perbaiki file lalu pratinjau ulang.")
    for code, g in prods.items():
        p = g.get("existing")
        if p:
            if (p["name"], p["category"], p["brand"]) != (g["name"], g["category"], g["brand"]):
                await update_product(p["id"], ProductIn(code=code, name=g["name"], category=g["category"], brand=g["brand"], active=p["active"]), user)
                p = await get_or_404("products", p["id"])
        else:
            p = await new_product(g, user)
        for v in g["variants"]:
            row = next((x for x in plan if x["row"] == v["row"]), None)
            if not row or row["action"] == "tetap":
                continue
            if row["action"] == "baru":
                await add_variant(p, v, user)
            else:
                await db.items.update_one({"id": row["item_id"]}, {"$set": {k: v[k] for k in ("variant", "price", "cost", "warranty_days", "min_stock", "active")}
                                                                    | {"name": display_name(p["name"], v["variant"])}})
    await audit(user, "impor_barang_excel", "item", None, after=summary)
    return res | {"committed": True}
