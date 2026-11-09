from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from core import db, iso, new_id, find_list, get_or_404, require, audit

router = APIRouter(prefix="/api")
OWNER = require("owner")
TX = (("jobs", "nota pekerjaan bengkel/klaim garansi"), ("sales", "penjualan langsung"), ("orders", "pesanan WhatsApp"))
# Mutasi yang boleh tetap ada setelah barang dihapus (tetap terbaca lewat SKU/nama + arsip). Selain ini = riwayat transaksi.
SAFE_MUTATIONS = ("stok_awal", "masuk", "opname", "koreksi")


class ActiveIn(BaseModel):
    active: bool


async def _archive(user, ref_type, doc, extra=None):
    await db.deleted_records.insert_one({"id": new_id(), "ref_type": ref_type, "ref_id": doc["id"], "name": doc.get("name"),
                                         "data": doc, "extra": extra, "deleted_by": user["name"], "deleted_by_id": user["id"],
                                         "deleted_at": iso()})


async def package_blockers(p):
    reasons = []
    for coll, label in (("jobs", "nota pekerjaan bengkel"), ("orders", "pesanan WhatsApp")):
        n = await db[coll].count_documents({"lines.package_id": p["id"]})
        if n:
            reasons.append(f"Paket dipakai pada {n} {label} (semua status). Nonaktifkan saja agar tidak bisa dipilih lagi.")
    return reasons


async def item_blockers(it):
    iid, reasons = it["id"], []
    q = {"$or": [{"lines.item_id": iid}, {"lines.components.item_id": iid}, {"returns.items.item_id": iid}, {"claim.old_part.item_id": iid}]}
    for coll, label in TX:
        n = await db[coll].count_documents(q)
        if n:
            reasons.append(f"Dipakai pada {n} {label} (semua status)")
    n = await db.damaged.count_documents({"item_id": iid})
    if n:
        reasons.append(f"Tercatat pada {n} catatan barang rusak")
    n = await db.stock_mutations.count_documents({"item_id": iid, "kind": {"$nin": list(SAFE_MUTATIONS)}})
    if n:
        reasons.append(f"Punya {n} riwayat mutasi stok dari transaksi/pemakaian yang harus dipertahankan")
    pk = await find_list("packages", {"$or": [{"components.item_id": iid}, {"options.items.item_id": iid}, {"options.replaces": iid}]})
    packages = [{"id": p["id"], "name": p["name"], "can_delete": not await package_blockers(p)} for p in pk]
    for p in packages:
        reasons.append(f"Varian dipakai Paket {p['name']} (komponen dasar/opsi). " +
                       ("Hapus paket itu terlebih dahulu." if p["can_delete"] else "Paket itu sudah dipakai transaksi, jadi ubah komponennya atau Nonaktifkan barang ini."))
    if it.get("stock", 0) > 0:
        reasons.append(f"Masih memiliki stok {it['stock']} pcs. Nolkan dulu lewat Koreksi stok/Opname (tercatat di mutasi) atau Nonaktifkan.")
    return reasons, packages


async def user_blockers(u, me):
    reasons = []
    if u["id"] == me["id"]:
        reasons.append("Tidak dapat menghapus akun yang sedang Anda pakai")
    if u["role"] == "owner" and await db.users.count_documents({"role": "owner"}) <= 1:
        reasons.append("Ini akun owner terakhir")
    name, uid = u["name"], u["id"]
    q = {"$or": [{"created_by_id": uid}, {"completed_by_id": uid}, {"created_by": name}, {"completed_by": name}, {"lines.added_by": name}]}
    n = sum([await db[c].count_documents(q) for c, _ in TX])
    if n:
        reasons.append(f"Pengguna tercatat pada {n} transaksi")
    m = sum([await db[c].count_documents({"user_id": uid}) for c in ("payments", "stock_mutations", "expenses", "damaged")])
    if m:
        reasons.append(f"Pengguna tercatat pada {m} catatan pembayaran/stok/biaya")
    return reasons


def _check(name, reasons, **extra):
    return {"name": name, "can_delete": not reasons, "reasons": reasons, **extra}


def _confirm(name, confirm):
    if (confirm or "").strip() != name:
        raise HTTPException(400, f"Ketik nama persis untuk konfirmasi: {name}")


@router.get("/admin/delete-check/{kind}/{rid}")
async def delete_check(kind: str, rid: str, user=Depends(OWNER)):
    if kind == "item":
        it = await get_or_404("items", rid, "Barang tidak ditemukan")
        reasons, packages = await item_blockers(it)
        if await db.items.count_documents({"product_id": it.get("product_id")}) <= 1:
            reasons.append("Ini satu-satunya barang di produk ini. Gunakan Hapus Produk.")
        return _check(it["name"], reasons, packages=packages)
    if kind == "product":
        p = await get_or_404("products", rid, "Produk tidak ditemukan")
        variants = await find_list("items", {"product_id": rid})
        reasons, packages = [], []
        for v in variants:
            r, pk = await item_blockers(v)
            reasons += [f"{v['name']} ({v['sku']}): {x}" for x in r]
            packages += [x for x in pk if x["id"] not in {y["id"] for y in packages}]
        return _check(p["name"], reasons, packages=packages, variant_count=len(variants))
    if kind == "package":
        p = await get_or_404("packages", rid, "Paket tidak ditemukan")
        return _check(p["name"], await package_blockers(p))
    if kind == "user":
        u = await get_or_404("users", rid, "Pengguna tidak ditemukan")
        return _check(u["name"], await user_blockers(u, user), email=u["email"])
    raise HTTPException(400, "Jenis data tidak valid")


