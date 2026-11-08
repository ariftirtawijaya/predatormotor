"""Iteration 4 testing agent: verify pay_lock overpay fix (orders + jobs), cancel validation 422, Baru-order return block."""
import threading
from conftest import BASE_URL, uid, stock_of
from test_order_stock_integrity import new_item, new_order, pay, phone

B = BASE_URL + "/api"


def run_parallel(fn, n):
    out = []
    th = [threading.Thread(target=lambda i=i: out.append(fn(i))) for i in range(n)]
    [t.start() for t in th]
    [t.join() for t in th]
    return out


def new_job(s, price=150000):
    r = s.post(f"{B}/jobs", json={"customer": {"name": f"TEST_it4_{uid()}", "phone": phone()},
                                  "complaint": "TEST", "lines": [{"type": "service", "name": "TEST jasa", "unit_price": price}]})
    assert r.status_code == 200, r.text
    return r.json()


# Orders: concurrent different-key full payments -> exactly one payment, others 409/400
def test_order_different_keys_codes(owner, kasir):
    it = new_item(owner, 10)
    o = new_order(kasir, it, 2)
    codes = run_parallel(lambda i: pay(kasir, o, o["total"], f"it4-{uid()}").status_code, 6)
    d = kasir.get(f"{B}/orders/{o['id']}").json()
    assert codes.count(200) == 1 and all(c in (200, 400, 409) for c in codes), codes
    assert len(d["payments"]) == 1 and d["paid"] == o["total"] and d["stock_applied"]
    assert stock_of(owner, it["id"]) == 8
    assert d.get("pay_lock") in (None,) or "pay_lock" not in d


# Orders: concurrent partial payments (each half) with different keys -> never overpaid
def test_order_concurrent_partials_never_overpay(owner, kasir):
    for _ in range(3):
        it = new_item(owner, 10)
        o = new_order(kasir, it, 1)
        amt = o["total"] * 2 // 3
        run_parallel(lambda i: pay(kasir, o, amt, f"it4-{uid()}").status_code, 4)
        d = kasir.get(f"{B}/orders/{o['id']}").json()
        assert d["paid"] <= d["total"], d["paid"]
        assert d["paid"] == sum(p["amount"] for p in d["payments"] if p["direction"] == "in")
        assert d["stock_applied"] is False and stock_of(owner, it["id"]) == 10


# Jobs: concurrent different-key full payments -> exactly one payment
def test_job_different_keys(kasir):
    for _ in range(3):
        j = new_job(kasir)
        codes = run_parallel(lambda i: kasir.post(f"{B}/tx/job/{j['id']}/payments", json={
            "amount": j["total"], "method": "tunai", "idem_key": f"it4-{uid()}"}).status_code, 5)
        d = kasir.get(f"{B}/jobs/{j['id']}").json()
        assert len(d["payments"]) == 1 and d["paid"] == j["total"], (codes, d["paid"], len(d["payments"]))


# Same idem key concurrent -> one payment, all 200 (idempotent)
def test_order_identical_key_all_ok(owner, kasir):
    it = new_item(owner, 5)
    o = new_order(kasir, it, 1)
    key = f"it4-{uid()}"
    codes = run_parallel(lambda i: pay(kasir, o, o["total"], key).status_code, 6)
    d = kasir.get(f"{B}/orders/{o['id']}").json()
    assert len(d["payments"]) == 1 and stock_of(owner, it["id"]) == 4
    assert all(c in (200, 409) for c in codes), codes
    # sequential retry of same key after completion is safe
    assert pay(kasir, o, o["total"], key).status_code == 200
    assert len(kasir.get(f"{B}/orders/{o['id']}").json()["payments"]) == 1


# Cancel malformed items -> strictly 422
def test_cancel_malformed_422(owner, kasir):
    it = new_item(owner, 5)
    o = new_order(kasir, it, 1)
    assert pay(kasir, o, o["total"], f"it4-{uid()}").status_code == 200
    bodies = [[{"qty": 1, "condition": "layak"}], [{"item_id": it["id"], "qty": "abc", "condition": "layak"}],
              [{"item_id": it["id"], "qty": 0, "condition": "layak"}], [{"item_id": "", "qty": 1, "condition": "layak"}],
              [{"item_id": it["id"], "qty": -1, "condition": "layak"}], [{"item_id": it["id"], "qty": 1}], "notalist"]
    codes = [owner.post(f"{B}/orders/{o['id']}/cancel", json={"reason": "TEST batal", "items": b}).status_code for b in bodies]
    assert codes == [422] * len(bodies), codes
    bad_cond = owner.post(f"{B}/orders/{o['id']}/cancel", json={"reason": "TEST batal",
                                                                "items": [{"item_id": it["id"], "qty": 1, "condition": "hilang"}]})
    assert bad_cond.status_code == 400
    assert kasir.get(f"{B}/orders/{o['id']}").json()["ship_status"] == "Baru" and stock_of(owner, it["id"]) == 4
    # valid cancel then works, belum_kembali reflected
    ok = owner.post(f"{B}/orders/{o['id']}/cancel", json={"reason": "TEST batal", "items": [
        {"item_id": it["id"], "qty": 1, "condition": "belum_kembali"}]})
    assert ok.status_code == 200, ok.text
    d = ok.json()
    assert d["ship_status"] == "Batal" and d["cancel"]["items_not_returned"] == [{"item_id": it["id"], "qty": 1}]
    assert d["outstanding_items"][0]["qty"] == 1


# Return on prepaid order in Baru -> 400; shipped order return works
def test_return_baru_blocked_shipped_ok(owner, kasir):
    it = new_item(owner, 5)
    o = new_order(kasir, it, 2)
    assert pay(kasir, o, o["total"], f"it4-{uid()}").status_code == 200
    r = owner.post(f"{B}/tx/order/{o['id']}/return", json={"reason": "TEST retur", "items": [
        {"item_id": it["id"], "qty": 1, "condition": "layak"}]})
    assert r.status_code == 400 and "Batalkan" in r.json()["detail"]
    r = owner.post(f"{B}/tx/order/{o['id']}/return", json={"reason": "TEST retur", "refund_amount": 1000})
    assert r.status_code == 400
    assert kasir.get(f"{B}/orders/{o['id']}").json()["ship_status"] == "Baru"
    assert kasir.post(f"{B}/orders/{o['id']}/ship", json={"resi": "TESTRESI"}).status_code == 200
    r = owner.post(f"{B}/tx/order/{o['id']}/return", json={"reason": "TEST retur", "items": [
        {"item_id": it["id"], "qty": 1, "condition": "layak"}, {"item_id": it["id"], "qty": 1, "condition": "rusak"}]})
    assert r.status_code == 200, r.text
    assert r.json()["ship_status"] == "Kembali" and stock_of(owner, it["id"]) == 4
