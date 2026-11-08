"""Helper (not a test): paid prepaid WA order (3 pcs) + job with DP for UI cancel smoke. Prints ids."""
import sys
sys.path.insert(0, "/app/backend/tests")
from conftest import login, uid, BASE_URL
from test_order_stock_integrity import new_item, new_order, pay
from test_iteration4_fixes import new_job

owner, kasir = login("owner"), login("kasir")
it = new_item(owner, 5)
o = new_order(kasir, it, 3)
assert pay(kasir, o, o["total"], f"ui5-{uid()}").status_code == 200
j = new_job(kasir, 300000)
assert kasir.post(f"{BASE_URL}/api/tx/job/{j['id']}/payments", json={"amount": 100000, "method": "tunai", "idem_key": f"ui5-{uid()}"}).status_code == 200
print(f"ITEM={it['id']} ORDER={o['id']} TOTAL={o['total']} JOB={j['id']}")
