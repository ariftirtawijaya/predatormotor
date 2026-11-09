import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from pymongo.errors import PyMongoError
from core import db, client, iso, new_id, find_list, get_or_404, require, audit, is_replica_set

router = APIRouter(prefix="/api")
OWNER = require("owner")
TX = (("jobs", "nota pekerjaan bengkel/klaim garansi"), ("sales", "penjualan langsung"), ("orders", "pesanan WhatsApp"))
# Mutasi yang boleh tetap ada setelah barang dihapus (tetap terbaca lewat SKU/nama + arsip). Selain ini = riwayat transaksi.
SAFE_MUTATIONS = ("stok_awal", "masuk", "opname", "koreksi")


class ActiveIn(BaseModel):
    active: bool


async def _archive(user, ref_type, doc, extra=None, session=None):
    await db.deleted_records.insert_one({"id": new_id(), "ref_type": ref_type, "ref_id": doc["id"], "name": doc.get("name"),
                                         "data": doc, "extra": extra, "deleted_by": user["name"], "deleted_by_id": user["id"],
                                         "deleted_at": iso()}, session=session)


def _fault(stage):
    if os.environ.get("DELETE_TEST_FAIL_AT") == stage and os.environ.get("DB_NAME", "").startswith("predator_pytest_"):
        raise RuntimeError(f"Kegagalan buatan (uji) pada tahap {stage}")


async def _in_transaction(fn):
    """Hapus produk/varian + arsip + audit: berhasil seluruhnya atau batal seluruhnya."""
    if not await is_replica_set():
        raise HTTPException(503, "Penghapusan barang membutuhkan MongoDB mode replica set (transaksi). Tidak ada data yang dihapus. Lihat README.")
    try:
        async with await client.start_session() as s:
            return await s.with_transaction(fn)
    except HTTPException:
        raise
    except (PyMongoError, RuntimeError):
        raise HTTPException(500, "Penghapusan gagal di tengah proses. Seluruh perubahan dibatalkan — tidak ada data yang terhapus.")


async def package_blockers(p, session=None):
    reasons = []
    for coll, label in (("jobs", "nota pekerjaan bengkel"), ("orders", "pesanan WhatsApp")):
        n = await db[coll].count_documents({"lines.package_id": p["id"]}, session=session)
        if n:
            reasons.append(f"Paket dipakai pada {n} {label} (semua status). Nonaktifkan saja agar tidak bisa dipilih lagi.")
    return reasons


async def item_blockers(it, session=None):
    iid, reasons = it["id"], []
    q = {"$or": [{"lines.item_id": iid}, {"lines.components.item_id": iid}, {"returns.items.item_id": iid}, {"claim.old_part.item_id": iid}]}
    for coll, label in TX:
        n = await db[coll].count_documents(q, session=session)
        if n:
            reasons.append(f"Dipakai pada {n} {label} (semua status)")
    n = await db.damaged.count_documents({"item_id": iid}, session=session)
    if n:
        reasons.append(f"Tercatat pada {n} catatan barang rusak")
    n = await db.stock_mutations.count_documents({"item_id": iid, "kind": {"$nin": list(SAFE_MUTATIONS)}}, session=session)
    if n:
        reasons.append(f"Punya {n} riwayat mutasi stok dari transaksi/pemakaian yang harus dipertahankan")
    pk = await db.packages.find({"$or": [{"components.item_id": iid}, {"options.items.item_id": iid}, {"options.replaces": iid}]},
                                {"_id": 0}, session=session).to_list(500)
    packages = [{"id": p["id"], "name": p["name"], "can_delete": not await package_blockers(p, session)} for p in pk]
    for p in packages:
        reasons.append(f"Varian dipakai Paket {p['name']} (komponen dasar/opsi). " +
                       ("Hapus paket itu terlebih dahulu." if p["can_delete"] else "Paket itu sudah dipakai transaksi, jadi ubah komponennya atau Nonaktifkan barang ini."))
    if it.get("stock", 0) > 0:
        reasons.append(f"Masih memiliki stok {it['stock']} pcs. Nolkan dulu lewat Koreksi stok/Opname (tercatat di mutasi) atau Nonaktifkan.")
    return reasons, packages


async def user_blockers(u, me, session=None):
    reasons = []
    if u["id"] == me["id"]:
        reasons.append("Tidak dapat menghapus akun yang sedang Anda pakai")
    if u["role"] == "owner" and not await db.users.count_documents({"role": "owner", "active": True, "id": {"$ne": u["id"]}}, session=session):
        reasons.append("Ini akun owner terakhir")
    name, uid = u["name"], u["id"]
    q = {"$or": [{"created_by_id": uid}, {"completed_by_id": uid}, {"created_by": name}, {"completed_by": name}, {"lines.added_by": name}]}
    n = sum([await db[c].count_documents(q, session=session) for c, _ in TX])
    if n:
        reasons.append(f"Pengguna tercatat pada {n} transaksi")
    m = sum([await db[c].count_documents({"user_id": uid}, session=session) for c in ("payments", "stock_mutations", "expenses", "damaged")])
    if m:
        reasons.append(f"Pengguna tercatat pada {m} catatan pembayaran/stok/biaya")
    return reasons


