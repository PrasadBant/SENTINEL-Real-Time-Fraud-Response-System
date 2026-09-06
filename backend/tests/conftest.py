"""
Shared pytest fixtures for the SENTINEL backend test suite.

Uses FastAPI's TestClient against the real `main.app` — no mocking of the
scoring pipeline, persistence layer, or auth stack. Tests use randomly
generated tx_id/account_id values (see `unique_id`/`make_tx`) so they don't
collide with each other within the shared in-memory data_store over the
course of a session (see `client` below).

The suite used to run against the real backend/sentinel.db, which meant
every local run permanently wrote rows like the rate-limit fixtures'
synthetic usernames into it. It now runs against a throwaway SQLite file
per session instead (see the DATABASE_URL override below) — set
TEST_DATABASE_URL to point it at something else (e.g. a Postgres test
instance in CI).

Same "container-free by default" posture for Redis: unless TEST_REDIS_URL
is set, app.core.redis_client's accessors are swapped for fakeredis
in-memory instances below, so velocity-cache/account/WS-pub-sub/EC-03
code paths run without a real Redis. See tests/test_redis_integration.py
for the narrow opt-in suite that runs against a real one instead.
"""

import os
import sys
import tempfile
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Must happen before `import main`: app.core.database reads DATABASE_URL
# and binds its engine at import time, so setting this any later would be
# a no-op and tests would silently fall through to the real sentinel.db.
_TEST_DB_PATH = os.path.join(tempfile.gettempdir(), f"sentinel_test_{uuid.uuid4().hex}.db")
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", f"sqlite:///{_TEST_DB_PATH}")

# Same "must happen before `import main`" reasoning: app.core.users now
# raises at import time if ADMIN_PASSWORD/VIEWER_PASSWORD aren't set (it
# no longer falls back to admin123/viewer123). setdefault (not a hard
# overwrite) so a real deployment's env still wins if these somehow leak
# into that environment's process.
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")
os.environ.setdefault("VIEWER_USERNAME", "viewer")
os.environ.setdefault("VIEWER_PASSWORD", "viewer123")

# app/services/withdrawal_queue.py talks to Arq's own Redis pool
# directly, which fakeredis can't stand in for — without this, every
# HIGH_RISK-case test would hit Arq's real connection-retry backoff
# against a Redis that isn't there, measurably slowing the whole suite
# down (schedule()/cancel() already degrade safely, just slowly).
# tests/test_redis_integration.py re-enables this against a real Redis.
os.environ.setdefault("EC03_QUEUE_ENABLED", "false")

# Redis: same escape hatch shape as TEST_DATABASE_URL above, and same
# "must happen before the first import that reads it" reasoning —
# app.core.config reads REDIS_URL at import time (a plain module-level
# `os.getenv(...)` call), and app.core.redis_client imports that name
# from config at ITS OWN import time, so setting this env var any later
# than the `import redis_client` below would be a no-op. If a real Redis
# instance is supplied via TEST_REDIS_URL, point REDIS_URL at it and let
# app.core.redis_client connect for real (this is also how
# tests/test_redis_integration.py is meant to be run for a full-suite
# pass). Otherwise, substitute fakeredis instances by replacing
# get_redis()/get_async_redis() themselves — not their return values —
# since app code calls these via the `redis_client` module reference
# (e.g. `redis_client.get_redis()`), never via a `from ... import
# get_redis` binding, specifically so this kind of module-level
# monkeypatch reaches every call site.
if "TEST_REDIS_URL" in os.environ:
    os.environ["REDIS_URL"] = os.environ["TEST_REDIS_URL"]

# Also before any app.core.config import (see the comment above): main.py
# normally calls this first, before importing anything that transitively
# imports app.core.config (whose SECRET_KEY-fallback warning fires at
# import time) — but here `import redis_client` on the very next line
# does exactly that, ahead of `import main` below, so call it here too
# rather than let that one line fall back to unconfigured plain-text
# logging during tests.
from app.core.logging_config import configure_logging  # noqa: E402
configure_logging()

from app.core import redis_client  # noqa: E402

if "TEST_REDIS_URL" not in os.environ:
    import fakeredis  # noqa: E402

    _fake_sync_redis = fakeredis.FakeRedis(decode_responses=True)
    _fake_async_redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    redis_client.get_redis = lambda: _fake_sync_redis
    redis_client.get_async_redis = lambda: _fake_async_redis

from fastapi.testclient import TestClient

import main

# Matches the default in app/core/config.py (SIMULATOR_API_KEY) unless the
# environment overrides it — keep these in sync if you change one.
TX_HEADERS = {"X-API-Key": os.getenv("SIMULATOR_API_KEY", "sentinel-dev-simulator-key")}


@pytest.fixture(scope="session")
def client():
    # Using the context-manager form runs FastAPI's startup event (DB init,
    # state restore, background analyzer task) exactly once for the whole
    # test session — a plain `TestClient(main.app)` skips lifespan entirely.
    with TestClient(main.app) as c:
        yield c
    # Best-effort cleanup of the throwaway DB file created above. Skipped
    # when TEST_DATABASE_URL was supplied — that DB is the caller's to manage.
    if "TEST_DATABASE_URL" not in os.environ:
        from app.core.database import engine

        # SQLAlchemy's connection pool keeps the sqlite file handle open
        # even after every individual session is closed; on Windows that
        # makes os.remove() fail silently (a PermissionError, which is an
        # OSError) unless the pool's connections are disposed first.
        engine.dispose()
        try:
            os.remove(_TEST_DB_PATH)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _reset_copilot_rate_limit():
    # The whole suite reuses the same two demo accounts (admin/viewer)
    # across dozens of copilot tests spread over several files, all
    # running within the same real-world minute — without a per-test
    # reset, the shared 30-req/60s quota (app/services/copilot/
    # rate_limit.py) exhausts partway through the suite and later,
    # unrelated tests start failing with 429s that have nothing to do
    # with what they're actually testing. The rate limiter itself is
    # untouched in production; this fixture only exists here.
    from app.services.copilot import rate_limit

    rate_limit.reset()
    yield


@pytest.fixture
def admin_token(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def viewer_token(client):
    r = client.post("/auth/login", json={"username": "viewer", "password": "viewer123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def viewer_headers(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}"}


def unique_id(prefix: str = "TX") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def make_tx(**overrides) -> dict:
    tx = {
        "tx_id": unique_id("TX"),
        "timestamp": "2026-08-07T23:00:00Z",
        "sender_account": unique_id("ACC"),
        "receiver_account": unique_id("ACC"),
        "amount": 1000.0,
        "channel": "UPI",
        "hop_number": 0,
    }
    tx.update(overrides)
    return tx
