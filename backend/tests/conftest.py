"""
Shared pytest fixtures for the SENTINEL backend test suite.

Uses FastAPI's TestClient against the real `main.app` — no mocking of the
scoring pipeline, persistence layer, or auth stack. Tests use randomly
generated tx_id/account_id values (see `unique_id`/`make_tx`) so they don't
collide with each other or with pre-existing data in sentinel.db across
runs.
"""

import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
