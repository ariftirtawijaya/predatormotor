import re
from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from core import (db, now, iso, new_id, local_date, token, find_list, get_or_404, require, audit, strip_cost, norm_phone, norm_plate,
                  next_number, move_many, add_payment, record_damage, recompute_paid, COLL, STAFF, MANAGERS)
from master_routes import upsert_customer, upsert_vehicle, JAVA

router = APIRouter(prefix="/api")


class LineIn(BaseModel):
    type: str
    package_id: str | None = None
    option_ids: list[str] = []
    item_id: str | None = None
    name: str | None = None
    qty: int = Field(default=1, ge=1, le=999)
    unit_price: int | None = Field(default=None, ge=0)
    warranty_replacement: bool = False


async def build_line(inp: LineIn, user):
    is_mgr = user["role"] in MANAGERS
    base = {"lid": new_id(), "type": inp.type, "qty": inp.qty, "options": [], "detail": "", "removed": False,
            "added_by": user["name"], "added_at": iso(), "warranty_days": 0, "warranty_replacement": False}
    if inp.type == "package":
        p = await get_or_404("packages", inp.package_id or "", "Paket tidak ditemukan")
        opts = [o for o in p["options"] if o["id"] in inp.option_ids]
        comps = p["components"] + [c for o in opts for c in o["items"]]
        items = {i["id"]: i for i in await find_list("items", {"id": {"$in": [c["item_id"] for c in comps]}})}
        base.update(name=p["name"], package_id=p["id"], detail=p.get("main_brand_model", ""),
                    options=[{"name": o["name"], "price": o["price"]} for o in opts],
                    unit_price=p["price"] + sum(o["price"] for o in opts), warranty_days=p.get("warranty_days", 0),
                    components=[{"item_id": c["item_id"], "sku": items[c["item_id"]]["sku"], "name": items[c["item_id"]]["name"],
                                 "qty": c["qty"], "cost": items[c["item_id"]].get("cost", 0)} for c in comps])
    elif inp.type == "item":
        it = await get_or_404("items", inp.item_id or "", "Barang tidak ditemukan")
        price = inp.unit_price if (is_mgr and inp.unit_price is not None) else it["price"]
        if inp.warranty_replacement:
            price = 0
        base.update(name=it["name"], item_id=it["id"], detail=" ".join(x for x in (it.get("brand"), it.get("variant")) if x),
                    unit_price=price, warranty_days=it.get("warranty_days", 0), warranty_replacement=inp.warranty_replacement,
                    components=[{"item_id": it["id"], "sku": it["sku"], "name": it["name"], "qty": 1, "cost": it.get("cost", 0)}])
    elif inp.type == "service":
        if not (inp.name or "").strip() or inp.unit_price is None:
            raise HTTPException(400, "Nama dan harga jasa wajib diisi")
        base.update(name=inp.name.strip()[:120], unit_price=inp.unit_price, components=[])
    else:
        raise HTTPException(400, "Jenis baris tidak valid")
    base["subtotal"] = base["unit_price"] * base["qty"]
    base["cost_total"] = sum(c["cost"] * c["qty"] for c in base["components"]) * base["qty"]
    return base


def totals(doc):
    active = [l for l in doc.get("lines", []) if not l.get("removed")]
    sub = sum(l["subtotal"] for l in active)
    d = doc.get("discount") or {}
    disc = d.get("amount", 0) if d.get("status") == "approved" else 0
    disc = min(disc, sub)
    ship = doc.get("shipping_cost", 0) or 0
    return {"subtotal": sub, "discount_amount": disc, "total": sub - disc + ship,
            "hpp": sum(l.get("cost_total", 0) for l in active)}


def usage(doc):
    return [(c["item_id"], -c["qty"] * l["qty"]) for l in doc.get("lines", []) if not l.get("removed") for c in l["components"]]


async def save_totals(kind, doc, write_lines=False):
    coll = db[COLL[kind]]
    if write_lines:
        t = totals(doc)
        await coll.update_one({"id": doc["id"]}, {"$set": t | {"lines": doc["lines"]}})
        return t
    # Simpan total hanya jika baris belum berubah sejak dibaca; jika berubah (edit serentak) hitung ulang.
    for _ in range(20):
        t = totals(doc)
        if (await coll.update_one({"id": doc["id"], "lines": doc["lines"]}, {"$set": t})).matched_count:
            return t
        doc = await load(kind, doc["id"])
    return t


async def set_line(jid, line):
    await db.jobs.update_one({"id": jid, "status": "Masuk"}, {"$set": {"lines.$[l]": line}}, array_filters=[{"l.lid": line["lid"]}])
    doc = await load("job", jid)
    await save_totals("job", doc)


async def load(kind, id_):
    return await get_or_404(COLL[kind], id_, "Transaksi tidak ditemukan")


async def with_extras(kind, doc, user):
    doc["payments"] = await find_list("payments", {"ref_type": kind, "ref_id": doc["id"]}, [("created_at", 1)])
    if kind in ("job", "sale"):
        doc["claims"] = await find_list("jobs", {"claim.ref_id": doc["id"]}, [("created_at", 1)])
    if kind == "order":
        out = outstanding(doc)
        names = {x["id"]: x["name"] for x in await find_list("items", {"id": {"$in": list(out)}})}
        doc["outstanding_items"] = [{"item_id": k, "name": names.get(k, "?"), "qty": v} for k, v in out.items()]
    return strip_cost(doc, user)


# ---------- Jobs ----------
class JobIn(BaseModel):
    customer: dict
    vehicle: dict | None = None
    complaint: str = ""
    notes: str = ""
    photos: list[str] = []
    lines: list[LineIn] = []


class JobPatch(BaseModel):
    complaint: str | None = None
    notes: str | None = None
    photos: list[str] | None = None
    claim: dict | None = None


