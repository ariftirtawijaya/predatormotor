"""Data contoh KHUSUS pengujian. Jangan jalankan di produksi.
Pemakaian: ALLOW_DEMO_SEED=true DEMO_ADMIN_PASSWORD=... DEMO_KASIR_PASSWORD=... python seed_demo.py"""
import asyncio
import os
import sys
from core import db, new_id, hash_pw, iso, move_stock

USERS = [("admin.test@predator.local", "Admin Uji", "admin", "DEMO_ADMIN_PASSWORD"),
         ("kasir.test@predator.local", "Kasir Uji", "kasir", "DEMO_KASIR_PASSWORD")]
ITEMS = [("TEST-BILED-01", "[TEST] BiLED 3 inch", "BiLED", "TestBrand", "3 inch", 600000, 900000, 365, 10),
         ("TEST-SHROUD-01", "[TEST] Shroud Standar", "Shroud", "TestBrand", "Hitam", 80000, 150000, 90, 10),
         ("TEST-SHROUD-RGB", "[TEST] Shroud RGB", "Shroud", "TestBrand", "RGB", 150000, 350000, 90, 5),
         ("TEST-RELAY-01", "[TEST] Relay 4 pin", "Kelistrikan", "TestBrand", "", 15000, 35000, 30, 20),
         ("TEST-LEDALIS-01", "[TEST] LED Alis", "LED", "TestBrand", "Putih", 70000, 150000, 60, 2)]


async def main():
    if os.environ.get("ALLOW_DEMO_SEED") != "true":
        print("Set ALLOW_DEMO_SEED=true untuk menjalankan. Jangan di produksi.")
        sys.exit(1)
    system = {"id": "seed", "name": "seed-demo"}
    for email, name, role, env in USERS:
        pw = os.environ.get(env)
        if not pw or len(pw) < 8:
            print(f"Set {env} (min 8 karakter).")
            sys.exit(1)
        if not await db.users.find_one({"email": email}):
            await db.users.insert_one({"id": new_id(), "email": email, "name": name, "role": role, "active": True,
                                       "password_hash": hash_pw(pw), "created_at": iso(), "demo": True})
    ids = {}
    for sku, name, cat, brand, var, cost, price, wd, stock in ITEMS:
        ex = await db.items.find_one({"sku": sku})
        if ex:
            ids[sku] = ex["id"]
            continue
        iid = new_id()
        ids[sku] = iid
        await db.items.insert_one({"id": iid, "sku": sku, "name": name, "category": cat, "brand": brand, "variant": var, "cost": cost,
                                   "price": price, "active": True, "min_stock": 2, "warranty_days": wd, "unit": "pcs", "stock": 0,
                                   "created_at": iso(), "demo": True})
        await move_stock(iid, stock, "stok_awal", "Stok awal data uji", system)
    if not await db.packages.find_one({"name": "[TEST] Paket BiLED + Shroud"}):
        await db.packages.insert_one({"id": new_id(), "name": "[TEST] Paket BiLED + Shroud", "main_brand_model": "TestBrand BiLED 3 inch",
                                      "description": "Paket uji", "price": 1500000, "warranty_days": 365, "active": True, "demo": True,
                                      "components": [{"item_id": ids["TEST-BILED-01"], "qty": 2}, {"item_id": ids["TEST-SHROUD-01"], "qty": 2},
                                                     {"item_id": ids["TEST-RELAY-01"], "qty": 1}],
                                      "options": [{"id": new_id(), "name": "Upgrade Shroud RGB", "price": 350000,
                                                   "items": [{"item_id": ids["TEST-SHROUD-RGB"], "qty": 2}]}], "created_at": iso()})
    from catalog_routes import migrate_products
    await migrate_products()
    print("Data uji siap.")


asyncio.run(main())