async def _delete_item(it, user):
    res = await db.items.delete_one({"id": it["id"], "stock": 0})
    if not res.deleted_count:
        raise HTTPException(409, "Stok barang berubah. Muat ulang lalu periksa lagi.")
    await _archive(user, "item", it, {"mutations_kept": await db.stock_mutations.count_documents({"item_id": it["id"]})})


@router.delete("/items/{iid}")
async def delete_item(iid: str, confirm: str = "", user=Depends(OWNER)):
    it = await get_or_404("items", iid, "Barang tidak ditemukan")
    _confirm(it["name"], confirm)
    reasons, _ = await item_blockers(it)
    if await db.items.count_documents({"product_id": it.get("product_id")}) <= 1:
        reasons.append("Ini satu-satunya barang di produk ini. Gunakan Hapus Produk.")
    if reasons:
        raise HTTPException(409, "Tidak dapat dihapus: " + "; ".join(reasons))
    await _delete_item(it, user)
    await audit(user, "hapus_varian", "item", iid, before={"sku": it["sku"], "name": it["name"]})
    return {"ok": True}


@router.delete("/products/{pid}")
async def delete_product(pid: str, confirm: str = "", user=Depends(OWNER)):
    p = await get_or_404("products", pid, "Produk tidak ditemukan")
    _confirm(p["name"], confirm)
    variants = await find_list("items", {"product_id": pid})
    reasons = []
    for v in variants:
        reasons += [f"{v['name']} ({v['sku']}): {x}" for x in (await item_blockers(v))[0]]
    if reasons:
        raise HTTPException(409, "Tidak dapat dihapus: " + "; ".join(reasons))
    for v in variants:
        await _delete_item(v, user)
    await db.products.delete_one({"id": pid})
    await _archive(user, "product", p, {"variants": [v["sku"] for v in variants]})
    await audit(user, "hapus_produk", "product", pid, before={"code": p["code"], "name": p["name"], "variants": [v["sku"] for v in variants]})
    return {"ok": True, "variants_deleted": len(variants)}


@router.delete("/packages/{pid}")
async def delete_package(pid: str, confirm: str = "", user=Depends(OWNER)):
    p = await get_or_404("packages", pid, "Paket tidak ditemukan")
    _confirm(p["name"], confirm)
    reasons = await package_blockers(p)
    if reasons:
        raise HTTPException(409, "Tidak dapat dihapus: " + "; ".join(reasons))
    await db.packages.delete_one({"id": pid})
    await _archive(user, "package", p)
    await audit(user, "hapus_paket", "package", pid, before={"name": p["name"], "price": p["price"]})
    return {"ok": True}


@router.delete("/users/{uid}")
async def delete_user(uid: str, confirm: str = "", user=Depends(OWNER)):
    u = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})
    if not u:
        raise HTTPException(404, "Pengguna tidak ditemukan")
    _confirm(u["name"], confirm)
    reasons = await user_blockers(u, user)
    if reasons:
        raise HTTPException(409, "Tidak dapat dihapus: " + "; ".join(reasons))
    await db.users.delete_one({"id": uid})
    await _archive(user, "user", u)
    await audit(user, "hapus_pengguna", "user", uid, before={"email": u["email"], "name": u["name"], "role": u["role"]})
    return {"ok": True}


@router.post("/products/{pid}/active")
async def set_product_active(pid: str, body: ActiveIn, user=Depends(OWNER)):
    p = await get_or_404("products", pid, "Produk tidak ditemukan")
    await db.products.update_one({"id": pid}, {"$set": {"active": body.active}})
    await db.items.update_many({"product_id": pid}, {"$set": {"active": body.active}})
    await audit(user, "aktifkan_produk" if body.active else "nonaktifkan_produk", "product", pid, before={"active": p.get("active")},
                after={"active": body.active})
    return {"ok": True}


@router.post("/items/{iid}/active")
async def set_item_active(iid: str, body: ActiveIn, user=Depends(OWNER)):
    it = await get_or_404("items", iid, "Barang tidak ditemukan")
    await db.items.update_one({"id": iid}, {"$set": {"active": body.active}})
    await audit(user, "aktifkan_varian" if body.active else "nonaktifkan_varian", "item", iid, before={"active": it.get("active")},
                after={"active": body.active})
    return {"ok": True}


@router.post("/packages/{pid}/active")
async def set_package_active(pid: str, body: ActiveIn, user=Depends(OWNER)):
    p = await get_or_404("packages", pid, "Paket tidak ditemukan")
    await db.packages.update_one({"id": pid}, {"$set": {"active": body.active}})
    await audit(user, "aktifkan_paket" if body.active else "nonaktifkan_paket", "package", pid, before={"active": p.get("active")},
                after={"active": body.active})
    return {"ok": True}
