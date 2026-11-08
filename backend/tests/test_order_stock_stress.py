"""Extra stress/edge tests for order stock integrity (iteration 3 testing agent)."""
import threading
from conftest import BASE_URL, uid, stock_of
from test_order_stock_integrity import new_item, new_order, pay

B = BASE_URL + "/api"


def run_parallel(fn, n):
    out = []
    th = [threading.Thread(target=lambda i=i: out.append(fn(i))) for i in range(n)]
    [t.start() for t in th]
    [t.join() for t in th]
    return out


# Settlement: repeated concurrent identical requests, many rounds (race window check)
def test_concurrent_identical_settlement_many_rounds(owner, kasir):
    bad = []
    for rnd in range(8):
        it = new_item(owner, 5)
        o = new_order(kasir, it, 2)
        key = f"osi-{uid()}"
        codes = run_parallel(lambda i: pay(kasir, o, o["total"], key).status_code, 6)
        d = kasir.get(f"{B}/orders/{o['id']}").json()
        st = stock_of(owner, it["id"])
        ok = len(d["payments"]) == 1 and d["paid"] == o["total"] and d["stock_applied"] and st == 3
        if not ok:
            bad.append({"round": rnd, "codes": codes, "payments": len(d["payments"]), "paid": d["paid"],
                        "stock_applied": d["stock_applied"], "stock": st})
    assert not bad, repr(bad)


# Settlement: concurrent requests with DIFFERENT idem keys (double submit from two tabs) must not overpay/double deduct
def test_concurrent_different_keys_settlement(owner, kasir):
    bad = []
    for rnd in range(5):
        it = new_item(owner, 10)
        o = new_order(kasir, it, 2)
        codes = run_parallel(lambda i: pay(kasir, o, o["total"], f"osi-{uid()}").status_code, 4)
        d = kasir.get(f"{B}/orders/{o['id']}").json()
        st = stock_of(owner, it["id"])
        if not (d["paid"] == o["total"] and len(d["payments"]) == 1 and st == 8 and d["stock_applied"]):
            bad.append({"round": rnd, "codes": codes, "payments": len(d["payments"]), "paid": d["paid"], "total": o["total"],
                        "stock": st, "stock_applied": d["stock_applied"]})
    assert not bad, repr(bad)


# Cancel: malformed items must be 400 not 500
def test_cancel_malformed_items(owner, kasir):
    it = new_item(owner, 5)
    o = new_order(kasir, it, 1)
    assert pay(kasir, o, o["total"], f"osi-{uid()}").status_code == 200
    r1 = owner.post(f"{B}/orders/{o['id']}/cancel", json={"reason": "TEST batal", "items": [{"qty": 1, "condition": "layak"}]})
    r2 = owner.post(f"{B}/orders/{o['id']}/cancel", json={"reason": "TEST batal",
                                                           "items": [{"item_id": it["id"], "qty": "abc", "condition": "layak"}]})
    r3 = owner.post(f"{B}/orders/{o['id']}/cancel", json={"reason": "TEST batal",
                                                           "items": [{"item_id": "nope", "qty": 1, "condition": "layak"}]})
    assert (r1.status_code, r2.status_code, r3.status_code) == (400, 400, 400) or all(
        c in (400, 422) for c in (r1.status_code, r2.status_code, r3.status_code)), (r1.status_code, r2.status_code, r3.status_code, r3.text)
    assert stock_of(owner, it["id"]) == 4


# Cancel: concurrent cancel requests -> exactly one return recorded
def test_concurrent_cancel(owner, kasir):
    it = new_item(owner, 5)
    o = new_order(kasir, it, 2)
    assert pay(kasir, o, o["total"], f"osi-{uid()}").status_code == 200
    items = [{"item_id": it["id"], "qty": 2, "condition": "layak"}]
    codes = run_parallel(lambda i: owner.post(f"{B}/orders/{o['id']}/cancel", json={
        "reason": "TEST batal", "items": items, "refund_amount": o["total"], "refund_method": "transfer"}).status_code, 4)
    d = owner.get(f"{B}/orders/{o['id']}").json()
    assert codes.count(200) == 1, codes
    assert len(d["returns"]) == 1 and d["refunded"] == o["total"] and stock_of(owner, it["id"]) == 5


# Ship an order that is Batal -> 400; payment on Batal -> 400
def test_batal_blocks_ship_and_pay(owner, kasir):
    it = new_item(owner, 5)
    o = new_order(kasir, it, 1)
    assert owner.post(f"{B}/orders/{o['id']}/cancel", json={"reason": "TEST batal", "items": []}).status_code == 200
    assert kasir.post(f"{B}/orders/{o['id']}/ship", json={}).status_code == 400
    assert pay(kasir, o, o["total"], f"osi-{uid()}").status_code == 400
