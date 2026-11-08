import re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from core import (db, iso, new_id, local_date, find_list, get_or_404, require, audit, strip_cost, norm_phone, norm_plate,
                  move_stock, record_damage, STAFF, MANAGERS)

router = APIRouter(prefix="/api")

PROVINCES = [
    ("Banten", True), ("DKI Jakarta", True), ("Jawa Barat", True), ("Jawa Tengah", True), ("DI Yogyakarta", True), ("Jawa Timur", True),
    ("Aceh", False), ("Sumatera Utara", False), ("Sumatera Barat", False), ("Riau", False), ("Kepulauan Riau", False), ("Jambi", False),
    ("Sumatera Selatan", False), ("Kepulauan Bangka Belitung", False), ("Bengkulu", False), ("Lampung", False), ("Bali", False),
    ("Nusa Tenggara Barat", False), ("Nusa Tenggara Timur", False), ("Kalimantan Barat", False), ("Kalimantan Tengah", False),
    ("Kalimantan Selatan", False), ("Kalimantan Timur", False), ("Kalimantan Utara", False), ("Sulawesi Utara", False),
    ("Gorontalo", False), ("Sulawesi Tengah", False), ("Sulawesi Barat", False), ("Sulawesi Selatan", False), ("Sulawesi Tenggara", False),
    ("Maluku", False), ("Maluku Utara", False), ("Papua", False), ("Papua Barat", False), ("Papua Barat Daya", False),
    ("Papua Tengah", False), ("Papua Pegunungan", False), ("Papua Selatan", False),
]
JAVA = {p for p, j in PROVINCES if j}


@router.get("/provinces")
async def provinces():
    return [{"name": p, "is_java": j} for p, j in PROVINCES]


