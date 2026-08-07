"""
AI Copilot Phase F: fraud domain knowledge (app/services/copilot/knowledge.py)
and the recommendation logic it feeds into (pattern-specific investigation
steps on 'explain transaction' and 'what should I investigate next',
instead of the same generic boilerplate regardless of fraud type).
"""

from conftest import TX_HEADERS, make_tx


def test_what_is_mule_chain(client, admin_headers):
    r = client.post(
        "/api/copilot/chat",
        json={"message": "What is a mule chain?"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert "Money Muling / Mule Chains" in reply
    assert "Investigation steps" in reply
    assert "golden_window_minutes" in reply  # ties back to SENTINEL's own case model


def test_explain_sim_swap_fraud(client, admin_headers):
    r = client.post(
        "/api/copilot/chat",
        json={"message": "Explain SIM swap fraud to me"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert "SIM Swap Fraud" in r.json()["reply"]


def test_explain_account_takeover(client, admin_headers):
    r = client.post(
        "/api/copilot/chat",
        json={"message": "how does account takeover work?"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert "Account Takeover" in r.json()["reply"]


def test_explain_crypto_drain(client, admin_headers):
    r = client.post(
        "/api/copilot/chat",
        json={"message": "what is crypto drain"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert "Crypto Drain" in r.json()["reply"]


def test_general_concept_not_modeled_by_sentinel(client, admin_headers):
    r = client.post(
        "/api/copilot/chat",
        json={"message": "What is friendly fraud?"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert "Friendly fraud" in reply
    assert "doesn't model merchant" in reply


def test_unrecognized_term_falls_through_to_freeform(client, admin_headers):
    """A fraud-sounding question that doesn't match any known pattern/
    concept alias must still get a non-empty reply via the freeform/
    offline-fallback path, not silence or an error."""
    r = client.post(
        "/api/copilot/chat",
        json={"message": "what is quantum ledger fraud"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["reply"]


def test_recommend_next_case_uses_pattern_specific_steps():
    """Direct, isolated unit test rather than going through the shared
    session-scoped client: by this point in the suite many other copilot
    tests have already left their own un-actioned high-risk cases in
    data_store (e.g. test_copilot_intents.py's cross-border fixtures), so
    asserting on 'the' top-urgency case via the real /api/copilot/chat
    endpoint would be at the mercy of tie-breaking across the whole
    accumulated test session rather than testing this function's logic."""
    from app.core.data_store import data_store
    from app.services.copilot.intents import _recommend_next

    case_id = "CASE-RECOMMEND-TEST"
    tx_id = "TX-RECOMMEND-TEST"
    original_cases = data_store["cases"]
    original_txs = data_store["transactions"]
    try:
        data_store["transactions"] = {
            tx_id: {
                "tx_id": tx_id,
                "amount": 400000,
                "channel": "NEFT",
                "sender_account": "ACC-A",
                "receiver_account": "ACC-B",
                "risk_score": 100,
                "risk_factors": [
                    {"name": "cross_border_risk", "weight": 0.5, "value": 100, "contribution": 50},
                    {"name": "new_receiver", "weight": 0.35, "value": 100, "contribution": 35},
                ],
            }
        }
        data_store["cases"] = {
            case_id: {
                "case_id": case_id,
                "status": "HIGH_RISK",
                "risk_level": 100,
                "urgency_score": 999.0,  # guaranteed max — isolated store, no other cases to tie with
                "golden_window_minutes": 20,
                "total_fraud_amount": 400000,
                "transactions": [tx_id],
            }
        }

        reply = _recommend_next()

        assert "Pattern match" in reply
        assert "Cross-Border Fraud" in reply
        # pattern-specific step text, not the old always-the-same generic steps
        assert "correspondent-bank cooperation" in reply
        assert case_id in reply
    finally:
        data_store["cases"] = original_cases
        data_store["transactions"] = original_txs


def test_explain_transaction_surfaces_likely_pattern(client, admin_headers):
    tx = make_tx(amount=350000, channel="IMPS", is_crypto_related=True)
    r = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r.status_code == 200
    tx_id = r.json()["transaction"]["tx_id"]

    reply = client.post(
        "/api/copilot/chat",
        json={"message": f"why was {tx_id} flagged?"},
        headers=admin_headers,
    ).json()["reply"]

    assert "Likely pattern:" in reply
    assert "Crypto Drain" in reply


def test_case_context_includes_likely_pattern_for_llm_path():
    """Direct unit test of the context builder (used by the freeform LLM
    path and Mock/offline fallback, not just the structured intents) --
    confirms pattern cross-referencing reaches that path too."""
    from app.core.data_store import data_store
    from app.services.copilot.context_builder import case_context

    case_id = "CASE-KNOWLEDGE-TEST"
    tx_id = "TX-KNOWLEDGE-TEST"
    data_store["transactions"][tx_id] = {
        "tx_id": tx_id,
        "amount": 500000,
        "channel": "NEFT",
        "sender_account": "ACC-A",
        "receiver_account": "ACC-B",
        "risk_score": 95,
        "threshold": "HIGH_RISK",
        "risk_factors": [{"name": "velocity_spike", "weight": 0.4, "value": 100, "contribution": 40}],
    }
    data_store["cases"][case_id] = {
        "case_id": case_id,
        "status": "HIGH_RISK",
        "risk_level": 95,
        "urgency_score": 100.0,
        "golden_window_minutes": 20,
        "total_fraud_amount": 500000,
        "recoverable_amount": 0,
        "origin_account": "ACC-A",
        "chain": ["ACC-A", "ACC-B"],
        "transactions": [tx_id],
        "actions_taken": [],
    }

    context = case_context(case_id)
    assert "Likely Pattern(s):" in context
    assert "Velocity Attacks" in context

    del data_store["transactions"][tx_id]
    del data_store["cases"][case_id]