@router.get("/jobs")
async def list_jobs(status: str | None = None, q: str = "", kind: str | None = None, user=Depends(require(*STAFF))):
    f = {}
    if status:
        f["status"] = status
    if kind:
        f["kind"] = kind
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        f["$or"] = [{"no": rx}, {"vehicle.plate": {"$regex": re.escape(re.sub(r"[^A-Za-z0-9]", "", q).upper() or q)}},
                    {"customer.name": rx}, {"customer.phone": {"$regex": re.escape(norm_phone(q) or q)}}]
    return strip_cost(await find_list("jobs", f, [("created_at", -1)], 500), user)


async def create_job_doc(kind, customer, vehicle, user, complaint="", notes="", photos=None, claim=None):
    no = await next_number("NG" if kind == "garansi" else "NB")
    d = {"id": new_id(), "no": no, "kind": kind, "status": "Masuk", "customer_id": customer["id"],
         "customer": {"name": customer["name"], "phone": customer.get("phone", "")},
         "vehicle_id": vehicle["id"] if vehicle else None,
         "vehicle": {k: vehicle.get(k) for k in ("plate", "brand", "model")} if vehicle else None,
         "complaint": complaint[:2000], "notes": notes[:2000], "photos": photos or [], "lines": [], "discount": None,
         "subtotal": 0, "discount_amount": 0, "total": 0, "hpp": 0, "paid": 0, "refunded": 0, "stock_applied": False,
         "recognized": False, "returns": [], "claim": claim, "public_token": token(),
         "created_by": user["name"], "created_at": iso(), "date_local": local_date()}
    await db.jobs.insert_one(d)
    return d


@router.post("/jobs")
async def create_job(body: JobIn, user=Depends(require(*STAFF))):
    if body.vehicle and not body.vehicle.get("id") and await db.vehicles.find_one({"plate": norm_plate(body.vehicle.get("plate"))}):
        raise HTTPException(409, "Plat sudah terdaftar. Cari dan pilih kendaraan tersebut dari pencarian pelanggan lama.")
    c = await upsert_customer(body.customer)
    v = await upsert_vehicle(body.vehicle, c["id"]) if body.vehicle else None
    lines = [await build_line(l, user) for l in body.lines]
    d = await create_job_doc("servis", c, v, user, body.complaint, body.notes, body.photos)
    d["lines"] = lines
    await save_totals("job", d, True)
    await audit(user, "buat_nota_pekerjaan", "job", d["id"], after={"no": d["no"]})
    return await with_extras("job", await load("job", d["id"]), user)


@router.get("/jobs/{jid}")
async def get_job(jid: str, user=Depends(require(*STAFF))):
    return await with_extras("job", await load("job", jid), user)


def assert_open(doc):
    if doc["status"] != "Masuk":
        raise HTTPException(400, "Nota sudah Selesai/Batal dan tidak dapat diubah")
    if doc.get("lock"):
        raise HTTPException(409, "Nota sedang diproses")


@router.patch("/jobs/{jid}")
async def patch_job(jid: str, body: JobPatch, user=Depends(require(*STAFF))):
    doc = await load("job", jid)
    assert_open(doc)
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if "claim" in upd:
        upd["claim"] = (doc.get("claim") or {}) | {k: upd["claim"].get(k) for k in
                                                    ("inspection", "action", "technician", "claim_notes", "cost_note", "old_part") if k in upd["claim"]}
    await db.jobs.update_one({"id": jid}, {"$set": upd})
    return await with_extras("job", await load("job", jid), user)


@router.post("/jobs/{jid}/lines")
async def add_job_line(jid: str, body: LineIn, user=Depends(require(*STAFF))):
    doc = await load("job", jid)
    assert_open(doc)
    if body.warranty_replacement and doc["kind"] != "garansi":
        raise HTTPException(400, "Barang pengganti garansi hanya pada nota garansi")
    line = await build_line(body, user)
    await db.jobs.update_one({"id": jid, "status": "Masuk"}, {"$push": {"lines": line}})
    doc = await load("job", jid)
    await save_totals("job", doc)
    await audit(user, "tambah_baris", "job", jid, after={"name": line["name"], "qty": line["qty"], "price": line["unit_price"]})
    return await with_extras("job", await load("job", jid), user)


class LineEdit(BaseModel):
    qty: int | None = Field(default=None, ge=1)
    unit_price: int | None = Field(default=None, ge=0)
    reason: str = Field(min_length=3)


@router.put("/jobs/{jid}/lines/{lid}")
async def edit_job_line(jid: str, lid: str, body: LineEdit, user=Depends(require(*MANAGERS))):
    doc = await load("job", jid)
    assert_open(doc)
    line = next((l for l in doc["lines"] if l["lid"] == lid and not l.get("removed")), None)
    if not line:
        raise HTTPException(404, "Baris tidak ditemukan")
    before = {"qty": line["qty"], "unit_price": line["unit_price"]}
    if body.qty:
        line["cost_total"] = line["cost_total"] // line["qty"] * body.qty
        line["qty"] = body.qty
    if body.unit_price is not None:
        line["unit_price"] = body.unit_price
    line["subtotal"] = line["qty"] * line["unit_price"]
    line["edited_by"] = user["name"]
    if totals(doc)["total"] < doc["paid"]:
        raise HTTPException(400, "Total baru lebih kecil dari uang yang sudah dibayar")
    await set_line(jid, line)
    await audit(user, "ubah_baris", "job", jid, before=before | {"name": line["name"]},
                after={"qty": line["qty"], "unit_price": line["unit_price"]}, reason=body.reason)
    return await with_extras("job", await load("job", jid), user)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3)


