import csv
import io
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from core import db, find_list, require, local_date, STAFF, MANAGERS

router = APIRouter(prefix="/api")


def rng(start, end):
    return {"$gte": start, "$lte": end}


async def recognized(coll, start, end):
    return await find_list(coll, {"recognized": True, "recognized_date": rng(start, end)}, [("recognized_date", 1)], 20000)


def omzet_of(kind, d):
    return d["total"] - (d.get("shipping_cost", 0) if kind == "order" else 0)


@router.get("/reports/daily")
async def daily(date: str | None = None, user=Depends(require(*STAFF))):
    day = date or local_date()
    out = {"date": day, "types": {}}
    for kind, coll in (("job", "jobs"), ("sale", "sales"), ("order", "orders")):
        docs = await recognized(coll, day, day)
        out["types"][kind] = {"count": len(docs), "omzet": sum(omzet_of(kind, d) for d in docs)}
    pays = await find_list("payments", {"date_local": day}, limit=20000)
    out["payments_in"] = {m: sum(p["amount"] for p in pays if p["direction"] == "in" and p["method"] == m) for m in ("tunai", "transfer", "cod")}
    out["refunds"] = sum(p["amount"] for p in pays if p["direction"] == "out")
    out["sales"] = [{"id": s["id"], "no": s["no"], "time": s["created_at"], "customer_name": s.get("customer_name"), "total": s["total"],
                     "method": s["method"]} for s in await recognized("sales", day, day)]
    return out


async def item_costs():
    return {i["id"]: i.get("cost", 0) for i in await find_list("items", {}, limit=20000)}


@router.get("/reports/summary")
async def summary(start: str, end: str, user=Depends(require("owner"))):
    costs = await item_costs()
    tx, daily_rows = [], defaultdict(lambda: defaultdict(int))
    res = {"omzet": {}, "count": {}, "hpp": 0, "discount": 0, "shipping": 0}
    for kind, coll in (("job", "jobs"), ("sale", "sales"), ("order", "orders")):
        docs = await recognized(coll, start, end)
        res["omzet"][kind] = sum(omzet_of(kind, d) for d in docs)
        res["count"][kind] = len(docs)
        res["hpp"] += sum(d.get("hpp", 0) for d in docs)
        res["discount"] += sum(d.get("discount_amount", 0) for d in docs)
        if kind == "order":
            res["shipping"] = sum(d.get("shipping_cost", 0) for d in docs)
        for d in docs:
            daily_rows[d["recognized_date"]][f"omzet_{kind}"] += omzet_of(kind, d)
            tx.append({"kind": kind, "id": d["id"], "no": d["no"], "date": d["recognized_date"],
                       "customer": (d.get("customer") or {}).get("name") or d.get("customer_name") or "-",
                       "subtotal": d["subtotal"], "discount": d.get("discount_amount", 0), "total": d["total"],
                       "paid": d["paid"], "refunded": d.get("refunded", 0), "hpp": d.get("hpp", 0)})
    res["omzet_total"] = sum(res["omzet"].values())
    pays = await find_list("payments", {"date_local": rng(start, end)}, [("created_at", 1)], 50000)
    pin = [p for p in pays if p["direction"] == "in"]
    pout = [p for p in pays if p["direction"] == "out"]
    res["received"] = {m: sum(p["amount"] for p in pin if p["method"] == m) for m in ("tunai", "transfer", "cod")}
    res["received_total"] = sum(res["received"].values())
    res["refund_total"] = sum(p["amount"] for p in pout)
    res["refund_by_method"] = {m: sum(p["amount"] for p in pout if p["method"] == m) for m in ("tunai", "transfer")}
    res["dp_received"] = sum(p["amount"] for p in pin if p["kind"] == "dp")
    res["net_cash"] = res["received_total"] - res["refund_total"]
    for p in pays:
        daily_rows[p["date_local"]]["uang_masuk" if p["direction"] == "in" else "uang_keluar"] += p["amount"]
    ret_hpp_back = 0
    ret_refund = 0
    write_off = 0
    returns = []
    for kind, coll in (("job", "jobs"), ("sale", "sales"), ("order", "orders")):
        for d in await find_list(coll, {"returns.date_local": rng(start, end)}, limit=5000):
            for r in d["returns"]:
                if start <= r["date_local"] <= end:
                    ret_hpp_back += sum(costs.get(i["item_id"], 0) * i["qty"] for i in r["items"] if i["condition"] == "layak")
                    ret_refund += r["refund"]
                    write_off += r.get("write_off", 0)
                    returns.append({"kind": kind, "id": d["id"], "no": d["no"], "date": r["date_local"], "refund": r["refund"],
                                    "write_off": r.get("write_off", 0), "reason": r["reason"], "items": r["items"]})
    res["returns"] = returns
    res["return_hpp_back"] = ret_hpp_back
    res["return_refund"] = ret_refund
    res["write_off"] = write_off
    res["net_revenue"] = res["omzet_total"] - ret_refund - write_off
    kept = 0
    cancels = []
    for kind, coll in (("job", "jobs"), ("order", "orders")):
        for d in await find_list(coll, {"cancel.date_local": rng(start, end)}, limit=5000):
            kept += d["cancel"].get("kept", 0) if not d.get("recognized") else 0
            cancels.append({"kind": kind, "id": d["id"], "no": d["no"], "date": d["cancel"]["date_local"], "reason": d["cancel"]["reason"],
                            "refund": d["cancel"]["refund"], "kept": d["cancel"].get("kept", 0)})
    res["cancels"] = cancels
    res["cancel_kept"] = kept
    exps = await find_list("expenses", {"date": rng(start, end), "void": {"$ne": True}}, limit=20000)
    by_cat = defaultdict(int)
    for e in exps:
        by_cat[e["category"]] += e["amount"]
        daily_rows[e["date"]]["biaya"] += e["amount"]
    res["expenses"] = dict(by_cat)
    res["expense_total"] = sum(by_cat.values())
    dmg = await find_list("damaged", {"date_local": rng(start, end)}, limit=20000)
    res["damaged_count"] = sum(d["qty"] for d in dmg)
    res["damage_loss"] = sum(costs.get(d["item_id"], 0) * d["qty"] for d in dmg if d["source"] == "stok")
    internal = await find_list("stock_mutations", {"kind": "pemakaian_internal", "date_local": rng(start, end)}, limit=20000)
    res["internal_use_cost"] = sum(costs.get(m["item_id"], 0) * -m["delta"] for m in internal)
    res["gross_profit"] = res["net_revenue"] - (res["hpp"] - ret_hpp_back)
    res["net_profit"] = res["gross_profit"] - res["expense_total"] - res["damage_loss"] - res["internal_use_cost"] + kept
    res["missing_cost_items"] = await db.items.count_documents({"active": True, "cost": {"$in": [0, None]}})
    res["daily"] = [{"date": k} | dict(v) for k, v in sorted(daily_rows.items())]
    res["transactions"] = tx
    res |= await snapshot()
    return res


