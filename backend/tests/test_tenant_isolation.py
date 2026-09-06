"""
Phase 2 (Security & Observability) — object-level authorization: an
authenticated investigator must only ever see or act on their own
tenant's cases/transactions, never another tenant's, even though today's
transaction ingestion is single-tenant (see app/api/cases.py's module
docstring for that scope boundary). Seeds two tenants' worth of data
directly via the repository (bypassing the single-tenant ingestion
pipeline entirely — this is the read/action authorization layer under
test, not ingestion), matching tests/test_multi_replica_consistency.py's
existing direct-repository seeding pattern.
"""

from app.core.repository import repository
from app.core.security import hash_password


def _seed_tenant(tenant_id: str, case_id: str, username: str, role: str = "admin") -> None:
    repository.create_user(username, hash_password("test-password-123"), role, tenant_id=tenant_id)
    repository.save_case(
        {
            "case_id": case_id, "status": "HIGH_RISK", "origin_account": f"ACC-{tenant_id}",
            "chain": [f"ACC-{tenant_id}"], "max_nodes": 5, "total_fraud_amount": 1000.0,
            "recoverable_amount": 1000.0, "recovery_pct": 100.0, "golden_window_minutes": 20,
            "actions_taken": [], "timeline": [],
        },
        tenant_id=tenant_id,
    )


def _login(client, username: str) -> dict:
    r = client.post("/auth/login", json={"username": username, "password": "test-password-123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_get_cases_never_leaks_another_tenants_case(client):
    _seed_tenant("tenant-a", "CASE-TENANT-A-001", "investigator-a")
    _seed_tenant("tenant-b", "CASE-TENANT-B-001", "investigator-b")

    headers_a = _login(client, "investigator-a")
    headers_b = _login(client, "investigator-b")

    cases_a = {c["case_id"] for c in client.get("/cases", headers=headers_a).json()}
    cases_b = {c["case_id"] for c in client.get("/cases", headers=headers_b).json()}

    assert "CASE-TENANT-A-001" in cases_a
    assert "CASE-TENANT-B-001" not in cases_a, "tenant A must never see tenant B's case"

    assert "CASE-TENANT-B-001" in cases_b
    assert "CASE-TENANT-A-001" not in cases_b, "tenant B must never see tenant A's case"


def test_freeze_across_tenant_boundary_is_rejected_as_not_found(client):
    """The actual IDOR fix: an admin from tenant A must not be able to
    freeze tenant B's case just by supplying its case_id — not a 403
    (which would confirm the case exists), a plain case_not_found, same
    as a genuinely nonexistent case_id would produce."""
    _seed_tenant("tenant-c", "CASE-TENANT-C-001", "investigator-c")
    _seed_tenant("tenant-d", "CASE-TENANT-D-001", "investigator-d")

    headers_c = _login(client, "investigator-c")

    r = client.post("/action/freeze", json={"case_id": "CASE-TENANT-D-001", "account_id": "GLOBAL"}, headers=headers_c)
    assert r.status_code == 200  # handle_action returns 200 with an error field, not an HTTP error
    body = r.json()
    assert body["ok"] is False
    assert body["error"] == "case_not_found"

    # Sanity: the same admin CAN freeze their own tenant's case.
    r2 = client.post("/action/freeze", json={"case_id": "CASE-TENANT-C-001", "account_id": "GLOBAL"}, headers=headers_c)
    assert r2.json()["ok"] is True


def test_local_cache_hit_does_not_bypass_tenant_check(client):
    """Regression for the subtler variant of the IDOR: a case already
    sitting in this process's local data_store cache (e.g. this replica
    personally handled its ingestion) must still be tenant-checked before
    being handed back — not just the Postgres fallback path. See
    app/api/actions.py::_get_or_hydrate_case's docstring."""
    from app.core.data_store import data_store

    _seed_tenant("tenant-e", "CASE-TENANT-E-001", "investigator-e")
    _seed_tenant("tenant-f", "CASE-TENANT-F-001", "investigator-f")

    # Force a local-cache hit for tenant E's case, simulating "this
    # replica already has it in memory" rather than relying on the
    # Postgres fallback. Fully-shaped (not a partial dict): data_store is
    # the SAME process-global singleton every other test's run_pipeline()
    # scans (orchestrator.py's _find_matching_case unconditionally reads
    # c["origin_account"]/c["chain"] on every case in the store) — a
    # malformed case here would crash unrelated tests running afterward
    # in the same session, same defensive reasoning
    # tests/test_redis_integration.py's test_schedule_fire_and_cancel
    # already documents. Cleaned up in `finally` for the same reason.
    case_id = "CASE-TENANT-E-001"
    data_store.setdefault("cases", {})[case_id] = {
        "case_id": case_id, "tenant_id": "tenant-e", "status": "HIGH_RISK",
        "origin_account": "ACC-tenant-e", "chain": ["ACC-tenant-e"], "max_nodes": 5,
        "total_fraud_amount": 1000.0, "recoverable_amount": 1000.0, "recovery_pct": 100.0,
        "golden_window_minutes": 20, "actions_taken": [], "timeline": [],
    }
    try:
        headers_f = _login(client, "investigator-f")
        r = client.post("/action/freeze", json={"case_id": case_id, "account_id": "GLOBAL"}, headers=headers_f)
        assert r.json()["error"] == "case_not_found", "a local-cache hit must still enforce tenant_id"
    finally:
        data_store["cases"].pop(case_id, None)
