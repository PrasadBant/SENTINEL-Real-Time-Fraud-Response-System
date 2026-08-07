"""
Auth: login, token validation, role gating, and the simulator's API-key
gate on /transaction. Regression coverage for Phase 4 (see git history).
"""

from conftest import TX_HEADERS, make_tx


def test_login_admin_success(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "admin"
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_viewer_success(client):
    r = client.post("/auth/login", json={"username": "viewer", "password": "viewer123"})
    assert r.status_code == 200
    assert r.json()["role"] == "viewer"


def test_login_bad_password_rejected(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user_rejected(client):
    r = client.post("/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


def test_auth_me_returns_role(client, admin_headers):
    r = client.get("/auth/me", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == {"username": "admin", "role": "admin"}


def test_protected_route_requires_token(client):
    r = client.get("/cases")
    assert r.status_code == 401


def test_protected_route_rejects_malformed_token(client):
    r = client.get("/cases", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_any_role_can_read_cases(client, admin_headers, viewer_headers):
    assert client.get("/cases", headers=admin_headers).status_code == 200
    assert client.get("/cases", headers=viewer_headers).status_code == 200


def test_viewer_cannot_freeze(client, viewer_headers):
    r = client.post("/action/freeze", json={"case_id": "ANY"}, headers=viewer_headers)
    assert r.status_code == 403


def test_viewer_cannot_trigger_attack_mode(client, viewer_headers):
    r = client.post("/attack-mode", headers=viewer_headers)
    assert r.status_code == 403


def test_admin_can_trigger_attack_mode(client, admin_headers):
    r = client.post("/attack-mode", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_transaction_requires_api_key(client):
    r = client.post("/transaction", json=make_tx())
    assert r.status_code == 401


def test_transaction_rejects_wrong_api_key(client):
    r = client.post("/transaction", json=make_tx(), headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401


def test_transaction_accepts_correct_api_key(client):
    r = client.post("/transaction", json=make_tx(), headers=TX_HEADERS)
    assert r.status_code == 200