@router.post("/jobs/{jid}/lines/{lid}/remove")
async def remove_job_line(jid: str, lid: str, body: ReasonIn, user=Depends(require(*MANAGERS))):
    doc = await load("job", jid)
    assert_open(doc)
    line = next((l for l in doc["lines"] if l["lid"] == lid and not l.get("removed")), None)
    if not line:
        raise HTTPException(404, "Baris tidak ditemukan")
    line.update(removed=True, removed_by=user["name"], removed_at=iso(), removed_reason=body.reason)
    if totals(doc)["total"] < doc["paid"]:
        raise HTTPException(400, "Total baru lebih kecil dari uang yang sudah dibayar")
    await set_line(jid, line)
    await audit(user, "hapus_baris", "job", jid, before={"name": line["name"], "qty": line["qty"], "price": line["unit_price"]}, reason=body.reason)
    return await with_extras("job", await load("job", jid), user)


class IdemIn(BaseModel):
    idem_key: str | None = None


@router.post("/jobs/{jid}/complete")
async def complete_job(jid: str, user=Depends(require(*STAFF))):
    doc = await load("job", jid)
    if doc["status"] == "Selesai":
        return await with_extras("job", doc, user)
    if (doc.get("discount") or {}).get("status") == "pending":
        raise HTTPException(400, "Diskon masih menunggu persetujuan owner")
    if not [l for l in doc["lines"] if not l.get("removed")] and doc["kind"] != "garansi":
        raise HTTPException(400, "Nota belum memiliki barang/jasa")
    locked = await db.jobs.find_one_and_update({"id": jid, "status": "Masuk", "lock": {"$ne": True}, "stock_applied": False},
                                               {"$set": {"lock": True}}, return_document=ReturnDocument.AFTER)
    if not locked:
        doc = await load("job", jid)
        if doc["status"] == "Selesai":
            return await with_extras("job", doc, user)
        raise HTTPException(409, "Nota sedang diproses atau tidak dapat diselesaikan")
    try:
        await move_many(usage(locked), "keluar_pekerjaan", f"Pekerjaan selesai {locked['no']}", user, "job", jid, locked["no"])
    except HTTPException:
        await db.jobs.update_one({"id": jid}, {"$set": {"lock": False}})
        raise
    today = local_date()
    for l in locked["lines"]:
        if l.get("warranty_days") and not l.get("removed"):
            l["warranty_until"] = (date.fromisoformat(today) + timedelta(days=l["warranty_days"])).isoformat()
    await db.jobs.update_one({"id": jid}, {"$set": {"status": "Selesai", "lock": False, "stock_applied": True, "recognized": True,
                                                    "recognized_date": today, "completed_at": iso(), "completed_by": user["name"],
                                                    "lines": locked["lines"]}})
    op = (locked.get("claim") or {}).get("old_part") or {}
    if op.get("name") and op.get("condition") == "rusak":
        await record_damage(op.get("item_id"), op["name"], int(op.get("qty") or 1), "klaim", f"Barang lama dari klaim {locked['no']}",
                            user, False, "job", jid, locked["no"], "rusak")
    await audit(user, "pekerjaan_selesai", "job", jid, after={"no": locked["no"], "total": locked["total"]})
    return await with_extras("job", await load("job", jid), user)


class ReturnItem(BaseModel):
    item_id: str = Field(min_length=1)
    qty: int = Field(ge=1, le=9999)
    condition: str


class CancelIn(BaseModel):
    reason: str = Field(min_length=3)
    refund_amount: int = Field(default=0, ge=0)
    refund_method: str = "tunai"
    items: list[ReturnItem] = []
    idem_key: str | None = None


@router.post("/jobs/{jid}/cancel")
async def cancel_job(jid: str, body: CancelIn, user=Depends(require("owner"))):
    stamp = iso()
    cutoff = (now() - timedelta(seconds=30)).isoformat()
    got = await db.jobs.find_one_and_update({"id": jid, "status": "Masuk", "lock": {"$ne": True},
                                             "$or": [{"pay_lock": None}, {"pay_lock": {"$lt": cutoff}}]}, {"$set": {"pay_lock": stamp}})
    if not got:
        doc = await load("job", jid)
        if doc["status"] != "Masuk":
            raise HTTPException(400, "Hanya nota berstatus Masuk yang dapat dibatalkan. Gunakan retur untuk nota Selesai.")
        raise HTTPException(409, "Nota sedang diproses. Muat ulang lalu coba lagi.")
    try:
        doc = await load("job", jid)
        kept = await _cancel_job(doc, body, user)
    finally:
        await db.jobs.update_one({"id": jid}, {"$set": {"pay_lock": None}})
    await audit(user, "batal_nota", "job", jid, before={"status": "Masuk", "paid": doc["paid"]},
                after={"status": "Batal", "refund": body.refund_amount, "dp_ditahan": kept}, reason=body.reason)
    return await with_extras("job", await load("job", jid), user)


async def _cancel_job(doc, body, user):
    jid = doc["id"]
    if body.refund_amount > doc["paid"] - doc["refunded"]:
        raise HTTPException(400, "Pengembalian melebihi uang yang diterima")
    if body.refund_amount:
        await add_payment("job", doc, body.refund_amount, body.refund_method, "refund", user, body.idem_key,
                          f"Pembatalan: {body.reason}", "out")
    kept = doc["paid"] - doc["refunded"] - body.refund_amount
    await db.jobs.update_one({"id": jid}, {"$set": {"status": "Batal", "cancel": {
        "reason": body.reason, "refund": body.refund_amount, "kept": kept, "by": user["name"], "at": iso(), "date_local": local_date()}}})
    return kept



class ClaimIn(BaseModel):
    ref_type: str
    ref_id: str
    line_lid: str
    symptom: str = Field(min_length=2)