# ---------- Items ----------
class ItemIn(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    category: str = ""
    brand: str = ""
    variant: str = ""
    cost: int = Field(default=0, ge=0)
    price: int = Field(default=0, ge=0)
    active: bool = True
    min_stock: int = Field(default=0, ge=0)
    warranty_days: int = Field(default=0, ge=0)
    initial_stock: int = Field(default=0, ge=0)


@router.get("/items")
async def list_items(q: str = "", active_only: bool = False, user=Depends(require(*STAFF))):
    f = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        f["$or"] = [{"name": rx}, {"sku": rx}, {"brand": rx}, {"category": rx}]
    if active_only:
        f["active"] = True
    return strip_cost(await find_list("items", f, [("name", 1)], 3000), user)


@router.post("/items")
async def create_item(body: ItemIn, user=Depends(require(*MANAGERS))):
    sku = body.sku.strip().upper()
    if await db.items.find_one({"sku": sku}):
        raise HTTPException(400, "Kode/SKU sudah dipakai")
    d = body.model_dump(exclude={"initial_stock"}) | {"id": new_id(), "sku": sku, "unit": "pcs", "stock": 0, "created_at": iso()}
    await db.items.insert_one(d)
    if body.initial_stock:
        await move_stock(d["id"], body.initial_stock, "stok_awal", "Stok awal", user, "item", d["id"], sku)
    await audit(user, "buat_barang", "item", d["id"], after={"sku": sku, "name": d["name"], "price": d["price"], "cost": d["cost"]})
    return await get_or_404("items", d["id"])


@router.put("/items/{iid}")
async def update_item(iid: str, body: ItemIn, user=Depends(require(*MANAGERS))):
    old = await get_or_404("items", iid)
    sku = body.sku.strip().upper()
    if await db.items.find_one({"sku": sku, "id": {"$ne": iid}}):
        raise HTTPException(400, "Kode/SKU sudah dipakai")
    upd = body.model_dump(exclude={"initial_stock"}) | {"sku": sku}
    await db.items.update_one({"id": iid}, {"$set": upd})
    await audit(user, "ubah_barang", "item", iid, before={k: old.get(k) for k in upd}, after=upd)
    return await get_or_404("items", iid)


# ---------- Packages ----------
class CompIn(BaseModel):
    item_id: str
    qty: int = Field(ge=1)


class OptIn(BaseModel):
    id: str | None = None
    name: str
    price: int = Field(ge=0)
    items: list[CompIn] = []


class PackageIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    main_brand_model: str = ""
    description: str = ""
    price: int = Field(ge=0)
    components: list[CompIn] = []
    options: list[OptIn] = []
    warranty_days: int = Field(default=0, ge=0)
    active: bool = True


@router.get("/packages")
async def list_packages(user=Depends(require(*STAFF))):
    pk = await find_list("packages", {}, [("name", 1)])
    items = {i["id"]: i for i in await find_list("items", {})}
    for p in pk:
        for c in p["components"] + [x for o in p["options"] for x in o["items"]]:
            it = items.get(c["item_id"], {})
            c.update({"name": it.get("name", "?"), "sku": it.get("sku"), "stock": it.get("stock", 0), "cost": it.get("cost", 0)})
        p["cost_total"] = sum(c["cost"] * c["qty"] for c in p["components"])
    return strip_cost(pk, user)


async def _check_items(body):
    ids = {c.item_id for c in body.components} | {c.item_id for o in body.options for c in o.items}
    found = await db.items.count_documents({"id": {"$in": list(ids)}})
    if found != len(ids):
        raise HTTPException(400, "Ada komponen yang tidak ditemukan di master barang")


def _pkg_doc(body):
    d = body.model_dump()
    for o in d["options"]:
        o["id"] = o.get("id") or new_id()
    return d


@router.post("/packages")
async def create_package(body: PackageIn, user=Depends(require(*MANAGERS))):
    await _check_items(body)
    d = _pkg_doc(body) | {"id": new_id(), "created_at": iso()}
    await db.packages.insert_one(d)
    await audit(user, "buat_paket", "package", d["id"], after={"name": d["name"], "price": d["price"]})
    return {"id": d["id"]}


@router.put("/packages/{pid}")
async def update_package(pid: str, body: PackageIn, user=Depends(require(*MANAGERS))):
    old = await get_or_404("packages", pid)
    await _check_items(body)
    d = _pkg_doc(body)
    await db.packages.update_one({"id": pid}, {"$set": d})
    await audit(user, "ubah_paket", "package", pid, before={"price": old["price"], "components": old["components"]},
                after={"price": d["price"], "components": d["components"]})
    return {"id": pid}


# ---------- Customers & vehicles ----------
class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = ""
    notes: str = ""


class VehicleIn(BaseModel):
    customer_id: str
    plate: str = Field(min_length=1, max_length=15)
    brand: str = ""
    model: str = ""
    year: str = ""
    color: str = ""


async def upsert_customer(c: dict):
    if c.get("id"):
        return await get_or_404("customers", c["id"], "Pelanggan tidak ditemukan")
    phone = norm_phone(c.get("phone"))
    if phone:
        ex = await db.customers.find_one({"phone": phone}, {"_id": 0})
        if ex:
            return ex
    if not (c.get("name") or "").strip():
        raise HTTPException(400, "Nama pelanggan wajib diisi")
    d = {"id": new_id(), "name": c["name"].strip()[:100], "phone": phone, "notes": "", "created_at": iso()}
    await db.customers.insert_one(d)
    return {k: v for k, v in d.items() if k != "_id"}


async def upsert_vehicle(v: dict, customer_id: str):
    if v.get("id"):
        return await get_or_404("vehicles", v["id"], "Kendaraan tidak ditemukan")
    plate = norm_plate(v.get("plate"))
    if not plate:
        raise HTTPException(400, "Plat nomor wajib diisi")
    ex = await db.vehicles.find_one({"plate": plate}, {"_id": 0})
    if ex:
        if ex["customer_id"] != customer_id:
            raise HTTPException(409, f"Plat {plate} sudah terdaftar atas pelanggan lain. Pilih kendaraan dari pencarian.")
        return ex
    d = {"id": new_id(), "customer_id": customer_id, "plate": plate, "brand": (v.get("brand") or "")[:40],
         "model": (v.get("model") or "")[:60], "year": (v.get("year") or "")[:4], "color": (v.get("color") or "")[:20], "created_at": iso()}
    await db.vehicles.insert_one(d)
    return {k: x for k, x in d.items() if k != "_id"}


@router.get("/customers")
async def list_customers(q: str = "", user=Depends(require(*STAFF))):
    f = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        f["$or"] = [{"name": rx}, {"phone": {"$regex": re.escape(norm_phone(q) or q)}}]
    return await find_list("customers", f, [("created_at", -1)], 300)


@router.put("/customers/{cid}")
async def update_customer(cid: str, body: CustomerIn, user=Depends(require(*STAFF))):
    old = await get_or_404("customers", cid)
    upd = {"name": body.name.strip(), "phone": norm_phone(body.phone), "notes": body.notes}
    await db.customers.update_one({"id": cid}, {"$set": upd})
    await audit(user, "ubah_pelanggan", "customer", cid, before={k: old.get(k) for k in upd}, after=upd)
    return await get_or_404("customers", cid)


@router.post("/vehicles")
async def create_vehicle(body: VehicleIn, user=Depends(require(*STAFF))):
    await get_or_404("customers", body.customer_id, "Pelanggan tidak ditemukan")
    if await db.vehicles.find_one({"plate": norm_plate(body.plate)}):
        raise HTTPException(400, "Plat sudah terdaftar")
    return await upsert_vehicle(body.model_dump(), body.customer_id)


@router.put("/vehicles/{vid}")
async def update_vehicle(vid: str, body: VehicleIn, user=Depends(require(*STAFF))):
    old = await get_or_404("vehicles", vid)
    plate = norm_plate(body.plate)
    if await db.vehicles.find_one({"plate": plate, "id": {"$ne": vid}}):
        raise HTTPException(400, "Plat sudah dipakai kendaraan lain")
    upd = body.model_dump() | {"plate": plate}
    await db.vehicles.update_one({"id": vid}, {"$set": upd})
    await audit(user, "ubah_kendaraan", "vehicle", vid, before={k: old.get(k) for k in upd}, after=upd)
    return await get_or_404("vehicles", vid)


@router.get("/search")
async def search(q: str, user=Depends(require(*STAFF))):
    q = q.strip()
    if len(q) < 2:
        return []
    rx = {"$regex": re.escape(q), "$options": "i"}
    cust = await find_list("customers", {"$or": [{"name": rx}, {"phone": {"$regex": re.escape(norm_phone(q) or q)}}]}, limit=50)
    plate = norm_plate(q)
    vf = [{"customer_id": {"$in": [c["id"] for c in cust]}}]
    if plate:
        vf.append({"plate": {"$regex": re.escape(plate)}})
    vehicles = await find_list("vehicles", {"$or": vf}, limit=50)
    cmap = {c["id"]: c for c in cust}
    missing = [v["customer_id"] for v in vehicles if v["customer_id"] not in cmap]
    for c in await find_list("customers", {"id": {"$in": missing}}):
        cmap[c["id"]] = c
    out = [{"vehicle": v, "customer": cmap.get(v["customer_id"])} for v in vehicles]
    with_v = {v["customer_id"] for v in vehicles}
    out += [{"vehicle": None, "customer": c} for c in cust if c["id"] not in with_v]
    return out


@router.get("/vehicles/{vid}/history")
async def vehicle_history(vid: str, user=Depends(require(*STAFF))):
    v = await get_or_404("vehicles", vid, "Kendaraan tidak ditemukan")
    c = await db.customers.find_one({"id": v["customer_id"]}, {"_id": 0})
    jobs = await find_list("jobs", {"vehicle_id": vid}, [("created_at", -1)])
    return strip_cost({"vehicle": v, "customer": c, "jobs": jobs}, user)


@router.get("/customers/{cid}/history")
async def customer_history(cid: str, user=Depends(require(*STAFF))):
    c = await get_or_404("customers", cid, "Pelanggan tidak ditemukan")
    vehicles = await find_list("vehicles", {"customer_id": cid})
    jobs = await find_list("jobs", {"customer_id": cid}, [("created_at", -1)])
    sales = await find_list("sales", {"customer_phone": c.get("phone") or "__none__"}, [("created_at", -1)], 100)
    orders = await find_list("orders", {"customer.phone": c.get("phone") or "__none__"}, [("created_at", -1)], 100)
    return strip_cost({"customer": c, "vehicles": vehicles, "jobs": jobs, "sales": sales, "orders": orders}, user)


# ---------- Stock operations ----------
class StockIn(BaseModel):
    item_id: str
    qty: int = Field(ge=1)
    note: str = ""
    cost: int | None = Field(default=None, ge=0)


class OpnameIn(BaseModel):
    item_id: str
    counted: int = Field(ge=0)
    note: str = ""


class CorrectionIn(BaseModel):
    item_id: str
    delta: int
    reason: str = Field(min_length=3)


class OutIn(BaseModel):
    item_id: str
    qty: int = Field(ge=1)
    reason: str = Field(min_length=3)


@router.post("/stock/in")
async def stock_in(body: StockIn, user=Depends(require(*MANAGERS))):
    reason = "Barang masuk diterima di bengkel" + (f" — {body.note}" if body.note else "")
    it = await move_stock(body.item_id, body.qty, "masuk", reason, user, "stock_in", None, None)
    if body.cost is not None and body.cost != it.get("cost"):
        await db.items.update_one({"id": body.item_id}, {"$set": {"cost": body.cost}})
        await audit(user, "ubah_modal", "item", body.item_id, before={"cost": it.get("cost")}, after={"cost": body.cost}, reason="barang masuk")
    return {"ok": True, "stock": it["stock"]}


@router.post("/stock/opname")
async def stock_opname(body: OpnameIn, user=Depends(require(*MANAGERS))):
    it = await get_or_404("items", body.item_id)
    delta = body.counted - it["stock"]
    if delta == 0:
        await db.stock_mutations.insert_one({"id": new_id(), "item_id": it["id"], "sku": it["sku"], "item_name": it["name"], "kind": "opname",
                                             "qty_before": it["stock"], "qty_after": it["stock"], "delta": 0, "reason": f"Opname cocok. {body.note}",
                                             "user_id": user["id"], "user_name": user["name"], "created_at": iso(), "date_local": local_date()})
        return {"ok": True, "delta": 0}
    res = await db.items.find_one_and_update({"id": it["id"], "stock": it["stock"]}, {"$set": {"stock": body.counted}},
                                             return_document=ReturnDocument.AFTER)
    if not res:
        raise HTTPException(409, "Stok berubah saat opname (ada transaksi lain). Muat ulang lalu ulangi.")
    await db.stock_mutations.insert_one({"id": new_id(), "item_id": it["id"], "sku": it["sku"], "item_name": it["name"], "kind": "opname",
                                         "qty_before": it["stock"], "qty_after": body.counted, "delta": delta,
                                         "reason": f"Stok opname. {body.note}".strip(), "user_id": user["id"], "user_name": user["name"],
                                         "created_at": iso(), "date_local": local_date()})
    await audit(user, "stok_opname", "item", it["id"], before={"stock": it["stock"]}, after={"stock": body.counted}, reason=body.note)
    return {"ok": True, "delta": delta}


@router.post("/stock/correction")
async def stock_correction(body: CorrectionIn, user=Depends(require(*MANAGERS))):
    if body.delta == 0:
        raise HTTPException(400, "Selisih tidak boleh 0")
    it = await move_stock(body.item_id, body.delta, "koreksi", body.reason, user, "correction")
    await audit(user, "koreksi_stok", "item", body.item_id, before={"stock": it["stock"] - body.delta}, after={"stock": it["stock"]}, reason=body.reason)
    return {"ok": True, "stock": it["stock"]}


@router.post("/stock/internal")
async def stock_internal(body: OutIn, user=Depends(require(*MANAGERS))):
    it = await move_stock(body.item_id, -body.qty, "pemakaian_internal", body.reason, user, "internal")
    return {"ok": True, "stock": it["stock"]}


@router.post("/stock/damage")
async def stock_damage(body: OutIn, user=Depends(require(*MANAGERS))):
    it = await get_or_404("items", body.item_id)
    d = await record_damage(it["id"], it["name"], body.qty, "stok", body.reason, user, True, "damage")
    await audit(user, "barang_rusak", "item", it["id"], after={"qty": body.qty}, reason=body.reason)
    return d


@router.get("/stock/mutations")
async def list_mutations(item_id: str | None = None, start: str | None = None, end: str | None = None, kind: str | None = None,
                         user=Depends(require(*MANAGERS))):
    f = {}
    if item_id:
        f["item_id"] = item_id
    if kind:
        f["kind"] = kind
    if start or end:
        f["date_local"] = {k: v for k, v in (("$gte", start), ("$lte", end)) if v}
    return await find_list("stock_mutations", f, [("created_at", -1)], 3000)


@router.get("/damaged")
async def list_damaged(user=Depends(require(*MANAGERS))):
    return await find_list("damaged", {}, [("created_at", -1)], 2000)


# ---------- Expenses ----------
class ExpenseIn(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    category: str
    amount: int = Field(ge=1)
    method: str = "tunai"
    note: str = ""


@router.get("/expenses")
async def list_expenses(start: str | None = None, end: str | None = None, user=Depends(require(*MANAGERS))):
    f = {"void": {"$ne": True}}
    if start or end:
        f["date"] = {k: v for k, v in (("$gte", start), ("$lte", end)) if v}
    return await find_list("expenses", f, [("date", -1)], 3000)


@router.post("/expenses")
async def create_expense(body: ExpenseIn, user=Depends(require(*MANAGERS))):
    d = body.model_dump() | {"id": new_id(), "user_name": user["name"], "user_id": user["id"], "created_at": iso()}
    await db.expenses.insert_one(d)
    await audit(user, "catat_biaya", "expense", d["id"], after=body.model_dump())
    return {"id": d["id"]}


class VoidIn(BaseModel):
    reason: str = Field(min_length=3)


@router.post("/expenses/{eid}/void")
async def void_expense(eid: str, body: VoidIn, user=Depends(require("owner"))):
    old = await get_or_404("expenses", eid)
    await db.expenses.update_one({"id": eid}, {"$set": {"void": True, "void_reason": body.reason, "void_by": user["name"]}})
    await audit(user, "batalkan_biaya", "expense", eid, before=old, reason=body.reason)
    return {"ok": True}
