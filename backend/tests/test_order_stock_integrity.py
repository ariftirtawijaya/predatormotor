"""Order stock integrity: prepaid settlement must not be recorded when stock deduction fails;
cancelled orders must account for every pcs that left stock."""
import threading
from conftest import BASE_URL, uid, stock_of
from test_predator_core import phone

B = BASE_URL + "/api"


def new_item(owner, stock, price=100000):
    r = owner.post(f"{B}/items", json={"sku": f"TEST-OSI-{uid()}", "name": f"[TEST] OSI {uid()}", "cost": 40000, "price": price,
                                       "initial_stock": stock})
    assert r.status_code == 200, r.text
    return r.json()


def new_order(s, item, qty, province="Bali"):
    r = s.post(f"{B}/orders", json={"customer_name": f"TEST_osi_{uid()}", "customer_phone": phone(), "province": province,
                                    "address": "Jl. Uji 1", "delivery": "kurir", "shipping_cost": 0, "payment_type": "prabayar",
                                    "lines": [{"type": "item", "item_id": item["id"], "qty": qty}]})
    assert r.status_code == 200, r.text
    return r.json()


def pay(s, o, amount, key):
    return s.post(f"{B}/tx/order/{o['id']}/payments", json={"amount": amount, "method": "transfer", "idem_key": key})


def payments(s, o):
    return s.get(f"{B}/orders/{o['id']}").json()["payments"]


class TestPrepaidSettlement:
    def test_insufficient_stock_blocks_settlement_and_shipping(self, owner, kasir):
        it = new_item(owner, 1)
        o = new_order(kasir, it, 2)
        r = pay(kasir, o, o["total"], f"osi-{uid()}")
        assert r.status_code == 409, r.text
        d = kasir.get(f"{B}/orders/{o['id']}").json()
        assert d["paid"] == 0 and not d["stock_applied"] and d["payments"] == []
        assert stock_of(owner, it["id"]) == 1
        assert kasir.post(f"{B}/orders/{o['id']}/ship", json={}).status_code == 400
        # after restock the same settlement succeeds and stock is deducted once
        owner.post(f"{B}/stock/in", json={"item_id": it["id"], "qty": 4})
        key = f"osi-{uid()}"
        r = pay(kasir, o, o["total"], key)
        assert r.status_code == 200, r.text
        assert r.json()["stock_applied"] and r.json()["paid"] == o["total"]
        assert stock_of(owner, it["id"]) == 3
        # repeated identical request: no second payment, no second deduction
        r2 = pay(kasir, o, o["total"], key)
        assert r2.status_code == 200
        assert len(payments(kasir, o)) == 1 and stock_of(owner, it["id"]) == 3
        assert kasir.post(f"{B}/orders/{o['id']}/ship", json={"resi": "JT1"}).json()["ship_status"] == "Dikirim"

    def test_dp_then_settlement_with_stock_taken_by_sale(self, owner, kasir):
        it = new_item(owner, 1)
        o = new_order(kasir, it, 1)
        assert pay(kasir, o, 30000, f"osi-{uid()}").status_code == 200
        sale = kasir.post(f"{B}/sales", json={"lines": [{"item_id": it["id"], "qty": 1}], "method": "tunai", "idem_key": f"osi-{uid()}"})
        assert sale.status_code == 200, sale.text
        r = pay(kasir, o, o["total"] - 30000, f"osi-{uid()}")
        assert r.status_code == 409
        d = kasir.get(f"{B}/orders/{o['id']}").json()
        assert d["paid"] == 30000 and not d["stock_applied"]
        assert stock_of(owner, it["id"]) == 0
        assert kasir.post(f"{B}/orders/{o['id']}/ship", json={}).status_code == 400

    def test_concurrent_identical_settlement(self, owner, kasir):
        it = new_item(owner, 5)
        o = new_order(kasir, it, 2)
        key = f"osi-{uid()}"
        codes = []
        th = [threading.Thread(target=lambda: codes.append(pay(kasir, o, o["total"], key).status_code)) for _ in range(4)]
        [t.start() for t in th]
        [t.join() for t in th]
        assert 200 in codes and all(c in (200, 409) for c in codes), codes
        d = kasir.get(f"{B}/orders/{o['id']}").json()
        assert len(d["payments"]) == 1 and d["paid"] == o["total"] and d["stock_applied"]
        assert stock_of(owner, it["id"]) == 3


