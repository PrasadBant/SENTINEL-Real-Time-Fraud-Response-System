"""
Redis-specific behavior for the Phase 1 shared-state/pub-sub/EC-03 work.

The rest of the suite runs against fakeredis by default (see
conftest.py) — deliberate, not an oversight: velocity_cache/accounts/WS
pub-sub all go through app.core.redis_client, which fakeredis stands in
for faithfully enough that testing business logic against it is
sufficient. This module exists for the one thing that genuinely can't be
faked: app.services.withdrawal_queue.py talks to Arq's own Redis pool
directly (Arq needs real atomic dequeue/dedup semantics), and pub/sub
fanout across independently-constructed clients is worth proving crosses
real process boundaries, not just a single in-memory fakeredis object
shared within one test process.

Skipped entirely unless TEST_REDIS_URL points at a real Postgres... er,
Redis instance — e.g.:
    TEST_REDIS_URL=redis://localhost:6379/0 \
        pytest tests/test_redis_integration.py -v

Not part of the default `pytest` run wired into CI (same rationale as
Phase 0's tests/test_repository_postgres.py) — keeps CI fast and
container-free for now.
"""

import asyncio
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    "TEST_REDIS_URL" not in os.environ,
    reason="set TEST_REDIS_URL to a real Redis instance to run these",
)


@pytest.fixture()
def real_redis_url():
    return os.environ["TEST_REDIS_URL"]


@pytest.fixture()
def ec03_enabled(monkeypatch):
    """EC03_QUEUE_ENABLED is read by app.core.config at import time and
    bound into app.services.withdrawal_queue's own namespace at ITS
    import time — setting the env var here would be a no-op by the time
    this fixture runs (both modules are already imported). Patch the
    already-bound name directly instead, which is what actually gates
    schedule()/cancel()'s behavior."""
    import app.services.withdrawal_queue as wq
    monkeypatch.setattr(wq, "EC03_QUEUE_ENABLED", True)


async def _cleanup_pool():
    """withdrawal_queue.py caches its Arq pool as a module-level
    singleton (see its docstring on why — same lazy pattern as
    app.core.redis_client) — reset it between tests in this module so
    each test's TEST_REDIS_URL is honored fresh rather than reusing a
    pool opened against a stale URL from a previous test run."""
    import app.services.withdrawal_queue as wq
    wq._pool = None


@pytest.fixture(autouse=True)
def _reset_pool_between_tests():
    asyncio.run(_cleanup_pool())
    yield
    asyncio.run(_cleanup_pool())


def test_cross_client_pubsub_fanout(real_redis_url):
    """Two independently-constructed async Redis clients — simulating two
    API replicas, each running its own connection_manager.listen() —
    prove a publish from one is actually delivered to a subscriber on
    the other. A single fakeredis instance can't tell you this crosses a
    real process boundary; two real connections to the same server can."""
    import redis.asyncio as aioredis

    channel = f"test-channel-{uuid.uuid4().hex[:8]}"

    async def _run():
        publisher = aioredis.Redis.from_url(real_redis_url, decode_responses=True)
        subscriber_client = aioredis.Redis.from_url(real_redis_url, decode_responses=True)
        pubsub = subscriber_client.pubsub()
        await pubsub.subscribe(channel)

        received = []

        async def listen():
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                received.append(msg["data"])
                break

        listener_task = asyncio.create_task(listen())
        await asyncio.sleep(0.2)  # let the subscribe actually register server-side
        await publisher.publish(channel, "hello-from-replica-a")
        await asyncio.wait_for(listener_task, timeout=5)

        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await publisher.aclose()
        await subscriber_client.aclose()
        return received

    received = asyncio.run(_run())
    assert received == ["hello-from-replica-a"]


def test_schedule_dedup_by_job_id(real_redis_url, ec03_enabled, monkeypatch):
    """Arq's own _job_id dedup: a second schedule() call with the same
    key while the first is still pending must be rejected, atomically —
    no separate is_active()-then-register() race window."""
    monkeypatch.setenv("REDIS_URL", real_redis_url)
    import app.core.config as cfg
    monkeypatch.setattr(cfg, "REDIS_URL", real_redis_url)
    import app.services.withdrawal_queue as wq
    monkeypatch.setattr(wq, "REDIS_URL", real_redis_url)

    key = f"CASE-DEDUP-{uuid.uuid4().hex[:8]}:ACC-X"

    async def _run():
        first = await wq.schedule(key, "CASE-DEDUP", "ACC-X", delay_seconds=30, correlation_id="corr-1")
        second = await wq.schedule(key, "CASE-DEDUP", "ACC-X", delay_seconds=30, correlation_id="corr-1")
        return first, second

    first, second = asyncio.run(_run())
    assert first is True
    assert second is False


