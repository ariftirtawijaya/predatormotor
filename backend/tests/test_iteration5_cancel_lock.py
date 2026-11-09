"""Iteration 5 testing agent: cancel (order/job) shares pay_lock with payments; cancel labels; 2nd cancel 400; cancel during payment 409."""
import threading
from datetime import datetime, timezone
from pymongo import MongoClient
from conftest import BASE_URL, uid, stock_of, MONGO_URL, TEST_DB
from test_order_stock_integrity import new_item, new_order, pay
from test_iteration4_fixes import new_job

B = BASE_URL + "/api"


def _db():
    return MongoClient(MONGO_URL)[TEST_DB]


def race(*fns):
    out = [None] * len(fns)
    bar = threading.Barrier(len(fns))

    def run(i):
        bar.wait()
        out[i] = fns[i]()
    th = [threading.Thread(target=run, args=(i,)) for i in range(len(fns))]
    [t.start() for t in th]
    [t.join() for t in th]
    return out


def _in(d):
    return sum(p["amount"] for p in d["payments"] if p["direction"] == "in")


def _out(d):
    return sum(p["amount"] for p in d["payments"] if p["direction"] == "out")


# Order: concurrent partial payment + cancel (with refund of current paid) -> no payment after Batal, refund <= paid, no 500
def test_order_pay_vs_cancel_race(owner, kasir):
    for _ in range(6):
        it = new_item(owner, 10)
        o = new_order(kasir, it, 2)
        half = o["total"] // 2
        assert pay(kasir, o, half, f"it5-{uid()}").status_code == 200
        codes = race(lambda: pay(kasir, o, o["total"] - half, f"it5-{uid()}"),
                     lambda: owner.post(f"{B}/orders/{o['id']}/cancel", json={"reason": "TEST race", "refund_amount": half,
                                                                                "refund_method": "transfer"}))
        cs = [c.status_code for c in codes]
        assert 500 not in cs, [c.text for c in codes]
        d = kasir.get(f"{B}/orders/{o['id']}").json()
        assert _out(d) <= _in(d)
        if d["ship_status"] == "Batal":
            cancel_at = d["cancel"]["at"]
            assert all(p["created_at"] <= cancel_at for p in d["payments"] if p["direction"] == "in"), d["payments"]
            # If pay succeeded first, stock deducted -> cancel without items must have failed (400), so status Batal => pay failed
            assert cs[0] in (400, 409), cs
            assert stock_of(owner, it["id"]) == 10
        else:
            assert cs[0] == 200 and cs[1] in (400, 409), cs
            assert d["paid"] == d["total"] and stock_of(owner, it["id"]) == 8
        assert not d.get("pay_lock") and not d.get("lock")


# Job: concurrent payment + cancel -> never payment on Batal job; refund never exceeds paid
def test_job_pay_vs_cancel_race(owner, kasir):
    for _ in range(6):
        j = new_job(kasir)
        dp = j["total"] // 3
        assert kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": dp, "method": "tunai", "idem_key": f"it5-{uid()}"}).status_code == 200
        codes = race(lambda: kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": dp, "method": "tunai", "idem_key": f"it5-{uid()}"}),
                     lambda: owner.post(f"{B}/jobs/{j['id']}/cancel", json={"reason": "TEST race", "refund_amount": dp}))
        cs = [c.status_code for c in codes]
        assert 500 not in cs, [c.text for c in codes]
        d = kasir.get(f"{B}/jobs/{j['id']}").json()
        assert _out(d) <= _in(d)
        if d["status"] == "Batal":
            assert all(p["created_at"] <= d["cancel"]["at"] for p in d["payments"] if p["direction"] == "in"), d["payments"]
            assert d["cancel"]["kept"] == _in(d) - _out(d)
        assert not d.get("pay_lock")


