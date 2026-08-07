"""
AI Copilot Phase E (backend half): POST /api/copilot/chat/stream — same
three-tier resolution as /api/copilot/chat, emitted as Server-Sent
Events. TestClient drains the whole stream synchronously (no real
network connection involved), so these tests assert on the full
sequence of parsed events rather than real-time incremental delivery.
"""

import json

from app.core.security import create_access_token
from conftest import TX_HEADERS, make_tx


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: ") :]))
    return events


def _create_high_risk_case(client):
    tx = make_tx(amount=300000, channel="NEFT", is_cross_border=True)
    r = client.post("/transaction", json=tx, headers=TX_HEADERS)
    assert r.status_code == 200
    return r.json()["case"]


def test_stream_structured_intent_emits_start_delta_done(client, admin_headers):
    r = client.post(
        "/api/copilot/chat/stream",
        json={"message": "show me open high-risk cases"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(r.text)
    assert events[0]["type"] == "start"
    assert events[0]["conversation_id"]

    deltas = [e for e in events if e["type"] == "delta"]
    assert deltas
    assert "High-Risk Cases" in "".join(d["text"] for d in deltas)

    done = events[-1]
    assert done["type"] == "done"
    assert done["conversation_id"] == events[0]["conversation_id"]
    assert done["action"] is None


def test_stream_freeze_intent_executes_and_reports_action(client, admin_headers):
    case = _create_high_risk_case(client)

    r = client.post(
        "/api/copilot/chat/stream",
        json={"message": "please freeze this case", "context_case_id": case["case_id"]},
        headers=admin_headers,
    )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    done = events[-1]
    assert done["type"] == "done"
    assert done["action"]["type"] == "FREEZE_ACCOUNTS"

    cases = client.get("/cases", headers=admin_headers).json()
    updated = next(c for c in cases if c["case_id"] == case["case_id"])
    assert updated["status"] == "ACTIONED"


def test_stream_viewer_freeze_denied(client, viewer_headers):
    r = client.post(
        "/api/copilot/chat/stream",
        json={"message": "please freeze this case", "context_case_id": "CASE-WHATEVER"},
        headers=viewer_headers,
    )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    deltas = [e for e in events if e["type"] == "delta"]
    assert any("admin" in d["text"].lower() for d in deltas)
    assert events[-1]["action"] is None


def test_stream_freeform_falls_through_and_persists_to_history(client, admin_headers):
    r = client.post(
        "/api/copilot/chat/stream",
        json={"message": "hello there"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    conv_id = events[0]["conversation_id"]
    deltas = [e for e in events if e["type"] == "delta"]
    assert deltas
    full_text = "".join(d["text"] for d in deltas)
    assert full_text

    history = client.get(f"/api/copilot/history?conversation_id={conv_id}", headers=admin_headers).json()
    messages = history["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == full_text


def test_stream_requires_auth(client):
    r = client.post("/api/copilot/chat/stream", json={"message": "hello"})
    assert r.status_code == 401


def test_stream_message_validation_still_applies(client, admin_headers):
    r = client.post(
        "/api/copilot/chat/stream",
        json={"message": "   "},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_stream_rate_limit_applies(client):
    from app.services.copilot.rate_limit import MAX_REQUESTS_PER_WINDOW

    token = create_access_token(subject="rate-limit-stream-subject", role="viewer")
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(MAX_REQUESTS_PER_WINDOW):
        r = client.post(
            "/api/copilot/chat/stream",
            json={"message": f"streamed message {i}"},
            headers=headers,
        )
        assert r.status_code == 200

    r = client.post(
        "/api/copilot/chat/stream",
        json={"message": "one too many"},
        headers=headers,
    )
    assert r.status_code == 429
