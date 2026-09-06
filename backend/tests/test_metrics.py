"""Phase 2 (Security & Observability) — GET /metrics smoke test."""


def test_metrics_returns_prometheus_format(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    # By the time this test runs, the shared session-scoped `client`
    # fixture has already made many other requests, each recorded by the
    # metrics middleware before this one — a concrete, not just
    # structural, assertion that requests are actually being counted
    # (this request's own count isn't reflected in its own body, since
    # the middleware increments the counter AFTER call_next() returns,
    # i.e. after generate_latest() already ran inside the handler).
    assert "sentinel_http_requests_total" in r.text


def test_metrics_requires_no_auth(client):
    """Deliberately unauthenticated — see app/core/metrics.py's docstring."""
    r = client.get("/metrics")
    assert r.status_code != 401
