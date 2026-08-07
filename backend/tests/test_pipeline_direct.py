"""
Direct (non-HTTP) pipeline smoke test — supersedes the old ad-hoc
test_runner.py script (import-check + a single manual assertion, not
pytest-discoverable, no CI wiring). Exercises run_pipeline() directly
against the in-memory data_store, bypassing the API/auth layer entirely.
"""

from app.core.data_store import data_store
from app.services.orchestrator import run_pipeline
from conftest import make_tx


def test_pipeline_scores_a_transaction_directly():
    tx = make_tx(amount=150.50, channel="WEB")
    result = run_pipeline(tx, data_store)

    assert result["transaction"]["tx_id"] == tx["tx_id"]
    assert "risk_score" in result["transaction"]
    assert data_store["transactions"][tx["tx_id"]]["tx_id"] == tx["tx_id"]
