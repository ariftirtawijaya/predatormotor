"""Helper (not a test): create TEST_ item + prepaid WA order for UI checks. Prints ids."""
import sys
sys.path.insert(0, "/app/backend/tests")
from conftest import login
from test_order_stock_integrity import new_item, new_order

owner, kasir = login("owner"), login("kasir")
it = new_item(owner, 5)
o = new_order(kasir, it, 3)
print(f"ITEM={it['id']} ORDER={o['id']} TOTAL={o['total']}")
