"""Buat atau reset akun owner: python create_owner.py email@domain.com "Nama Owner" """
import asyncio
import sys
import getpass
from core import db, new_id, hash_pw, iso


async def main():
    if len(sys.argv) < 2:
        print("Pemakaian: python create_owner.py email [nama]")
        return
    email = sys.argv[1].strip().lower()
    name = sys.argv[2] if len(sys.argv) > 2 else "Owner"
    pw = getpass.getpass("Password baru (min 8 karakter): ")
    if len(pw) < 8 or pw != getpass.getpass("Ulangi password: "):
        print("Password terlalu pendek atau tidak sama")
        return
    ex = await db.users.find_one({"email": email})
    if ex:
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_pw(pw), "role": "owner", "active": True}})
        print("Akun sudah ada: password diperbarui dan peran owner dipastikan.")
    else:
        await db.users.insert_one({"id": new_id(), "email": email, "name": name, "role": "owner", "active": True,
                                   "password_hash": hash_pw(pw), "created_at": iso()})
        print("Akun owner dibuat.")


asyncio.run(main())