@router.post("/claims")
async def create_claim(body: ClaimIn, user=Depends(require(*STAFF))):
    if body.ref_type not in ("job", "sale", "order"):
        raise HTTPException(400, "Referensi tidak valid")
    orig = await load(body.ref_type, body.ref_id)
    line = next((l for l in orig["lines"] if l["lid"] == body.line_lid and not l.get("removed")), None)
    if not line:
        raise HTTPException(404, "Item nota awal tidak ditemukan")
    if not orig.get("recognized"):
        raise HTTPException(400, "Nota awal belum selesai")
    rd = orig.get("recognized_date")
    until = line.get("warranty_until") or ((date.fromisoformat(rd) + timedelta(days=line.get("warranty_days", 0))).isoformat()
                                           if line.get("warranty_days") and rd else None)
    in_warranty = bool(until and until >= local_date())
    if body.ref_type == "job":
        cust = await get_or_404("customers", orig["customer_id"])
        veh = await db.vehicles.find_one({"id": orig.get("vehicle_id")}, {"_id": 0}) if orig.get("vehicle_id") else None
    else:
        c = orig.get("customer") or {"name": orig.get("customer_name") or "Pelanggan", "phone": orig.get("customer_phone", "")}
        cust = await upsert_customer({"name": c.get("name") or "Pelanggan", "phone": c.get("phone", "")})
        veh = None
    prev = await db.jobs.count_documents({"claim.ref_id": orig["id"], "claim.line_lid": line["lid"]})
    claim = {"ref_type": body.ref_type, "ref_id": orig["id"], "ref_no": orig["no"], "line_lid": line["lid"], "line_name": line["name"],
             "line_detail": line.get("detail", ""), "warranty_until": until, "in_warranty": in_warranty, "symptom": body.symptom[:1000],
             "claim_seq": prev + 1, "inspection": "", "action": "", "technician": "", "claim_notes": "", "old_part": None}
    d = await create_job_doc("garansi", cust, veh, user, f"Klaim garansi: {body.symptom}", "", [], claim)
    await audit(user, "buat_klaim_garansi", "job", d["id"], after={"no": d["no"], "ref": orig["no"], "item": line["name"]})
    return await with_extras("job", await load("job", d["id"]), user)


# ---------- Discount ----------
class DiscountIn(BaseModel):
    amount: int = Field(ge=1)
    reason: str = Field(min_length=3)


def discountable(kind, doc):
    if kind == "job" and doc["status"] != "Masuk":
        raise HTTPException(400, "Diskon hanya untuk nota yang masih Masuk")
    if kind == "order" and (doc.get("stock_applied") or doc["ship_status"] == "Batal"):
        raise HTTPException(400, "Diskon hanya sebelum pesanan diproses")


@router.post("/tx/{kind}/{tid}/discount")
async def request_discount(kind: str, tid: str, body: DiscountIn, user=Depends(require(*STAFF))):
    if kind not in ("job", "order"):
        raise HTTPException(400, "Jenis tidak valid")
    doc = await load(kind, tid)
    discountable(kind, doc)
    if body.amount > doc["subtotal"]:
        raise HTTPException(400, "Diskon melebihi subtotal")
    if totals(doc | {"discount": {"amount": body.amount, "status": "approved"}})["total"] < doc["paid"]:
        raise HTTPException(400, "Total setelah diskon lebih kecil dari uang yang sudah dibayar")
    owner = user["role"] == "owner"
    disc = {"amount": body.amount, "reason": body.reason, "status": "approved" if owner else "pending",
            "requested_by": user["name"], "requested_at": iso(), "decided_by": user["name"] if owner else None,
            "decided_at": iso() if owner else None}
    doc["discount"] = disc
    await db[COLL[kind]].update_one({"id": tid}, {"$set": {"discount": disc}})
    await save_totals(kind, doc)
    await audit(user, "ajukan_diskon", kind, tid, after=disc, reason=body.reason)
    return await with_extras(kind, await load(kind, tid), user)


class DecideIn(BaseModel):
    approve: bool
    note: str = ""


@router.post("/tx/{kind}/{tid}/discount/decide")
async def decide_discount(kind: str, tid: str, body: DecideIn, user=Depends(require("owner"))):
    doc = await load(kind, tid)
    disc = doc.get("discount") or {}
    if disc.get("status") != "pending":
        raise HTTPException(400, "Tidak ada diskon yang menunggu persetujuan")
    discountable(kind, doc)
    if body.approve and totals(doc | {"discount": disc | {"status": "approved"}})["total"] < doc["paid"]:
        raise HTTPException(400, "Total setelah diskon lebih kecil dari uang yang sudah dibayar")
    disc.update(status="approved" if body.approve else "rejected", decided_by=user["name"], decided_at=iso(), decision_note=body.note)
    doc["discount"] = disc
    await db[COLL[kind]].update_one({"id": tid}, {"$set": {"discount": disc}})
    await save_totals(kind, doc)
    await audit(user, "setujui_diskon" if body.approve else "tolak_diskon", kind, tid, after=disc)
    return await with_extras(kind, await load(kind, tid), user)


@router.get("/discounts/pending")
async def pending_discounts(user=Depends(require("owner"))):
    out = []
    for kind in ("job", "order"):
        for d in await find_list(COLL[kind], {"discount.status": "pending"}):
            out.append({"kind": kind, "id": d["id"], "no": d["no"], "customer": d["customer"]["name"],
                        "subtotal": d["subtotal"], "discount": d["discount"]})
    return out


# ---------- Payments ----------
class PayIn(BaseModel):
    amount: int = Field(ge=1)
    method: str
    note: str = ""
    idem_key: str | None = None


async def apply_order_stock(doc, user, reason):
    """Deduct order stock once. Returns True if deducted now, False if already deducted; raises 409 otherwise."""
    locked = await db.orders.find_one_and_update({"id": doc["id"], "stock_applied": False, "lock": {"$ne": True}},
                                                 {"$set": {"lock": True}}, return_document=ReturnDocument.AFTER)
    if not locked:
        cur = await load("order", doc["id"])
        if cur.get("stock_applied"):
            return False
        raise HTTPException(409, "Pesanan sedang diproses oleh permintaan lain. Muat ulang lalu coba lagi.")
    try:
        await move_many(usage(locked), "keluar_pesanan_wa", reason, user, "order", doc["id"], doc["no"])
    except HTTPException:
        await db.orders.update_one({"id": doc["id"]}, {"$set": {"lock": False}})
        raise
    await db.orders.update_one({"id": doc["id"]}, {"$set": {"lock": False, "stock_applied": True, "recognized": True,
                                                            "recognized_date": local_date(), "stock_applied_at": iso()}})
    return True


