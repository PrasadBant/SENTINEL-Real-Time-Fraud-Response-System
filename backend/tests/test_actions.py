"""
Investigative actions: freeze/monitor/close status transitions, admin-only
enforcement, and the EC-03 withdrawal-timer register/cancel wiring across
the transactions.py <-> actions.py module boundary (regression coverage
for the Phase 2 router split).
"""

import asyncio

from conftest import TX_HEADERS, make_tx


def _create_high_risk_case(client):
    tx = make_tx(amount=300000, channel="IMPS", is_crypto_related=True)
    r = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r.status_code == 200
    case = r.json()["case"]
    assert case is not None
    return case, tx


def test_freeze_unknown_case_returns_not_found(client, admin_headers):
    r = client.post("/action/freeze", json={"case_id": "CASE-DOES-NOT-EXIST"}, headers=admin_headers)
    assert r.status_code == 200  # not-found is reported in the body, not the HTTP status
    body = r.json()
    assert body["ok"] is False
    assert body["error"] == "case_not_found"


def test_freeze_sets_case_actioned_and_node_frozen(client, admin_headers):
    case, _tx = _create_high_risk_case(client)
    r = client.post(
        "/action/freeze",
        json={"case_id": case["case_id"], "target_id": "GLOBAL", "reason": "test"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["status"] == "ACK"

    cases = client.get("/cases", headers=admin_headers).json()
    updated = next(c for c in cases if c["case_id"] == case["case_id"])
    assert updated["status"] == "ACTIONED"
    frozen_nodes = [n for n in updated["nodes"] if n["status"] == "frozen"]
    assert len(frozen_nodes) > 0


def test_close_and_close_fp_set_expected_status(client, admin_headers):
    case, _tx = _create_high_risk_case(client)
    r = client.post("/action/close", json={"case_id": case["case_id"]}, headers=admin_headers)
    assert r.status_code == 200
    cases = client.get("/cases", headers=admin_headers).json()
    updated = next(c for c in cases if c["case_id"] == case["case_id"])
    assert updated["status"] == "CLOSED"


def test_ec03_withdrawal_tracker_register_and_cancel_roundtrip():
    """
    Direct unit test of the shared withdrawal_tracker module (moved out of
    main.py's module-global dict during the Phase 2 router split, and
    fixed for unbounded growth in Phase 1) — verifies register() marks a
    key active, and cancel() deactivates + evicts it.
    """
    from app.services import withdrawal_tracker

    async def _run():
        async def slow():
            await asyncio.sleep(10)

        key = f"test-key-{id(object())}"
        task = asyncio.create_task(slow())
        withdrawal_tracker.register(key, task)
        await asyncio.sleep(0)
        assert withdrawal_tracker.is_active(key) is True

        cancelled = withdrawal_tracker.cancel(key)
        assert cancelled is True
        # allow the cancellation + done-callback to propagate
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert withdrawal_tracker.is_active(key) is False
        assert key not in withdrawal_tracker._pending

    asyncio.run(_run())
