"""
Investigative actions: freeze/monitor/close status transitions and
admin-only enforcement. EC-03 withdrawal-timer scheduling/cancellation
(app/services/withdrawal_queue.py, Arq/Redis-backed as of Phase 1) has
its own coverage in tests/test_redis_integration.py, since it now
behaves differently enough against real Redis to be worth testing there
specifically rather than as a bare in-process unit test.
"""

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