# Labels: refund note 'Batal: <reason>' and stock mutation 'Batal <no> (layak jual): <reason>'
def test_cancel_labels(owner, kasir):
    it = new_item(owner, 5)
    o = new_order(kasir, it, 1)
    assert pay(kasir, o, o["total"], f"it5-{uid()}").status_code == 200
    reason = f"TEST label {uid()}"
    r = owner.post(f"{B}/orders/{o['id']}/cancel", json={"reason": reason, "refund_amount": o["total"], "refund_method": "transfer",
                                                         "items": [{"item_id": it["id"], "qty": 1, "condition": "layak"}]})
    assert r.status_code == 200, r.text
    d = r.json()
    refunds = [p for p in d["payments"] if p["direction"] == "out"]
    assert len(refunds) == 1 and refunds[0]["note"] == f"Batal: {reason}", refunds
    muts = owner.get(f"{B}/stock/mutations", params={"item_id": it["id"]}).json()
    back = [m for m in muts if m.get("ref_id") == o["id"] and m["qty" if "qty" in m else "delta"] > 0]
    assert any(m.get("reason") == f"Batal {o['no']} (layak jual): {reason}" for m in back), back
    assert stock_of(owner, it["id"]) == 5
    # Unpaid-stock (not applied) order refund-only path also 'Batal:'
    o2 = new_order(kasir, it, 1)
    assert pay(kasir, o2, o2["total"] // 2, f"it5-{uid()}").status_code == 200
    r2 = owner.post(f"{B}/orders/{o2['id']}/cancel", json={"reason": reason, "refund_amount": o2["total"] // 2})
    assert r2.status_code == 200, r2.text
    assert [p["note"] for p in r2.json()["payments"] if p["direction"] == "out"] == [f"Batal: {reason}"]
    # second cancel -> 400
    assert owner.post(f"{B}/orders/{o2['id']}/cancel", json={"reason": reason}).status_code == 400
    # payment on Batal order -> 400
    assert pay(kasir, o2, 1000, f"it5-{uid()}").status_code == 400


# Second job cancel -> 400; refund > paid -> 400
def test_job_second_cancel_and_overrefund(owner, kasir):
    j = new_job(kasir)
    assert kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 50000, "method": "tunai", "idem_key": f"it5-{uid()}"}).status_code == 200
    assert owner.post(f"{B}/jobs/{j['id']}/cancel", json={"reason": "TEST over", "refund_amount": 50001}).status_code == 400
    r = owner.post(f"{B}/jobs/{j['id']}/cancel", json={"reason": "TEST ok", "refund_amount": 20000})
    assert r.status_code == 200 and r.json()["status"] == "Batal" and r.json()["cancel"]["kept"] == 30000
    assert not r.json().get("pay_lock")
    assert owner.post(f"{B}/jobs/{j['id']}/cancel", json={"reason": "TEST again"}).status_code == 400
    assert kasir.post(f"{B}/tx/job/{j['id']}/payments", json={"amount": 1000, "method": "tunai", "idem_key": f"it5-{uid()}"}).status_code == 400


# Cancel while a payment holds pay_lock (simulated fresh lock) -> 409; stale lock (>30s) taken over
def test_cancel_while_payment_in_progress_409(owner, kasir):
    db = _db()
    j = new_job(kasir)
    it = new_item(owner, 3)
    o = new_order(kasir, it, 1)
    fresh = datetime.now(timezone.utc).isoformat()
    try:
        db.jobs.update_one({"id": j["id"]}, {"$set": {"pay_lock": fresh}})
        db.orders.update_one({"id": o["id"]}, {"$set": {"pay_lock": fresh}})
        assert owner.post(f"{B}/jobs/{j['id']}/cancel", json={"reason": "TEST 409"}).status_code == 409
        assert owner.post(f"{B}/orders/{o['id']}/cancel", json={"reason": "TEST 409"}).status_code == 409
        assert kasir.get(f"{B}/jobs/{j['id']}").json()["status"] == "Masuk"
        assert kasir.get(f"{B}/orders/{o['id']}").json()["ship_status"] == "Baru"
        stale = "2020-01-01T00:00:00+00:00"
        db.jobs.update_one({"id": j["id"]}, {"$set": {"pay_lock": stale}})
        db.orders.update_one({"id": o["id"]}, {"$set": {"pay_lock": stale}})
        assert owner.post(f"{B}/jobs/{j['id']}/cancel", json={"reason": "TEST stale"}).status_code == 200
        assert owner.post(f"{B}/orders/{o['id']}/cancel", json={"reason": "TEST stale"}).status_code == 200
    finally:
        db.jobs.update_one({"id": j["id"]}, {"$set": {"pay_lock": None}})
        db.orders.update_one({"id": o["id"]}, {"$set": {"pay_lock": None}})
