def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["postgres"] == "ok"
    assert body["redis"] == "ok"


def test_health_reports_unhealthy_when_redis_down(client, monkeypatch):
    """Phase 2 DoD: /health must report unhealthy (503), not silently
    report ok, when a dependency is unreachable."""
    from app.core import redis_client

    class _BrokenRedis:
        def __getattr__(self, _name):
            def _raise(*_a, **_kw):
                raise ConnectionError("simulated Redis outage")
            return _raise

    monkeypatch.setattr(redis_client, "get_redis", lambda: _BrokenRedis())

    r = client.get("/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "unhealthy"
    assert body["redis"] == "unreachable"
    assert body["postgres"] == "ok"