async def snapshot():
    cod = await find_list("orders", {"payment_type": "cod", "stock_applied": True, "cod_settled": False,
                                     "ship_status": {"$nin": ["Batal", "Kembali"]}})
    dp_jobs = await find_list("jobs", {"status": "Masuk", "paid": {"$gt": 0}})
    dp_orders = await find_list("orders", {"recognized": False, "paid": {"$gt": 0}, "ship_status": {"$nin": ["Batal"]}})
    recv = await find_list("jobs", {"status": "Selesai", "$expr": {"$gt": ["$total", "$paid"]}})
    items = await find_list("items", {}, limit=20000)
    return {
        "cod_pending": [{"id": o["id"], "no": o["no"], "customer": o["customer"]["name"], "amount": o["total"] - o["paid"],
                         "shipped_at": o.get("shipped_at")} for o in cod],
        "cod_pending_total": sum(o["total"] - o["paid"] for o in cod),
        "dp_held": [{"kind": k, "id": d["id"], "no": d["no"], "customer": d["customer"]["name"], "total": d["total"],
                     "paid": d["paid"] - d.get("refunded", 0)} for k, docs in (("job", dp_jobs), ("order", dp_orders)) for d in docs],
        "dp_held_total": sum(d["paid"] - d.get("refunded", 0) for d in dp_jobs + dp_orders),
        "receivables": [{"kind": "job", "id": d["id"], "no": d["no"], "customer": d["customer"]["name"], "amount": d["total"] - d["paid"]}
                        for d in recv],
        "receivables_total": sum(d["total"] - d["paid"] for d in recv),
        "inventory_value": sum(max(i.get("stock", 0), 0) * i.get("cost", 0) for i in items),
        "inventory_units": sum(i.get("stock", 0) for i in items),
        "low_stock": [{"id": i["id"], "sku": i["sku"], "name": i["name"], "stock": i["stock"], "min_stock": i.get("min_stock", 0)}
                      for i in items if i.get("active") and i.get("min_stock") and i["stock"] <= i["min_stock"]],
    }


