"""
POST /transaction idempotency: a caller-supplied idempotency_key (meant to
be a payment-rail reference — UPI/IMPS/NEFT) must make a repeated
submission a no-op, returning the original result instead of re-scoring,
re-casing, re-broadcasting, or re-arming an EC-03 withdrawal timer. A
transaction with no supplied key gets a generated one and is never treated
as a duplicate of anything else (see app/api/transactions.py).
"""

from conftest import TX_HEADERS, make_tx, unique_id


def test_duplicate_idempotency_key_returns_original_result(client):
    key = unique_id("RAIL-REF")
    tx = make_tx(amount=1500, idempotency_key=key)
    r1 = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r1.status_code == 200
    body1 = r1.json()

    # Same idempotency_key, different tx_id/amount — a real retry after a
    # client-side timeout wouldn't necessarily resend byte-identical JSON.
    retry = make_tx(amount=999999, idempotency_key=key)
    r2 = client.post("/transaction", json=retry, headers=TX_HEADERS)
    assert r2.status_code == 200
    body2 = r2.json()

    # The *original* transaction comes back unchanged — not re-scored
    # against the retry's (very different) amount.
    assert body2["transaction"]["tx_id"] == body1["transaction"]["tx_id"]
    assert body2["transaction"]["amount"] == body1["transaction"]["amount"]
    assert body2["transaction"]["risk_score"] == body1["transaction"]["risk_score"]
    assert body2["transaction"]["idempotency_key"] == key


def test_duplicate_idempotency_key_skips_broadcast_and_ec03(client, monkeypatch):
    from app.services import withdrawal_queue
    from app.websocket.connection_manager import manager

    calls = {"broadcast": 0, "schedule": 0}

    async def fake_broadcast(_event):
        calls["broadcast"] += 1

    async def fake_schedule(key, case_id, suspect_node_id, delay_seconds, correlation_id):
        calls["schedule"] += 1
        return True

    monkeypatch.setattr(manager, "broadcast", fake_broadcast)
    monkeypatch.setattr(withdrawal_queue, "schedule", fake_schedule)

    key = unique_id("RAIL-REF")
    tx = make_tx(amount=350000, channel="IMPS", is_cross_border=True, on_active_call=True, idempotency_key=key)
    r1 = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r1.status_code == 200
    assert r1.json()["case"] is not None  # sanity: this really is a HIGH_RISK case
    assert calls["broadcast"] > 0, "first-time POST should broadcast as usual"
    assert calls["schedule"] > 0, "first-time HIGH_RISK case should arm an EC-03 timer"
    broadcasts_after_first = calls["broadcast"]
    schedules_after_first = calls["schedule"]

    retry = make_tx(amount=350000, channel="IMPS", is_cross_border=True, on_active_call=True, idempotency_key=key)
    r2 = client.post("/transaction", json=retry, headers=TX_HEADERS)
    assert r2.status_code == 200

    # The duplicate must not add any further broadcasts or timers.
    assert calls["broadcast"] == broadcasts_after_first
    assert calls["schedule"] == schedules_after_first


def test_missing_idempotency_key_never_collides(client):
    """Two transactions with no supplied idempotency_key each get their own
    generated key and are processed independently — not treated as
    duplicates of each other."""
    tx1 = make_tx(amount=1200)
    tx2 = make_tx(amount=3400)
    r1 = client.post("/transaction", json=tx1, headers=TX_HEADERS)
    r2 = client.post("/transaction", json=tx2, headers=TX_HEADERS)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["transaction"]["tx_id"] != r2.json()["transaction"]["tx_id"]
    assert r1.json()["transaction"]["amount"] == 1200
    assert r2.json()["transaction"]["amount"] == 3400
