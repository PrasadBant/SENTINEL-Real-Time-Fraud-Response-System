"""
Failure-injection tests for the hostile-review Phase 1 blockers:

  1. Redis unreachable during scoring/broadcast must not turn a
     successful Postgres transaction into an HTTP 500.
  2. app.core.repository.load_all() must not let a Redis failure (or a
     single bad record) abort restoration of the transactions/cases that
     come after it.

These monkeypatch app.core.redis_client's accessors to raise, rather
than relying on fakeredis actually failing — fakeredis doesn't fail on
its own, so simulating "Redis is down" means making the accessor itself
raise, exactly as a real connection error would surface to callers.
"""

import pytest

from conftest import TX_HEADERS, make_tx


class _BrokenRedis:
    """Stands in for a redis.Redis/redis.asyncio.Redis client whose
    connection is down — every method raises, matching what a real
    ConnectionError from redis-py looks like to a caller (any attribute
    access that turns into a call raises)."""

    def __getattr__(self, _name):
        def _raise(*_a, **_kw):
            raise ConnectionError("simulated Redis outage")
        return _raise


@pytest.fixture()
def broken_sync_redis(monkeypatch):
    """Makes app.core.redis_client.get_redis() (the sync client used by
    app/services/orchestrator.py) raise on every call, for the duration
    of one test."""
    from app.core import redis_client
    monkeypatch.setattr(redis_client, "get_redis", lambda: _BrokenRedis())


@pytest.fixture()
def broken_async_redis(monkeypatch):
    """Same as broken_sync_redis, for the async client used by
    app/websocket/connection_manager.py's broadcast()."""
    from app.core import redis_client

    class _BrokenAsyncRedis:
        async def publish(self, *_a, **_kw):
            raise ConnectionError("simulated Redis outage")

    monkeypatch.setattr(redis_client, "get_async_redis", lambda: _BrokenAsyncRedis())


def test_transaction_scoring_survives_redis_outage(client, broken_sync_redis):
    """Fix 1: orchestrator.record_velocity()/save_account()/get_account()
    must degrade gracefully, not raise, when Redis is unreachable — a
    transaction must still score and return 200, not 500, even though
    velocity/account data can't be read or written."""
    tx = make_tx(amount=1500)
    r = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["transaction"]["tx_id"] == tx["tx_id"]
    assert "risk_score" in body["transaction"]


def test_high_risk_case_creation_survives_redis_outage(client, broken_sync_redis):
    """Same as above but for the path that also creates a case and
    schedules an EC-03 timer — none of that should require Redis to be
    reachable for the HTTP response to succeed (EC-03 scheduling itself
    already degrades independently via EC03_QUEUE_ENABLED/withdrawal_queue's
    own try/except, exercised here incidentally)."""
    tx = make_tx(amount=350000, channel="IMPS", is_cross_border=True, on_active_call=True)
    r = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r.status_code == 200
    assert r.json()["case"] is not None


def test_broadcast_survives_redis_outage(client, broken_async_redis):
    """Fix 1: ConnectionManager.broadcast() must degrade gracefully, not
    raise, when Redis publish fails — a lost live-update notification
    must not turn an otherwise-successful request into an HTTP 500."""
    tx = make_tx(amount=1500)
    r = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r.status_code == 200


def test_both_redis_clients_down_still_returns_200(client, broken_sync_redis, broken_async_redis):
    """Belt-and-suspenders: both the scoring path's sync client AND the
    broadcast path's async client failing simultaneously (the realistic
    shape of "Redis is down") still must not 500 a transaction that
    Postgres can process and persist fine."""
    tx = make_tx(amount=350000, channel="IMPS", is_cross_border=True, on_active_call=True)
    r = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r.status_code == 200
    assert r.json()["transaction"]["risk_score"] is not None


def test_load_all_restores_everything_despite_redis_failure(monkeypatch):
    """Fix 2: a Redis outage during startup replay must not silently
    abort restoration of transactions or cases. Seeds several
    transactions and cases directly via the repository (Postgres), then
    calls load_all() with Redis unreachable, and asserts every single one
    still lands in the target store dict — not just the ones before
    whichever record happened to trigger the first Redis call."""
    from app.core import redis_client
    from app.core.repository import repository
    from conftest import unique_id

    monkeypatch.setattr(redis_client, "get_redis", lambda: _BrokenRedis())

    tx_ids = []
    for i in range(5):
        tx = make_tx(amount=100.0 * (i + 1))
        tx_ids.append(tx["tx_id"])
        repository.save_transaction(tx)

    case_ids = []
    for i in range(3):
        case_id = unique_id("CASE")
        case_ids.append(case_id)
        repository.save_case({
            "case_id": case_id, "status": "NEW", "origin_account": "ACC-X",
            "chain": ["ACC-X"], "max_nodes": 5, "total_fraud_amount": 0.0, "timeline": [],
        })

    store = {"transactions": {}, "cases": {}, "graphs": {}}
    repository.load_all(store)

    for tx_id in tx_ids:
        assert tx_id in store["transactions"], f"{tx_id} missing from restored transactions"
    for case_id in case_ids:
        assert case_id in store["cases"], f"{case_id} missing from restored cases"