@router.get("/dashboard")
async def dashboard(user=Depends(require(*STAFF))):
    out = {"open_jobs": await db.jobs.count_documents({"status": "Masuk"}),
           "new_orders": await db.orders.count_documents({"ship_status": "Baru"}),
           "today": await daily(None, user)}
    if user["role"] == "owner":
        out["pending_discounts"] = await db.jobs.count_documents({"discount.status": "pending"}) + \
            await db.orders.count_documents({"discount.status": "pending"})
    if user["role"] in MANAGERS:
        s = await snapshot()
        out["low_stock"] = s["low_stock"]
        out["cod_pending_total"] = s["cod_pending_total"]
        if user["role"] == "owner":
            out["inventory_value"] = s["inventory_value"]
            out["receivables_total"] = s["receivables_total"]
    return out


def to_csv(rows, cols, name):
    buf = io.StringIO()
    buf.write("\ufeff")
    w = csv.writer(buf, delimiter=";")
    w.writerow([c[1] for c in cols])
    for r in rows:
        w.writerow([r.get(c[0], "") for c in cols])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})


@router.get("/reports/export")
async def export(kind: str, start: str, end: str, user=Depends(require(*MANAGERS))):
    if kind != "mutations" and user["role"] != "owner":
        raise HTTPException(403, "Hanya owner")
    if kind == "transactions":
        s = await summary(start, end, user)
        return to_csv(s["transactions"], [("date", "Tanggal"), ("kind", "Jenis"), ("no", "No Nota"), ("customer", "Pelanggan"),
                                          ("subtotal", "Subtotal"), ("discount", "Diskon"), ("total", "Total"), ("paid", "Dibayar"),
                                          ("refunded", "Dikembalikan"), ("hpp", "HPP")], f"transaksi_{start}_{end}")
    if kind == "payments":
        rows = await find_list("payments", {"date_local": rng(start, end)}, [("created_at", 1)], 50000)
        return to_csv(rows, [("date_local", "Tanggal"), ("created_at", "Waktu UTC"), ("ref_no", "No Nota"), ("ref_type", "Jenis"),
                             ("direction", "Arah"), ("kind", "Keterangan"), ("method", "Metode"), ("amount", "Jumlah"),
                             ("user_name", "Petugas"), ("note", "Catatan")], f"pembayaran_{start}_{end}")
    if kind == "mutations":
        rows = await find_list("stock_mutations", {"date_local": rng(start, end)}, [("created_at", 1)], 50000)
        return to_csv(rows, [("date_local", "Tanggal"), ("sku", "SKU"), ("item_name", "Barang"), ("kind", "Jenis"), ("qty_before", "Sebelum"),
                             ("delta", "Selisih"), ("qty_after", "Sesudah"), ("reason", "Alasan"), ("ref_no", "Referensi"),
                             ("user_name", "Petugas")], f"mutasi_{start}_{end}")
    if kind == "damaged":
        rows = await find_list("damaged", {"date_local": rng(start, end)}, [("created_at", 1)], 20000)
        return to_csv(rows, [("date_local", "Tanggal"), ("item_name", "Barang"), ("qty", "Jumlah"), ("source", "Sumber"),
                             ("reason", "Alasan"), ("ref_no", "Referensi"), ("user_name", "Petugas")], f"barang_rusak_{start}_{end}")
    if kind == "expenses":
        rows = await find_list("expenses", {"date": rng(start, end), "void": {"$ne": True}}, [("date", 1)], 20000)
        return to_csv(rows, [("date", "Tanggal"), ("category", "Kategori"), ("amount", "Jumlah"), ("method", "Metode"), ("note", "Catatan"),
                             ("user_name", "Petugas")], f"biaya_{start}_{end}")
    if kind == "inventory":
        rows = await find_list("items", {}, [("name", 1)], 20000)
        for r in rows:
            r["value"] = r.get("stock", 0) * r.get("cost", 0)
        return to_csv(rows, [("sku", "SKU"), ("name", "Nama"), ("category", "Kategori"), ("brand", "Merek"), ("variant", "Varian"),
                             ("stock", "Stok"), ("cost", "Modal"), ("price", "Harga Jual"), ("value", "Nilai Persediaan")], "persediaan")
    raise HTTPException(400, "Jenis ekspor tidak dikenal")