def test_schedule_fire_and_cancel(real_redis_url, ec03_enabled, monkeypatch):
    """End-to-end against a real Arq worker: a scheduled withdrawal
    actually fires and mutates the graph node when not cancelled in
    time, and does NOT fire when cancelled first — both via the real
    Job.abort()/worker dequeue mechanics, not a mock."""
    monkeypatch.setenv("REDIS_URL", real_redis_url)
    import app.core.config as cfg
    monkeypatch.setattr(cfg, "REDIS_URL", real_redis_url)
    import app.services.withdrawal_queue as wq
    monkeypatch.setattr(wq, "REDIS_URL", real_redis_url)

    from arq.connections import RedisSettings
    from arq.worker import Worker

    from app.core.data_store import data_store
    from app.services.withdrawal_simulator import run_withdrawal_job

    # data_store is the same process-global singleton every other test's
    # run_pipeline() scans (orchestrator.py:164 unconditionally accesses
    # c["origin_account"]/c["chain"] on every case in store["cases"]) —
    # a malformed/partial case dict here would crash unrelated tests that
    # happen to run afterward in the same session. Use fully-shaped case
    # dicts (matching app/engines/case_manager.py's real shape) and clean
    # up in `finally`, same defensive pattern tests/test_copilot_knowledge.py
    # already uses for the same shared-singleton reason.
    def _fake_case(case_id):
        return {
            "case_id": case_id, "status": "HIGH_RISK", "origin_account": "unused",
            "chain": [], "max_nodes": 5, "total_fraud_amount": 1000.0, "timeline": [],
        }

    fire_case = f"CASE-FIRE-{uuid.uuid4().hex[:8]}"
    cancel_case = f"CASE-CANCEL-{uuid.uuid4().hex[:8]}"
    data_store.setdefault("cases", {})[fire_case] = _fake_case(fire_case)
    data_store.setdefault("graphs", {})[fire_case] = {
        "nodes": [{"account_id": "ACC-FIRE", "status": "active", "balance": 500.0}], "edges": [],
    }
    data_store["cases"][cancel_case] = _fake_case(cancel_case)
    data_store["graphs"][cancel_case] = {
        "nodes": [{"account_id": "ACC-CANCEL", "status": "active", "balance": 500.0}], "edges": [],
    }

    async def _run():
        worker = Worker(
            functions=[run_withdrawal_job],
            redis_settings=RedisSettings.from_dsn(real_redis_url),
            allow_abort_jobs=True,
            handle_signals=False,
            poll_delay=0.2,
        )
        worker_task = asyncio.create_task(worker.async_run())
        await asyncio.sleep(0.3)  # let the worker start polling

        try:
            fire_key = f"{fire_case}:ACC-FIRE"
            await wq.schedule(fire_key, fire_case, "ACC-FIRE", delay_seconds=1, correlation_id="corr-fire")

            cancel_key = f"{cancel_case}:ACC-CANCEL"
            await wq.schedule(cancel_key, cancel_case, "ACC-CANCEL", delay_seconds=3, correlation_id="corr-cancel")
            await asyncio.sleep(0.5)
            cancelled = await wq.cancel(cancel_key)

            await asyncio.sleep(4)  # past both delays
            return cancelled
        finally:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    try:
        cancelled = asyncio.run(_run())

        assert cancelled is True
        assert data_store["graphs"][fire_case]["nodes"][0]["status"] == "withdrawn"
        assert data_store["graphs"][fire_case]["nodes"][0]["balance"] == 0.0
        assert data_store["graphs"][cancel_case]["nodes"][0]["status"] == "active"
    finally:
        # Belt-and-suspenders on top of the well-formed dicts above: don't
        # leave these in the shared data_store singleton for later tests
        # in the same session to trip over.
        data_store["cases"].pop(fire_case, None)
        data_store["cases"].pop(cancel_case, None)
        data_store["graphs"].pop(fire_case, None)
        data_store["graphs"].pop(cancel_case, None)
