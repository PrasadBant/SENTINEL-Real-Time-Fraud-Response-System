"""
AI Copilot Phase D: security hardening — input validation and the
per-user rate limiter on POST /api/copilot/chat.
"""

from app.core.security import create_access_token


def _headers_for(username: str, role: str = "viewer") -> dict:
    """Mints a token for a synthetic username not used by any other test
    (admin/viewer are shared across the whole session-scoped client
    fixture and already accumulate many copilot calls elsewhere) — keeps
    rate-limit tests isolated from unrelated tests' quota usage."""
    token = create_access_token(subject=username, role=role)
    return {"Authorization": f"Bearer {token}"}


def test_message_too_long_is_rejected(client, admin_headers):
    r = client.post(
        "/api/copilot/chat",
        json={"message": "x" * 2001, "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_blank_message_is_rejected(client, admin_headers):
    r = client.post(
        "/api/copilot/chat",
        json={"message": "   ", "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_empty_message_is_rejected(client, admin_headers):
    r = client.post(
        "/api/copilot/chat",
        json={"message": "", "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_context_case_id_too_long_is_rejected(client, admin_headers):
    r = client.post(
        "/api/copilot/chat",
        json={"message": "hello", "context_case_id": "X" * 65},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_message_at_max_length_is_accepted(client, admin_headers):
    r = client.post(
        "/api/copilot/chat",
        json={"message": "x" * 2000, "context_case_id": None},
        headers=admin_headers,
    )
    assert r.status_code == 200


def test_rate_limit_blocks_after_threshold_for_that_user_only(client):
    from app.services.copilot.rate_limit import MAX_REQUESTS_PER_WINDOW

    limited_user = _headers_for("rate-limit-subject-a")
    other_user = _headers_for("rate-limit-subject-b")

    for i in range(MAX_REQUESTS_PER_WINDOW):
        r = client.post(
            "/api/copilot/chat",
            json={"message": f"message number {i}"},
            headers=limited_user,
        )
        assert r.status_code == 200, f"request {i} should have succeeded"

    r = client.post(
        "/api/copilot/chat",
        json={"message": "one too many"},
        headers=limited_user,
    )
    assert r.status_code == 429

    # a different user is completely unaffected
    r_other = client.post(
        "/api/copilot/chat",
        json={"message": "hello from a different user"},
        headers=other_user,
    )
    assert r_other.status_code == 200


def test_history_endpoints_are_not_rate_limited(client, admin_headers):
    """Only the LLM-triggering chat route carries the rate limit — reading
    or deleting history should never 429 regardless of chat volume."""
    r = client.get("/api/copilot/history", headers=admin_headers)
    assert r.status_code == 200
