"""
AI Copilot Phase B: structured, data-exact intents (context_builder +
intents) — these must answer directly from data_store without going
through an LLM, so responses are deterministic and assertable exactly,
unlike the freeform LLM path.
"""

from conftest import TX_HEADERS, make_tx


def _create_high_risk_case(client):
    tx = make_tx(amount=300000, channel="NEFT", is_cross_border=True)
    r = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r.status_code == 200
    body = r.json()
    return body["case"], body["transaction"]


def test_explain_transaction_by_id_returns_exact_scoring_breakdown(client, admin_headers):
    _case, tx = _create_high_risk_case(client)
    tx_id = tx["tx_id"]

    r = client.post(
        "/api/copilot/chat",
        json={"message": f"why was {tx_id} flagged?", "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert tx_id in reply
    assert "Risk Score" in reply
    assert str(tx["amount"]) in reply.replace(",", "") or f"{tx['amount']:,.2f}" in reply


def test_explain_unknown_transaction_id_reports_not_found(client, admin_headers):
    r = client.post(
        "/api/copilot/chat",
        json={"message": "explain TX-DOESNOTEXIST", "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert "No transaction found" in r.json()["reply"]


def test_summarize_case_by_id_returns_case_details(client, admin_headers):
    case, _tx = _create_high_risk_case(client)
    case_id = case["case_id"]

    r = client.post(
        "/api/copilot/chat",
        json={"message": f"summarize {case_id}", "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert case_id in reply
    assert "Risk Level" in reply


def test_list_high_risk_cases_intent(client, admin_headers):
    _create_high_risk_case(client)

    r = client.post(
        "/api/copilot/chat",
        json={"message": "show me open high-risk cases", "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert "High-Risk Cases" in reply


def test_recommend_next_case_intent(client, admin_headers):
    _create_high_risk_case(client)

    r = client.post(
        "/api/copilot/chat",
        json={"message": "what should I investigate next?", "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert "Recommended next case" in reply or "queue is clear" in reply


def test_dashboard_stats_intent_matches_live_data(client, admin_headers):
    _create_high_risk_case(client)

    r = client.post(
        "/api/copilot/chat",
        json={"message": "what is the total exposure?", "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert "Total Exposure" in reply
    assert "Total Cases" in reply


def test_transaction_search_by_channel(client, admin_headers):
    _create_high_risk_case(client)  # NEFT channel

    r = client.post(
        "/api/copilot/chat",
        json={"message": "show me NEFT transactions", "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert "Transaction Search" in reply
    assert "channel=NEFT" in reply


def test_freeze_intent_still_takes_priority_over_structured_intents(client, admin_headers):
    """Regression: admin-gated action intents (checked in copilot.py's own
    if/elif) must still win over structured intents when both a case is
    selected and the message says 'freeze' — Phase B must not have
    reordered this."""
    case, _tx = _create_high_risk_case(client)

    r = client.post(
        "/api/copilot/chat",
        json={"message": "please freeze this case", "context_case_id": case["case_id"]},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["action"]["type"] == "FREEZE_ACCOUNTS"


def test_freeform_question_without_structured_match_falls_through_to_llm_path(client, admin_headers):
    """A message that doesn't match any structured intent (no TX/CASE ID,
    no recognized keyword) must still get a non-empty reply via the
    Mock/offline fallback path — this is the existing test_copilot.py
    contract, re-verified now that Phase B sits in front of it."""
    r = client.post(
        "/api/copilot/chat",
        json={"message": "hello there", "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["reply"]
