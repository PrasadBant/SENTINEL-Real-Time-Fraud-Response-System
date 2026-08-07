"""
AI Copilot Phase C: conversation history persistence
(app/services/copilot/history.py + GET/DELETE /api/copilot/history).
"""


def test_chat_returns_conversation_id_and_persists_messages(client, admin_headers):
    r1 = client.post(
        "/api/copilot/chat",
        json={"message": "hello there", "context_case_id": None},
        headers=admin_headers,
    )
    assert r1.status_code == 200
    conv_id = r1.json()["conversation_id"]
    assert conv_id

    r2 = client.get(f"/api/copilot/history?conversation_id={conv_id}", headers=admin_headers)
    assert r2.status_code == 200
    messages = r2.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello there"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"]


def test_conversation_id_continues_the_same_thread(client, admin_headers):
    r1 = client.post(
        "/api/copilot/chat",
        json={"message": "first message", "context_case_id": None},
        headers=admin_headers,
    )
    conv_id = r1.json()["conversation_id"]

    r2 = client.post(
        "/api/copilot/chat",
        json={"message": "second message", "context_case_id": None, "conversation_id": conv_id},
        headers=admin_headers,
    )
    assert r2.json()["conversation_id"] == conv_id

    history = client.get(f"/api/copilot/history?conversation_id={conv_id}", headers=admin_headers).json()
    assert len(history["messages"]) == 4  # 2 user + 2 assistant turns


def test_list_history_returns_caller_conversations_newest_first(client, admin_headers):
    r1 = client.post("/api/copilot/chat", json={"message": "conv one"}, headers=admin_headers)
    r2 = client.post("/api/copilot/chat", json={"message": "conv two"}, headers=admin_headers)
    conv1, conv2 = r1.json()["conversation_id"], r2.json()["conversation_id"]

    listing = client.get("/api/copilot/history", headers=admin_headers).json()["conversations"]
    ids = [c["conversation_id"] for c in listing]
    assert conv1 in ids
    assert conv2 in ids
    # newest (conv2) should sort before conv1
    assert ids.index(conv2) < ids.index(conv1)


def test_unknown_conversation_id_returns_404(client, admin_headers):
    r = client.get("/api/copilot/history?conversation_id=CONV-doesnotexist", headers=admin_headers)
    assert r.status_code == 404


def test_viewer_cannot_read_admins_conversation(client, admin_headers, viewer_headers):
    r1 = client.post(
        "/api/copilot/chat",
        json={"message": "admin's private thread"},
        headers=admin_headers,
    )
    conv_id = r1.json()["conversation_id"]

    r2 = client.get(f"/api/copilot/history?conversation_id={conv_id}", headers=viewer_headers)
    assert r2.status_code == 404  # not found, not leaked as "forbidden"


def test_viewer_cannot_delete_admins_conversation(client, admin_headers, viewer_headers):
    r1 = client.post(
        "/api/copilot/chat",
        json={"message": "admin's other thread"},
        headers=admin_headers,
    )
    conv_id = r1.json()["conversation_id"]

    r2 = client.delete(f"/api/copilot/history?conversation_id={conv_id}", headers=viewer_headers)
    assert r2.status_code == 404

    # still readable by its actual owner
    r3 = client.get(f"/api/copilot/history?conversation_id={conv_id}", headers=admin_headers)
    assert r3.status_code == 200


def test_delete_single_conversation(client, admin_headers):
    r1 = client.post("/api/copilot/chat", json={"message": "to be deleted"}, headers=admin_headers)
    conv_id = r1.json()["conversation_id"]

    r2 = client.delete(f"/api/copilot/history?conversation_id={conv_id}", headers=admin_headers)
    assert r2.status_code == 200
    assert r2.json()["deleted"] == 1

    r3 = client.get(f"/api/copilot/history?conversation_id={conv_id}", headers=admin_headers)
    assert r3.status_code == 404


def test_delete_all_clears_only_callers_history(client, admin_headers, viewer_headers):
    client.post("/api/copilot/chat", json={"message": "viewer thread"}, headers=viewer_headers)
    r_admin = client.post("/api/copilot/chat", json={"message": "admin thread"}, headers=admin_headers)
    admin_conv_id = r_admin.json()["conversation_id"]

    r = client.delete("/api/copilot/history", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["deleted"] >= 1

    # admin's conversations are gone
    listing = client.get("/api/copilot/history", headers=admin_headers).json()["conversations"]
    assert admin_conv_id not in [c["conversation_id"] for c in listing]

    # viewer's history is untouched
    viewer_listing = client.get("/api/copilot/history", headers=viewer_headers).json()["conversations"]
    assert len(viewer_listing) >= 1


def test_history_requires_auth(client):
    r = client.get("/api/copilot/history")
    assert r.status_code == 401
    r = client.delete("/api/copilot/history")
    assert r.status_code == 401