async def revert_order_stock(doc, user, reason):
    await move_many([(i, -d) for i, d in usage(doc)], "pembatalan_otomatis", reason, user, "order", doc["id"], doc["no"])
    await db.orders.update_one({"id": doc["id"]}, {"$set": {"stock_applied": False, "recognized": False, "recognized_date": None}})


@router.post("/tx/{kind}/{tid}/payments")
async def pay(kind: str, tid: str, body: PayIn, user=Depends(require(*STAFF))):
    if kind not in ("job", "order"):
        raise HTTPException(400, "Jenis tidak valid")
    await load(kind, tid)
    # One payment at a time per nota: balance check + insert happen under this lock (stale after 30 s).
    cutoff = (now() - timedelta(seconds=30)).isoformat()
    stamp = iso()
    got = await db[COLL[kind]].find_one_and_update({"id": tid, "$or": [{"pay_lock": None}, {"pay_lock": {"$lt": cutoff}}]},
                                                   {"$set": {"pay_lock": stamp}})
    if not got:
        if body.idem_key and await db.payments.find_one({"idem_key": body.idem_key}):
            return await with_extras(kind, await load(kind, tid), user)
        raise HTTPException(409, "Pembayaran lain untuk nota ini sedang diproses. Muat ulang lalu periksa sisa tagihan.")
    try:
        return await _pay(kind, tid, body, user)
    finally:
        await db[COLL[kind]].update_one({"id": tid, "pay_lock": stamp}, {"$set": {"pay_lock": None}})


async def _pay(kind, tid, body, user):
    doc = await load(kind, tid)
    if body.idem_key and await db.payments.find_one({"idem_key": body.idem_key}):
        return await with_extras(kind, doc, user)
    if kind == "job" and doc["status"] == "Batal" or kind == "order" and doc["ship_status"] in ("Batal", "Kembali"):
        raise HTTPException(400, "Transaksi sudah dibatalkan")
    if (doc.get("discount") or {}).get("status") == "pending":
        raise HTTPException(400, "Diskon masih menunggu persetujuan owner")
    remaining = doc["total"] - doc["paid"]
    if body.amount > remaining:
        raise HTTPException(400, f"Pembayaran melebihi sisa tagihan (Rp{remaining:,})".replace(",", "."))
    if kind == "order" and doc["payment_type"] == "cod":
        if body.method != "cod":
            raise HTTPException(400, "Pesanan COD dicatat dengan metode COD saat dana cair")
        if not doc.get("stock_applied"):
            raise HTTPException(400, "Dana COD dicatat setelah paket dikirim")
    elif body.method == "cod":
        raise HTTPException(400, "Metode COD hanya untuk pesanan COD")
    recognized = doc.get("recognized")
    pkind = "cod_cair" if body.method == "cod" else ("pelunasan" if (recognized or body.amount == remaining) and doc["paid"] > 0
                                                       else ("dp" if not recognized and body.amount < remaining else "pembayaran"))
    deducted = False
    if kind == "order" and doc["payment_type"] == "prabayar" and doc["paid"] + body.amount >= doc["total"]:
        # Stock first: if it fails (409) the settling payment is NOT recorded.
        deducted = await apply_order_stock(doc, user, f"Pesanan WA lunas {doc['no']}")
    try:
        p = await add_payment(kind, doc, body.amount, body.method, pkind, user, body.idem_key, body.note)
    except Exception:
        if deducted:
            await revert_order_stock(doc, user, f"Pembayaran gagal dicatat {doc['no']}")
        raise
    if p is None:
        if deducted:
            await revert_order_stock(doc, user, f"Permintaan pembayaran ganda {doc['no']}")
        return await with_extras(kind, await load(kind, tid), user)
    doc = await load(kind, tid)
    if kind == "order" and doc["payment_type"] == "cod" and doc["paid"] >= doc["total"]:
        await db.orders.update_one({"id": tid}, {"$set": {"cod_settled": True, "cod_settled_at": iso()}})
    await audit(user, "catat_pembayaran", kind, tid, after={"amount": body.amount, "method": body.method, "kind": pkind})
    return await with_extras(kind, await load(kind, tid), user)


# ---------- Returns ----------
class ReturnIn(BaseModel):
    items: list[ReturnItem] = []
    refund_amount: int = Field(default=0, ge=0)
    refund_method: str = "tunai"
    reason: str = Field(min_length=3)
    idem_key: str | None = None


RETURN_CONDITIONS = ("layak", "rusak", "belum_kembali")


def outstanding(doc):
    """Qty per item that left stock and has not yet physically come back (layak/rusak)."""
    if not doc.get("stock_applied"):
        return {}
    used = {}
    for iid, d in usage(doc):
        used[iid] = used.get(iid, 0) - d
    for r in doc.get("returns", []):
        for it in r["items"]:
            if it["condition"] != "belum_kembali":
                used[it["item_id"]] = used.get(it["item_id"], 0) - it["qty"]
    return {k: v for k, v in used.items() if v > 0}


