"""
WebSocket auth: browsers can't set custom headers on a WS handshake, so
the JWT travels as a ?token= query param instead (see
app/core/deps.py:get_ws_user). Regression coverage for Phase 4.
"""

from starlette.testclient import WebSocketDenialResponse, WebSocketDisconnect


def test_ws_connects_with_valid_token(client, viewer_token):
    with client.websocket_connect(f"/ws?token={viewer_token}") as ws:
        msg = ws.receive_json()
        assert msg["event"] == "connected"
        assert msg["status"] == "LIVE"


def test_ws_rejects_missing_token(client):
    try:
        with client.websocket_connect("/ws"):
            assert False, "connection should have been rejected"
    except (WebSocketDisconnect, WebSocketDenialResponse):
        pass


def test_ws_rejects_invalid_token(client):
    try:
        with client.websocket_connect("/ws?token=not-a-real-token"):
            assert False, "connection should have been rejected"
    except (WebSocketDisconnect, WebSocketDenialResponse):
        pass
