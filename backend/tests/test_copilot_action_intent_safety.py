"""
AI Copilot: regression coverage for a false-positive bug in the freeze/close
chat-action matcher (app.api.copilot._resolve_action_intent).

The original matcher was a bare substring check (`"freeze" in user_msg`,
`"close" in user_msg`). Two concrete failure modes:

  1. "close" is a common English word — "how close are we to resolving
     this case?" would silently CLOSE the case.
  2. "freeze" is a substring of "unfreeze" — "please unfreeze this
     account" would actually FREEZE it, the opposite of what was asked.

Both executed a real, hard-to-reverse action (handle_action) and reported
back "Action Executed" as if it were the intended result. Fixed by
anchoring the verb via regex (_FREEZE_RE/_CLOSE_RE) plus an explicit
_UNFREEZE_RE guard that answers honestly instead of firing the opposite
action. These tests pin that fix down.
"""

from conftest import TX_HEADERS, make_tx


def _create_high_risk_case(client):
    tx = make_tx(amount=300000, channel="NEFT", is_cross_border=True)
    r = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r.status_code == 200
    return r.json()["case"]


def _case_status(client, admin_headers, case_id):
    cases = client.get("/cases", headers=admin_headers).json()
    return next(c for c in cases if c["case_id"] == case_id)["status"]


def test_unfreeze_request_does_not_freeze_the_account(client, admin_headers):
    """The literal bug: asking to UNDO a freeze must not trigger one."""
    case = _create_high_risk_case(client)

    r = client.post(
        "/api/copilot/chat",
        json={"message": "please unfreeze this account", "context_case_id": case["case_id"]},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"] is None
    assert "unfreeze" in body["reply"].lower()

    assert _case_status(client, admin_headers, case["case_id"]) != "ACTIONED"


def test_how_close_question_does_not_close_the_case(client, admin_headers):
    """A plain investigative question containing "close" as an ordinary
    word must not trigger the close action."""
    case = _create_high_risk_case(client)

    r = client.post(
        "/api/copilot/chat",
        json={
            "message": "How close are we to resolving this case?",
            "context_case_id": case["case_id"],
        },
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"] is None

    assert _case_status(client, admin_headers, case["case_id"]) not in ("CLOSED", "CLOSED_FP")


def test_closer_look_phrasing_does_not_close_the_case(client, admin_headers):
    """"closer"/"closely" must not match the "close" trigger."""
    case = _create_high_risk_case(client)

    r = client.post(
        "/api/copilot/chat",
        json={"message": "let's take a closer look at this one", "context_case_id": case["case_id"]},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["action"] is None
    assert _case_status(client, admin_headers, case["case_id"]) not in ("CLOSED", "CLOSED_FP")


def test_explicit_close_this_case_still_executes(client, admin_headers):
    """The fix must not break the legitimate phrasing."""
    case = _create_high_risk_case(client)

    r = client.post(
        "/api/copilot/chat",
        json={"message": "please close this case", "context_case_id": case["case_id"]},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"]["type"] == "CLOSE_CASE"
    assert _case_status(client, admin_headers, case["case_id"]) == "CLOSED"


def test_freeze_this_case_still_executes(client, admin_headers):
    """The fix must not break the legitimate freeze phrasing either."""
    case = _create_high_risk_case(client)

    r = client.post(
        "/api/copilot/chat",
        json={"message": "freeze this case immediately", "context_case_id": case["case_id"]},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"]["type"] == "FREEZE_ACCOUNTS"
    assert _case_status(client, admin_headers, case["case_id"]) == "ACTIONED"