async def process_return(kind, doc, body, user, label="Retur"):
    if body.idem_key and any(r.get("idem_key") == body.idem_key for r in doc.get("returns", [])):
        return
    if not doc.get("stock_applied") and body.items:
        raise HTTPException(400, "Barang belum keluar dari stok")
    used = outstanding(doc)
    req = {}
    for it in body.items:
        if it.condition not in RETURN_CONDITIONS:
            raise HTTPException(400, "Kondisi harus layak, rusak, atau belum_kembali")
        req[it.item_id] = req.get(it.item_id, 0) + it.qty
    for iid, q in req.items():
        if q > used.get(iid, 0):
            raise HTTPException(400, "Jumlah retur melebihi barang yang keluar")
    if body.refund_amount > doc["paid"] - doc.get("refunded", 0):
        raise HTTPException(400, "Pengembalian uang melebihi uang yang diterima")
    good = [(i.item_id, i.qty) for i in body.items if i.condition == "layak"]
    await move_many(good, "retur_masuk", f"{label} {doc['no']} (layak jual): {body.reason}", user, kind, doc["id"], doc["no"])
    names = {i["id"]: i["name"] for i in await find_list("items", {"id": {"$in": [x.item_id for x in body.items]}})}
    for i in body.items:
        if i.condition == "rusak":
            await record_damage(i.item_id, names.get(i.item_id, "?"), i.qty, "retur", f"{label} {doc['no']} (rusak): {body.reason}",
                                user, False, kind, doc["id"], doc["no"], "rusak")
    if body.refund_amount:
        await add_payment(kind, doc, body.refund_amount, body.refund_method, "refund", user, None, f"{label}: {body.reason}", "out")
    physical = [i for i in body.items if i.condition != "belum_kembali"]
    write_off = 0
    if kind == "order" and physical and doc["payment_type"] == "cod" and not doc.get("cod_settled") and not doc.get("written_off"):
        write_off = max(doc["total"] - doc.get("shipping_cost", 0) - doc["paid"], 0)
        await db.orders.update_one({"id": doc["id"]}, {"$set": {"written_off": write_off}})
    rec = {"id": new_id(), "items": [i.model_dump() | {"name": names.get(i.item_id)} for i in body.items], "refund": body.refund_amount,
           "write_off": write_off,
           "refund_method": body.refund_method, "reason": body.reason, "by": user["name"], "at": iso(), "date_local": local_date(),
           "idem_key": body.idem_key}
    await db[COLL[kind]].update_one({"id": doc["id"]}, {"$push": {"returns": rec}})
    await audit(user, "retur", kind, doc["id"], after=rec, reason=body.reason)


@router.post("/tx/{kind}/{tid}/return")
async def tx_return(kind: str, tid: str, body: ReturnIn, user=Depends(require(*MANAGERS))):
    if kind not in COLL:
        raise HTTPException(400, "Jenis tidak valid")
    doc = await load(kind, tid)
    if kind == "job" and doc["status"] != "Selesai":
        raise HTTPException(400, "Retur hanya untuk nota Selesai")
    if kind == "order" and doc["ship_status"] == "Baru":
        raise HTTPException(400, "Pesanan belum dikirim. Gunakan Batalkan pesanan.")
    if any(i.condition == "belum_kembali" for i in body.items):
        raise HTTPException(400, "Pada retur, catat hanya barang yang benar-benar kembali (layak/rusak)")
    await process_return(kind, doc, body, user)
    if kind == "order" and body.items and doc["ship_status"] != "Batal":
        await db.orders.update_one({"id": tid}, {"$set": {"ship_status": "Kembali"}})
    return await with_extras(kind, await load(kind, tid), user)


# ---------- Direct sales ----------
class SaleLine(BaseModel):
    item_id: str
    qty: int = Field(ge=1, le=999)


class SaleIn(BaseModel):
    customer_name: str = ""
    customer_phone: str = ""
    lines: list[SaleLine] = Field(min_length=1)
    method: str
    cash_received: int | None = None
    discount: DiscountIn | None = None
    idem_key: str = Field(min_length=8)


@router.post("/sales")
async def create_sale(body: SaleIn, user=Depends(require(*STAFF))):
    ex = await db.sales.find_one({"idem_key": body.idem_key}, {"_id": 0})
    if ex:
        return await with_extras("sale", ex, user)
    if body.method not in ("tunai", "transfer"):
        raise HTTPException(400, "Metode harus tunai atau transfer")
    if body.discount and user["role"] != "owner":
        raise HTTPException(403, "Diskon penjualan langsung hanya dapat diberikan owner")
    lines = [await build_line(LineIn(type="item", item_id=l.item_id, qty=l.qty), user) for l in body.lines]
    d = {"id": new_id(), "no": await next_number("PJ"), "idem_key": body.idem_key, "status": "proses",
         "customer_name": body.customer_name.strip()[:100], "customer_phone": norm_phone(body.customer_phone), "lines": lines,
         "discount": ({"amount": body.discount.amount, "reason": body.discount.reason, "status": "approved", "requested_by": user["name"],
                       "decided_by": user["name"], "decided_at": iso()} if body.discount else None),
         "method": body.method, "paid": 0, "refunded": 0, "returns": [], "stock_applied": False, "recognized": False,
         "public_token": token(), "created_by": user["name"], "created_at": iso(), "date_local": local_date()}
    d |= totals(d)
    if body.method == "tunai" and body.cash_received is not None:
        if body.cash_received < d["total"]:
            raise HTTPException(400, "Uang diterima kurang dari total")
        d["cash_received"], d["change"] = body.cash_received, body.cash_received - d["total"]
    try:
        await db.sales.insert_one(d)
    except DuplicateKeyError:
        return await with_extras("sale", await db.sales.find_one({"idem_key": body.idem_key}, {"_id": 0}), user)
    try:
        await move_many(usage(d), "keluar_penjualan", f"Penjualan langsung {d['no']}", user, "sale", d["id"], d["no"])
    except HTTPException:
        await db.sales.delete_one({"id": d["id"]})
        raise
    if d["total"] > 0:
        await add_payment("sale", d, d["total"], body.method, "pembayaran", user, f"sale-{body.idem_key}")
    await db.sales.update_one({"id": d["id"]}, {"$set": {"status": "Lunas", "stock_applied": True, "recognized": True,
                                                         "recognized_date": local_date()}})
    return await with_extras("sale", await load("sale", d["id"]), user)


