"""
Phase 2 hostile-review fix (CRITICAL) — WebSocket cross-tenant leak.

Reproduces the exact exploit from the hostile review: two WebSocket
connections for two different tenants both received every broadcast
message regardless of which tenant it belonged to (live-verified via a
direct ConnectionManager repro: a tenant-a broadcast was delivered
verbatim to a tenant-b socket). Fixed by keying active_connections by
tenant_id and publishing to per-tenant Redis channels (see
app/websocket/connection_manager.py) — these tests prove both the core
delivery logic (direct, deterministic) and the real end-to-end wiring
(the actual /ws endpoint, tenant_id pulled from the JWT) are isolated.
"""

import concurrent.futures

from app.core.repository import repository
from app.core.security import hash_password


def _try_receive_json(ws, timeout: float = 1.5):
    """WebSocketTestSession.receive_json() blocks indefinitely if nothing
    arrives — there's no built-in timeout in Starlette's TestClient. Runs
    it in a throwaway thread and gives up after `timeout` seconds,
    returning None to mean "nothing arrived" (the expected outcome when
    proving isolation: the OTHER tenant's socket must receive nothing).
    The blocked worker thread is abandoned (shutdown(wait=False)) rather
    than joined, since a genuinely leaking message means it would never
    return on its own — acceptable for a test process that exits shortly
    after."""
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(ws.receive_json)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return None
    finally:
        ex.shutdown(wait=False)


def test_deliver_local_only_reaches_the_matching_tenant():
    """Direct, deterministic reproduction of the exact hostile-review
    exploit at the ConnectionManager level: two sockets tagged with
    different tenants, one broadcast on tenant-a's channel, assert
    tenant-b's socket receives nothing and tenant-a's receives it."""
    import asyncio
    from app.websocket.connection_manager import ConnectionManager

    class _FakeWS:
        def __init__(self):
            self.received = []

        async def send_json(self, msg):
            self.received.append(msg)

    async def _run():
        mgr = ConnectionManager()
        ws_a, ws_b = _FakeWS(), _FakeWS()
        mgr.active_connections["tenant-a"] = [ws_a]
        mgr.active_connections["tenant-b"] = [ws_b]

        await mgr._deliver_local("tenant-a", {
            "event": "case_updated",
            "case_id": "CASE-TENANT-A-SECRET",
            "total_fraud_amount": 12345678.0,
        })
        return ws_a.received, ws_b.received

    received_a, received_b = asyncio.run(_run())
    assert len(received_a) == 1, "tenant-a's own socket should receive its own tenant's broadcast"
    assert received_b == [], f"tenant-b's socket must receive NOTHING from tenant-a's broadcast; got: {received_b}"


def test_websocket_endpoint_delivers_only_own_tenant_events(client):
    """Full end-to-end reproduction through the real /ws endpoint,
    real JWTs (real tenant_id claims), and the real fakeredis-backed
    pub/sub — not just the internal delivery method in isolation above.
    Two tenants each open a real WebSocket connection; an action taken
    against tenant A's case must be delivered to tenant A's socket and
    NEVER to tenant B's."""
    repository.create_user("ws-investigator-a", hash_password("pw12345"), "admin", tenant_id="ws-tenant-a")
    repository.create_user("ws-investigator-b", hash_password("pw12345"), "admin", tenant_id="ws-tenant-b")

    case_id = "CASE-WS-ISOLATION-TEST"
    repository.save_case(
        {
            "case_id": case_id, "status": "HIGH_RISK", "origin_account": "ACC-WS-A",
            "chain": ["ACC-WS-A"], "max_nodes": 5, "total_fraud_amount": 5000.0,
            "recoverable_amount": 5000.0, "recovery_pct": 100.0, "golden_window_minutes": 20,
            "actions_taken": [], "timeline": [],
        },
        tenant_id="ws-tenant-a",
    )

    token_a = client.post("/auth/login", json={"username": "ws-investigator-a", "password": "pw12345"}).json()["access_token"]
    token_b = client.post("/auth/login", json={"username": "ws-investigator-b", "password": "pw12345"}).json()["access_token"]

    with client.websocket_connect(f"/ws?token={token_a}") as ws_a, \
         client.websocket_connect(f"/ws?token={token_b}") as ws_b:
        hello_a = ws_a.receive_json()
        hello_b = ws_b.receive_json()
        assert hello_a["event"] == "connected"
        assert hello_b["event"] == "connected"

        # A real admin action against tenant A's case — this is exactly
        # the broadcast path (app/api/actions.py::handle_action) the
        # hostile review found leaking to every connected socket.
        r = client.post(
            "/action/freeze",
            json={"case_id": case_id, "account_id": "GLOBAL"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # Tenant A's own socket must receive the action + case_updated events.
        msg1 = _try_receive_json(ws_a)
        msg2 = _try_receive_json(ws_a)
        events_a = {m.get("event") for m in (msg1, msg2) if m}
        assert "action_taken" in events_a or "case_updated" in events_a, (
            f"tenant A's own socket should have received its own action's broadcasts; got {msg1!r}, {msg2!r}"
        )

        # Tenant B's socket must receive NOTHING from tenant A's action.
        leaked = _try_receive_json(ws_b)
        assert leaked is None, (
            f"CROSS-TENANT LEAK: tenant B's socket received a message that belongs "
            f"to tenant A's case: {leaked!r}"
        )
