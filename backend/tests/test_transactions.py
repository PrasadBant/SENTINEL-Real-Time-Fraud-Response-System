"""
Transaction ingestion: input validation, scoring pipeline, case creation,
and the threshold/score consistency invariant (regression test for the
Phase 2 bugfix — see git history for orchestrator.py).
"""

from conftest import TX_HEADERS, make_tx


def test_valid_transaction_returns_score_fields(client):
    r = client.post("/transaction", json=make_tx(amount=1500), headers=TX_HEADERS)
    assert r.status_code == 200
    tx = r.json()["transaction"]
    assert "risk_score" in tx
    assert "rule_score" in tx
    assert "ml_score" in tx
    assert "threshold" in tx
    assert tx["threshold"] in ("LOW", "MEDIUM", "HIGH_RISK")


def test_missing_required_field_rejected(client):
    bad = make_tx()
    del bad["amount"]
    r = client.post("/transaction", json=bad, headers=TX_HEADERS)
    assert r.status_code == 422


def test_non_positive_amount_rejected(client):
    r = client.post("/transaction", json=make_tx(amount=-5), headers=TX_HEADERS)
    assert r.status_code == 422


def test_empty_tx_id_rejected(client):
    r = client.post("/transaction", json=make_tx(tx_id=""), headers=TX_HEADERS)
    assert r.status_code == 422


def test_high_risk_transaction_creates_case(client):
    tx = make_tx(amount=350000, channel="IMPS", is_cross_border=True, on_active_call=True)
    r = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["case"] is not None
    assert body["case"]["case_id"]
    assert body["transaction"]["risk_score"] >= 60


def test_extra_simulator_flags_pass_through(client):
    """extra='allow' on the Transaction model must not strip risk-signal flags."""
    tx = make_tx(amount=250000, is_crypto_related=True, velocity_flag=True)
    r = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r.status_code == 200
    factors = {f["name"] for f in r.json()["transaction"]["risk_factors"]}
    assert "crypto_risk" in factors
    assert "velocity_spike" in factors


def test_threshold_always_matches_final_score(client):
    """
    Regression test: the GNN re-score used to overwrite risk_score without
    recomputing threshold, so a transaction could show e.g. score=58 labeled
    HIGH_RISK. Run enough transactions to exercise the GNN branch (which
    only fires once a case has >= 2 graph nodes) and assert the label
    always matches the score's own bucket.
    """
    from app.core.config import HIGH_RISK_THRESHOLD, MEDIUM_THRESHOLD

    for _ in range(8):
        tx = make_tx(amount=60000, channel="IMPS")
        r = client.post("/transaction", json=tx, headers=TX_HEADERS)
        assert r.status_code == 200
        t = r.json()["transaction"]
        score, threshold = t["risk_score"], t["threshold"]
        expected = (
            "HIGH_RISK" if score >= HIGH_RISK_THRESHOLD
            else "MEDIUM" if score >= MEDIUM_THRESHOLD
            else "LOW"
        )
        assert threshold == expected, f"score={score} labeled {threshold}, expected {expected}"


def test_mule_chain_hop_decays_from_origin_score(client):
    origin = make_tx(amount=300000, channel="IMPS", is_cross_border=True)
    r1 = client.post("/transaction", json=origin, headers=TX_HEADERS)
    assert r1.status_code == 200
    case_id = r1.json()["case"]["case_id"]
    origin_rule_score = r1.json()["transaction"]["rule_score"]

    hop1 = make_tx(
        sender_account=origin["receiver_account"],
        amount=150000,
        channel="NEFT",
        hop_number=1,
        case_id=case_id,
    )
    r2 = client.post("/transaction", json=hop1, headers=TX_HEADERS)
    assert r2.status_code == 200
    hop1_rule_score = r2.json()["transaction"]["rule_score"]

    from app.core.config import DECAY_FACTOR
    assert hop1_rule_score == int(origin_rule_score * DECAY_FACTOR)