async def _still_owner(user, session):
    """Hak akses diperiksa ulang di dalam transaksi (akun bisa dinonaktifkan/dihapus sejak request dimulai)."""
    me = await db.users.find_one({"id": user["id"]}, {"_id": 0, "role": 1, "active": 1}, session=session)
    if not me or me.get("role") != "owner" or not me.get("active", True):
        raise HTTPException(403, "Hanya owner aktif yang dapat menghapus data")


async def _lock(key, user, session):
    await db.locks.update_one({"key": key}, {"$set": {"at": iso(), "by": user["id"]}}, upsert=True, session=session)


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


async def _delete_item(it, user, session):
    res = await db.items.delete_one({"id": it["id"], "stock": 0}, session=session)
    if not res.deleted_count:
        raise HTTPException(409, "Stok barang berubah. Muat ulang lalu periksa lagi.")
    _fault("after_item_delete")
    await _archive(user, "item", it, {"mutations_kept": await db.stock_mutations.count_documents({"item_id": it["id"]}, session=session)}, session)


async def _item_reasons(it, session):
    reasons, _ = await item_blockers(it, session)
    if await db.items.count_documents({"product_id": it.get("product_id")}, session=session) <= 1:
        reasons.append("Ini satu-satunya barang di produk ini. Gunakan Hapus Produk.")
    return reasons


@router.delete("/items/{iid}")
async def delete_item(iid: str, confirm: str = "", user=Depends(OWNER)):
    it = await get_or_404("items", iid, "Barang tidak ditemukan")
    _confirm(it["name"], confirm)
    reasons = await _item_reasons(it, None)
    if reasons:
        raise HTTPException(409, "Tidak dapat dihapus: " + "; ".join(reasons))

    async def run(s):
        await _still_owner(user, s)
        cur = await db.items.find_one({"id": iid}, {"_id": 0}, session=s)
        if not cur:
            raise HTTPException(404, "Barang sudah tidak ada")
        again = await _item_reasons(cur, s)
        if again:
            raise HTTPException(409, "Tidak dapat dihapus: " + "; ".join(again))
        await _delete_item(cur, user, s)
        _fault("before_audit")
        await audit(user, "hapus_varian", "item", iid, before={"sku": cur["sku"], "name": cur["name"]}, session=s)

    await _in_transaction(run)
    return {"ok": True}


async def _product_reasons(variants, session):
    reasons = []
    for v in variants:
        reasons += [f"{v['name']} ({v['sku']}): {x}" for x in (await item_blockers(v, session))[0]]
    return reasons


@router.delete("/products/{pid}")
async def delete_product(pid: str, confirm: str = "", user=Depends(OWNER)):
    p = await get_or_404("products", pid, "Produk tidak ditemukan")
    _confirm(p["name"], confirm)
    reasons = await _product_reasons(await find_list("items", {"product_id": pid}), None)
    if reasons:
        raise HTTPException(409, "Tidak dapat dihapus: " + "; ".join(reasons))

    async def run(s):
        await _still_owner(user, s)
        variants = await db.items.find({"product_id": pid}, {"_id": 0}, session=s).to_list(1000)
        again = await _product_reasons(variants, s)
        if again:
            raise HTTPException(409, "Tidak dapat dihapus: " + "; ".join(again))
        for v in variants:
            await _delete_item(v, user, s)
        _fault("after_variants")
        if not (await db.products.delete_one({"id": pid}, session=s)).deleted_count:
            raise HTTPException(404, "Produk sudah tidak ada")
        await _archive(user, "product", p, {"variants": [v["sku"] for v in variants]}, s)
        _fault("before_audit")
        await audit(user, "hapus_produk", "product", pid, before={"code": p["code"], "name": p["name"], "variants": [v["sku"] for v in variants]},
                    session=s)
        return len(variants)

    return {"ok": True, "variants_deleted": await _in_transaction(run)}


@router.delete("/packages/{pid}")
async def delete_package(pid: str, confirm: str = "", user=Depends(OWNER)):
    p = await get_or_404("packages", pid, "Paket tidak ditemukan")
    _confirm(p["name"], confirm)
    reasons = await package_blockers(p)
    if reasons:
        raise HTTPException(409, "Tidak dapat dihapus: " + "; ".join(reasons))

    async def run(s):
        await _still_owner(user, s)
        cur = await db.packages.find_one({"id": pid}, {"_id": 0}, session=s)
        if not cur:
            raise HTTPException(404, "Paket sudah tidak ada")
        again = await package_blockers(cur, s)
        if again:
            raise HTTPException(409, "Tidak dapat dihapus: " + "; ".join(again))
        await db.packages.delete_one({"id": pid}, session=s)
        _fault("after_main_delete")
        await _archive(user, "package", cur, session=s)
        _fault("before_audit")
        await audit(user, "hapus_paket", "package", pid, before={"name": cur["name"], "price": cur["price"]}, session=s)

    await _in_transaction(run)
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

    async def run(s):
        await _lock("users_delete", user, s)
        await _still_owner(user, s)
        cur = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0}, session=s)
        if not cur:
            raise HTTPException(404, "Pengguna sudah tidak ada")
        again = await user_blockers(cur, user, s)
        if again:
            raise HTTPException(409, "Tidak dapat dihapus: " + "; ".join(again))
        await db.users.delete_one({"id": uid}, session=s)
        _fault("after_main_delete")
        await _archive(user, "user", cur, session=s)
        _fault("before_audit")
        await audit(user, "hapus_pengguna", "user", uid, before={"email": cur["email"], "name": cur["name"], "role": cur["role"]}, session=s)

    await _in_transaction(run)
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