class TestCancelAccounting:
    def paid_order(self, owner, kasir, qty=3):
        it = new_item(owner, 10)
        o = new_order(kasir, it, qty)
        assert pay(kasir, o, o["total"], f"osi-{uid()}").status_code == 200
        assert stock_of(owner, it["id"]) == 10 - qty
        return it, o

    def cancel(self, owner, o, items, refund=0):
        return owner.post(f"{B}/orders/{o['id']}/cancel", json={"reason": "TEST batal", "refund_amount": refund,
                                                                 "refund_method": "transfer", "items": items})

    def test_cancel_requires_every_pcs(self, owner, kasir):
        it, o = self.paid_order(owner, kasir)
        assert self.cancel(owner, o, []).status_code == 400
        assert self.cancel(owner, o, [{"item_id": it["id"], "qty": 2, "condition": "layak"}]).status_code == 400
        assert self.cancel(owner, o, [{"item_id": it["id"], "qty": 4, "condition": "layak"}]).status_code == 400
        assert self.cancel(owner, o, [{"item_id": it["id"], "qty": 3, "condition": "hilang"}]).status_code == 400
        d = owner.get(f"{B}/orders/{o['id']}").json()
        assert d["ship_status"] == "Baru" and d["returns"] == []
        assert stock_of(owner, it["id"]) == 7

    def test_cancel_mixed_conditions_then_receive_back(self, owner, kasir, admin):
        it, o = self.paid_order(owner, kasir)
        r = self.cancel(owner, o, [{"item_id": it["id"], "qty": 1, "condition": "layak"},
                                   {"item_id": it["id"], "qty": 1, "condition": "rusak"},
                                   {"item_id": it["id"], "qty": 1, "condition": "belum_kembali"}], refund=o["total"])
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ship_status"] == "Batal" and d["refunded"] == o["total"]
        assert d["cancel"]["items_not_returned"] == [{"item_id": it["id"], "qty": 1}]
        assert [x["qty"] for x in d["outstanding_items"]] == [1]
        assert stock_of(owner, it["id"]) == 8
        dmg = [x for x in owner.get(f"{B}/damaged").json() if x["ref_id"] == o["id"]]
        assert len(dmg) == 1 and dmg[0]["qty"] == 1 and not dmg[0]["affects_stock"]
        # belum_kembali is not valid on a normal return
        assert admin.post(f"{B}/tx/order/{o['id']}/return", json={"items": [{"item_id": it["id"], "qty": 1, "condition": "belum_kembali"}],
                                                                     "reason": "TEST"}).status_code == 400
        # the missing pcs arrives later and is inspected as sellable
        r = admin.post(f"{B}/tx/order/{o['id']}/return", json={"items": [{"item_id": it["id"], "qty": 1, "condition": "layak"}],
                                                                  "reason": "TEST barang datang"})
        assert r.status_code == 200, r.text
        assert r.json()["ship_status"] == "Batal" and r.json()["outstanding_items"] == []
        assert stock_of(owner, it["id"]) == 9
        assert admin.post(f"{B}/tx/order/{o['id']}/return", json={"items": [{"item_id": it["id"], "qty": 1, "condition": "layak"}],
                                                                     "reason": "TEST lebih"}).status_code == 400

    def test_cancel_unpaid_order_rejects_items(self, owner, kasir):
        it = new_item(owner, 5)
        o = new_order(kasir, it, 1)
        assert self.cancel(owner, o, [{"item_id": it["id"], "qty": 1, "condition": "layak"}]).status_code == 400
        r = self.cancel(owner, o, [])
        assert r.status_code == 200 and r.json()["ship_status"] == "Batal"
        assert stock_of(owner, it["id"]) == 5

    def test_cancel_twice_and_kasir_forbidden(self, owner, kasir):
        it, o = self.paid_order(owner, kasir, 1)
        items = [{"item_id": it["id"], "qty": 1, "condition": "layak"}]
        assert kasir.post(f"{B}/orders/{o['id']}/cancel", json={"reason": "x batal", "items": items}).status_code == 403
        assert self.cancel(owner, o, items).status_code == 200
        assert self.cancel(owner, o, items).status_code == 400
        assert stock_of(owner, it["id"]) == 10