@router.get("/sales")
async def list_sales(q: str = "", date_from: str | None = None, date_to: str | None = None, user=Depends(require(*STAFF))):
    f = {"status": {"$ne": "proses"}}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        f["$or"] = [{"no": rx}, {"customer_name": rx}]
    if date_from or date_to:
        f["date_local"] = {k: v for k, v in (("$gte", date_from), ("$lte", date_to)) if v}
    return strip_cost(await find_list("sales", f, [("created_at", -1)], 1000), user)


@router.get("/sales/{sid}")
async def get_sale(sid: str, user=Depends(require(*STAFF))):
    return await with_extras("sale", await load("sale", sid), user)


# ---------- WhatsApp orders ----------
class OrderIn(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    customer_phone: str = Field(min_length=6)
    address: str = ""
    province: str = ""
    delivery: str = "kurir"
    courier: str = "J&T"
    shipping_cost: int = Field(default=0, ge=0)
    payment_type: str = "prabayar"
    lines: list[LineIn] = Field(min_length=1)
    notes: str = ""


def validate_order(body):
    if body.delivery not in ("kurir", "ambil"):
        raise HTTPException(400, "Pengiriman tidak valid")
    if body.payment_type not in ("prabayar", "cod"):
        raise HTTPException(400, "Jenis pembayaran tidak valid")
    if body.delivery == "kurir":
        if not body.province:
            raise HTTPException(400, "Provinsi tujuan wajib dipilih")
        if not body.address.strip():
            raise HTTPException(400, "Alamat tujuan wajib diisi")
    if body.payment_type == "cod":
        if body.delivery != "kurir":
            raise HTTPException(400, "COD hanya untuk pengiriman kurir")
        if body.province not in JAVA:
            raise HTTPException(400, "COD hanya tersedia untuk tujuan Pulau Jawa. Tujuan luar Jawa wajib bayar di muka.")


@router.post("/orders")
async def create_order(body: OrderIn, user=Depends(require(*STAFF))):
    validate_order(body)
    lines = [await build_line(l, user) for l in body.lines]
    d = {"id": new_id(), "no": await next_number("WA"), "customer": {"name": body.customer_name.strip(), "phone": norm_phone(body.customer_phone)},
         "address": body.address[:500], "province": body.province, "is_java": body.province in JAVA, "delivery": body.delivery,
         "courier": body.courier[:30] if body.delivery == "kurir" else "", "resi": "",
         "shipping_cost": body.shipping_cost if body.delivery == "kurir" else 0, "payment_type": body.payment_type,
         "lines": lines, "discount": None, "notes": body.notes[:1000], "ship_status": "Baru", "paid": 0, "refunded": 0,
         "stock_applied": False, "recognized": False, "cod_settled": False, "returns": [], "public_token": token(),
         "created_by": user["name"], "created_at": iso(), "date_local": local_date()}
    d |= totals(d)
    await db.orders.insert_one(d)
    await audit(user, "buat_pesanan_wa", "order", d["id"], after={"no": d["no"], "total": d["total"]})
    return await with_extras("order", await load("order", d["id"]), user)


@router.get("/orders")
async def list_orders(q: str = "", status: str | None = None, cod_pending: bool = False, user=Depends(require(*STAFF))):
    f = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        f["$or"] = [{"no": rx}, {"customer.name": rx}, {"resi": rx}]
    if status:
        f["ship_status"] = status
    if cod_pending:
        f |= {"payment_type": "cod", "stock_applied": True, "cod_settled": False, "ship_status": {"$nin": ["Batal", "Kembali"]}}
    return strip_cost(await find_list("orders", f, [("created_at", -1)], 1000), user)


@router.get("/orders/{oid}")
async def get_order(oid: str, user=Depends(require(*STAFF))):
    return await with_extras("order", await load("order", oid), user)


class OrderPatch(BaseModel):
    address: str | None = None
    resi: str | None = None
    courier: str | None = None
    notes: str | None = None
    shipping_cost: int | None = Field(default=None, ge=0)
    lines: list[LineIn] | None = None


@router.patch("/orders/{oid}")
async def patch_order(oid: str, body: OrderPatch, user=Depends(require(*STAFF))):
    doc = await load("order", oid)
    if doc["ship_status"] in ("Batal", "Kembali"):
        raise HTTPException(400, "Pesanan sudah ditutup")
    upd = {k: v for k, v in body.model_dump(exclude={"lines"}).items() if v is not None}
    if (body.lines is not None or body.shipping_cost is not None) and (doc["stock_applied"] or doc["paid"] > 0):
        raise HTTPException(400, "Barang/ongkir tidak dapat diubah setelah ada pembayaran atau barang diproses")
    if body.lines is not None:
        if not body.lines:
            raise HTTPException(400, "Minimal satu barang")
        doc["lines"] = [await build_line(l, user) for l in body.lines]
    doc |= upd
    await db.orders.update_one({"id": oid}, {"$set": upd})
    await save_totals("order", doc, body.lines is not None)
    await audit(user, "ubah_pesanan_wa", "order", oid, after={k: v for k, v in upd.items()} | ({"lines": "diganti"} if body.lines else {}))
    return await with_extras("order", await load("order", oid), user)


class ShipIn(BaseModel):
    resi: str = ""


@router.post("/orders/{oid}/ship")
async def ship_order(oid: str, body: ShipIn, user=Depends(require(*STAFF))):
    doc = await load("order", oid)
    if doc["ship_status"] != "Baru":
        if doc["ship_status"] in ("Dikirim", "Diambil"):
            return await with_extras("order", doc, user)
        raise HTTPException(400, "Status pesanan tidak dapat dikirim")
    if (doc.get("discount") or {}).get("status") == "pending":
        raise HTTPException(400, "Diskon masih menunggu persetujuan owner")
    if doc["payment_type"] == "prabayar" and doc["paid"] < doc["total"]:
        raise HTTPException(400, "Pesanan prabayar harus lunas sebelum dikirim/diambil")
    if doc["payment_type"] == "prabayar" and not doc.get("stock_applied"):
        await apply_order_stock(doc, user, f"Pesanan WA lunas {doc['no']} (pemotongan stok tertunda)")
    if doc["payment_type"] == "cod":
        await apply_order_stock(doc, user, f"Pesanan COD dikirim {doc['no']}")
    if not (await load("order", oid)).get("stock_applied"):
        raise HTTPException(409, "Stok pesanan belum berhasil dipotong. Pesanan tidak dapat dikirim.")
    status = "Diambil" if doc["delivery"] == "ambil" else "Dikirim"
    upd = {"ship_status": status, "shipped_at": iso(), "shipped_by": user["name"]}
    if body.resi:
        upd["resi"] = body.resi[:60]
    await db.orders.update_one({"id": oid, "ship_status": "Baru"}, {"$set": upd})
    await audit(user, "kirim_pesanan", "order", oid, after=upd)
    return await with_extras("order", await load("order", oid), user)


@router.post("/orders/{oid}/delivered")
async def order_delivered(oid: str, user=Depends(require(*STAFF))):
    doc = await load("order", oid)
    if doc["ship_status"] != "Dikirim":
        raise HTTPException(400, "Pesanan belum berstatus Dikirim")
    await db.orders.update_one({"id": oid}, {"$set": {"ship_status": "Diterima", "delivered_at": iso()}})
    return await with_extras("order", await load("order", oid), user)


@router.post("/orders/{oid}/cancel")
async def cancel_order(oid: str, body: CancelIn, user=Depends(require("owner"))):
    stamp = iso()
    cutoff = (now() - timedelta(seconds=30)).isoformat()
    locked = await db.orders.find_one_and_update(
        {"id": oid, "ship_status": "Baru", "lock": {"$ne": True}, "$or": [{"pay_lock": None}, {"pay_lock": {"$lt": cutoff}}]},
        {"$set": {"lock": True, "pay_lock": stamp}})
    if not locked:
        doc = await load("order", oid)
        if doc["ship_status"] != "Baru":
            raise HTTPException(400, "Pesanan yang sudah dikirim/dibatalkan dicatat lewat 'Paket kembali/Retur'")
        raise HTTPException(409, "Pesanan sedang diproses. Muat ulang lalu coba lagi.")
    try:
        doc = await load("order", oid)
        await _cancel_order(doc, body, user)
    finally:
        await db.orders.update_one({"id": oid}, {"$set": {"lock": False, "pay_lock": None}})
    await audit(user, "batal_pesanan", "order", oid, after={"refund": body.refund_amount, "items": [i.model_dump() for i in body.items]}, reason=body.reason)
    return await with_extras("order", await load("order", oid), user)


async def _cancel_order(doc, body, user):
    oid = doc["id"]
    out = outstanding(doc)
    req = {}
    for i in body.items:
        if i.condition not in RETURN_CONDITIONS:
            raise HTTPException(400, "Setiap barang harus berstatus layak, rusak, atau belum_kembali dengan jumlah ≥ 1")
        req[i.item_id] = req.get(i.item_id, 0) + i.qty
    if req != out:
        names = {x["id"]: x["name"] for x in await find_list("items", {"id": {"$in": list(set(out) | set(req))}})}
        diff = ", ".join(f"{names.get(k, k)}: keluar {out.get(k, 0)}, dicatat {req.get(k, 0)}" for k in sorted(set(out) | set(req))
                         if out.get(k, 0) != req.get(k, 0))
        raise HTTPException(400, f"Semua barang yang sudah keluar dari stok harus dicatat (layak / rusak / belum kembali). Selisih: {diff}")
    if doc.get("stock_applied"):
        await process_return("order", doc, ReturnIn(items=list(body.items), refund_amount=body.refund_amount, refund_method=body.refund_method,
                                                    reason=body.reason, idem_key=body.idem_key), user, "Batal")
    elif body.refund_amount:
        if body.refund_amount > doc["paid"] - doc["refunded"]:
            raise HTTPException(400, "Pengembalian melebihi uang yang diterima")
        await add_payment("order", doc, body.refund_amount, body.refund_method, "refund", user, body.idem_key, f"Batal: {body.reason}", "out")
    doc = await load("order", oid)
    not_back = [{"item_id": i.item_id, "qty": i.qty} for i in body.items if i.condition == "belum_kembali"]
    await db.orders.update_one({"id": oid}, {"$set": {"ship_status": "Batal", "cancel": {
        "reason": body.reason, "refund": body.refund_amount, "kept": doc["paid"] - doc["refunded"], "by": user["name"], "at": iso(),
        "date_local": local_date(), "items": [i.model_dump() for i in body.items], "items_not_returned": not_back}}})


# ---------- Public receipt ----------
@router.get("/public/nota/{tok}")
async def public_nota(tok: str):
    if len(tok) < 20:
        raise HTTPException(404, "Nota tidak ditemukan")
    for kind, coll in COLL.items():
        d = await db[coll].find_one({"public_token": tok}, {"_id": 0})
        if d and d.get("status") != "proses":
            name = (d.get("customer") or {}).get("name") or d.get("customer_name") or ""
            return {"kind": kind, "no": d["no"], "date": d["created_at"], "customer_name": name,
                    "plate": (d.get("vehicle") or {}).get("plate"), "status": d.get("status") or d.get("ship_status"),
                    "lines": [{k: l.get(k) for k in ("name", "detail", "options", "qty", "unit_price", "subtotal", "warranty_until")}
                              for l in d["lines"] if not l.get("removed")],
                    "subtotal": d["subtotal"], "discount_amount": d["discount_amount"], "shipping_cost": d.get("shipping_cost", 0),
                    "total": d["total"], "paid": d["paid"], "refunded": d.get("refunded", 0), "remaining": max(d["total"] - d["paid"], 0)}
    raise HTTPException(404, "Nota tidak ditemukan")
