"""
AI Copilot: role gating on its freeze/close chat intents. Regression
coverage for a real authorization bypass found and fixed in Phase 4 — the
copilot called handle_action() directly, skipping the /action/* routes'
own require_role("admin") dependency, so a viewer could freeze an account
just by asking the chatbot.
"""

from conftest import TX_HEADERS, make_tx


def _create_high_risk_case(client):
    tx = make_tx(amount=300000, channel="NEFT", is_cross_border=True)
    r = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r.status_code == 200
    return r.json()["case"]


def test_copilot_requires_auth(client):
    r = client.post("/api/copilot", json={"message": "hello", "context_case_id": None})
    assert r.status_code == 401


def test_viewer_freeze_intent_is_denied_and_not_executed(client, viewer_headers, admin_headers):
    case = _create_high_risk_case(client)

    r = client.post(
        "/api/copilot",
        json={"message": "please freeze this case", "context_case_id": case["case_id"]},
        headers=viewer_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"] is None
    assert "admin" in body["reply"].lower()

    cases = client.get("/cases", headers=admin_headers).json()
    updated = next(c for c in cases if c["case_id"] == case["case_id"])
    assert updated["status"] != "ACTIONED", "viewer's copilot freeze request must not execute"


def test_admin_freeze_intent_executes(client, admin_headers):
    case = _create_high_risk_case(client)

    r = client.post(
        "/api/copilot",
        json={"message": "please freeze this case", "context_case_id": case["case_id"]},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"]["type"] == "FREEZE_ACCOUNTS"

    cases = client.get("/cases", headers=admin_headers).json()
    updated = next(c for c in cases if c["case_id"] == case["case_id"])
    assert updated["status"] == "ACTIONED"


def test_copilot_offline_fallback_answers_without_case(client, admin_headers):
    r = client.post(
        "/api/copilot",
        json={"message": "hello", "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["reply"]
