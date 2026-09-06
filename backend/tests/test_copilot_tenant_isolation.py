"""
Phase 2 hostile-review fixes — Copilot subsystem.

CRITICAL (BOLA): every Copilot read path (structured intents in
app/services/copilot/intents.py, the RAG context builder in
app/services/copilot/context_builder.py, and the offline-fallback reply
in app/api/copilot.py) used to read app.core.data_store directly and
completely unscoped by tenant — live-verified during the hostile review
that a VIEWER (no admin rights at all) in one tenant could get the
copilot to dump another tenant's case/transaction details via "explain
case <id>", "show high-risk cases", "explain transaction <id>", "show
transactions over X", "highest risk sender", and even a bare freeform
question with no case selected (which folds every tenant's top cases
into "general" context). Every one of those exact exploits is
reproduced here, now proving each is blocked.

HIGH (false success): the copilot's freeze/close chat intents used to
discard handle_action()'s return value and always report the action as
successful — reproduced here via a cross-tenant freeze attempt through
chat, now proving the reply reflects the actual (failed) outcome.
"""

from app.core.repository import repository
from app.core.security import hash_password


def _seed_tenant(tenant_id: str, case_id: str, tx_id: str, username: str, role: str = "admin") -> str:
    """Mirrors the hostile review's exact repro: seeds a case + transaction
    for one tenant directly via the repository, plus a user in that
    tenant, and returns a bearer header value for that user. Also stamps
    data_store directly (matching what real ingestion does) so the
    copilot's data_store-backed reads have something to find — the
    Postgres-only tenant isolation (GET /cases) is covered by
    test_tenant_isolation.py; this file is specifically about the
    copilot's own (separate, data_store-backed) read path."""
    from app.core.data_store import data_store

    repository.create_user(username, hash_password("pw12345"), role, tenant_id=tenant_id)

    case = {
        "case_id": case_id, "tenant_id": tenant_id, "status": "HIGH_RISK",
        "origin_account": f"ACC-{tenant_id}-ORIGIN", "chain": [f"ACC-{tenant_id}-ORIGIN", f"ACC-{tenant_id}-MULE"],
        "max_nodes": 5, "total_fraud_amount": 9999999.0, "recoverable_amount": 9999999.0,
        "recovery_pct": 100.0, "golden_window_minutes": 20, "actions_taken": [], "timeline": [],
        "urgency_score": 99.9, "risk_level": 95, "transactions": [tx_id],
    }
    tx = {
        "tx_id": tx_id, "tenant_id": tenant_id, "sender_account": f"ACC-{tenant_id}-ORIGIN",
        "receiver_account": f"ACC-{tenant_id}-MULE", "amount": 9999999.0,
        "timestamp": "2026-01-01T00:00:00Z", "channel": "IMPS", "risk_score": 95,
        "case_id": case_id, "risk_factors": [],
    }
    data_store.setdefault("cases", {})[case_id] = case
    data_store.setdefault("transactions", {})[tx_id] = tx
    repository.save_case(case, tenant_id=tenant_id)
    repository.save_transaction(tx, tenant_id=tenant_id)
    return case_id, tx_id


def _login(client, username: str) -> dict:
    r = client.post("/auth/login", json={"username": username, "password": "pw12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _chat(client, headers, message, context_case_id=None):
    body = {"message": message}
    if context_case_id:
        body["context_case_id"] = context_case_id
    r = client.post("/api/copilot/chat", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["reply"]


def test_copilot_explain_case_never_leaks_another_tenant(client):
    """Exact hostile-review exploit: 'explain case CASE-SECRETVIC'."""
    victim_case, _ = _seed_tenant("copilot-tenant-victim-1", "CASE-COPILOTV1", "TX-COPILOTV1", "copilot-victim-1")
    repository.create_user("attacker-viewer-1", hash_password("pw12345"), "viewer", tenant_id="copilot-tenant-attacker-1")
    attacker_headers = _login(client, "attacker-viewer-1")

    reply = _chat(client, attacker_headers, f"explain case {victim_case}")
    assert "No case found" in reply, f"LEAK: attacker (wrong tenant, viewer role) got case details: {reply}"
    assert "9,999,999" not in reply
    assert "ORIGIN" not in reply


def test_copilot_list_high_risk_cases_never_leaks_another_tenant(client):
    """Exact hostile-review exploit: 'show me all high-risk cases'."""
    victim_case, _ = _seed_tenant("copilot-tenant-victim-2", "CASE-COPILOTV2", "TX-COPILOTV2", "copilot-victim-2")
    repository.create_user("attacker-viewer-2", hash_password("pw12345"), "viewer", tenant_id="copilot-tenant-attacker-2")
    attacker_headers = _login(client, "attacker-viewer-2")

    reply = _chat(client, attacker_headers, "show me all high-risk cases")
    assert victim_case not in reply, f"LEAK: attacker saw victim's case in high-risk list: {reply}"


def test_copilot_explain_transaction_never_leaks_another_tenant(client):
    """Exact hostile-review exploit: 'explain transaction TX-SECRETVIC01'."""
    _, victim_tx = _seed_tenant("copilot-tenant-victim-3", "CASE-COPILOTV3", "TX-COPILOTV3", "copilot-victim-3")
    repository.create_user("attacker-viewer-3", hash_password("pw12345"), "viewer", tenant_id="copilot-tenant-attacker-3")
    attacker_headers = _login(client, "attacker-viewer-3")

    reply = _chat(client, attacker_headers, f"explain transaction {victim_tx}")
    assert "No transaction found" in reply, f"LEAK: attacker got victim's transaction details: {reply}"
    assert "9,999,999" not in reply


def test_copilot_search_transactions_never_leaks_another_tenant(client):
    """Exact hostile-review exploit: 'show transactions over 1000'."""
    _, victim_tx = _seed_tenant("copilot-tenant-victim-4", "CASE-COPILOTV4", "TX-COPILOTV4", "copilot-victim-4")
    repository.create_user("attacker-viewer-4", hash_password("pw12345"), "viewer", tenant_id="copilot-tenant-attacker-4")
    attacker_headers = _login(client, "attacker-viewer-4")

    reply = _chat(client, attacker_headers, "show transactions over 1000")
    assert victim_tx not in reply, f"LEAK: attacker's transaction search returned victim's tx: {reply}"


def test_copilot_dashboard_stats_never_include_another_tenant(client):
    """Exact hostile-review exploit: 'what is the total fraud exposure'."""
    _seed_tenant("copilot-tenant-victim-5", "CASE-COPILOTV5", "TX-COPILOTV5", "copilot-victim-5")
    repository.create_user("attacker-viewer-5", hash_password("pw12345"), "viewer", tenant_id="copilot-tenant-attacker-5")
    attacker_headers = _login(client, "attacker-viewer-5")

    reply = _chat(client, attacker_headers, "what is the total fraud exposure right now")
    assert "9,999,999" not in reply, f"LEAK: attacker's dashboard stats include victim's fraud amount: {reply}"
    assert "Total Cases:** 0" in reply or "**Total Cases:** 0" in reply


def test_copilot_highest_risk_sender_never_leaks_another_tenant(client):
    """Additional read path found during the audit (not called out in the
    original review): 'highest risk sender'."""
    _seed_tenant("copilot-tenant-victim-6", "CASE-COPILOTV6", "TX-COPILOTV6", "copilot-victim-6")
    repository.create_user("attacker-viewer-6", hash_password("pw12345"), "viewer", tenant_id="copilot-tenant-attacker-6")
    attacker_headers = _login(client, "attacker-viewer-6")

    reply = _chat(client, attacker_headers, "who is the highest risk sender")
    assert "copilot-tenant-victim-6" not in reply
    assert "No transactions recorded yet." in reply


def test_copilot_recommend_next_never_leaks_another_tenant(client):
    """Additional read path found during the audit: 'what should I
    investigate next'."""
    _seed_tenant("copilot-tenant-victim-7", "CASE-COPILOTV7", "TX-COPILOTV7", "copilot-victim-7")
    repository.create_user("attacker-viewer-7", hash_password("pw12345"), "viewer", tenant_id="copilot-tenant-attacker-7")
    attacker_headers = _login(client, "attacker-viewer-7")

    reply = _chat(client, attacker_headers, "what should I investigate next")
    assert "CASE-COPILOTV7" not in reply
    assert "clear" in reply.lower() or "No active cases" in reply


def test_copilot_freeform_general_context_never_leaks_another_tenant(client):
    """The subtlest of the original leaks: NO case selected, freeform
    message with no matching structured intent — general_context() used
    to fold every tenant's top-5 high-risk cases into the LLM's context
    unconditionally. Uses the mock/offline provider (no live API key in
    tests), which still renders context_data verbatim into its reply for
    an unrecognized freeform message... actually the offline fallback has
    its own canned replies; the real assertion here is at the
    context_builder level, which is what actually feeds the LLM."""
    from app.services.copilot.context_builder import general_context

    _seed_tenant("copilot-tenant-victim-8", "CASE-COPILOTV8", "TX-COPILOTV8", "copilot-victim-8")

    ctx = general_context("copilot-tenant-attacker-8")
    assert "CASE-COPILOTV8" not in ctx
    assert "9,999,999" not in ctx
    assert "No cases exist yet" in ctx


def test_copilot_offline_fallback_never_leaks_another_tenant_case(client):
    """The offline-fallback reply (app/api/copilot.py::_offline_fallback_reply)
    found during the audit, not called out in the original review — reads
    data_store directly given a user-supplied context_case_id.

    Direct unit call, not through /api/copilot/chat: MockProvider (the
    default provider active in tests) never actually fails — for any
    message it doesn't specially recognize, it echoes build_for_request()'s
    context straight back (itself already covered by the case_context/
    general_context tests above), so _offline_fallback_reply is only ever
    reached in production when a real configured provider genuinely fails
    (bad key, network error, timeout). Calling it directly is the only way
    to actually exercise this specific function's own tenant scoping."""
    from app.api.copilot import _offline_fallback_reply

    victim_case, _ = _seed_tenant("copilot-tenant-victim-9", "CASE-COPILOTV9", "TX-COPILOTV9", "copilot-victim-9")

    reply = _offline_fallback_reply(victim_case, "hello", "copilot-tenant-attacker-9")
    assert "9,999,999" not in reply
    assert "ORIGIN" not in reply
    # Falls through to the generic "no case" branches, exactly as if
    # context_case_id had been None / genuinely nonexistent.
    assert "UNKNOWN" in reply or "offline mode" in reply.lower() or "Sentinel" in reply

    # Sanity: the SAME case_id from its OWN tenant must still work.
    own_reply = _offline_fallback_reply(victim_case, "hello", "copilot-tenant-victim-9")
    assert "9,999,999" in own_reply or "high-risk" in own_reply.lower() or "moderate risk" in own_reply.lower()


def test_copilot_freeze_reports_actual_failure_not_false_success(client):
    """HIGH: the copilot's freeze intent used to report 'Action Executed'
    even when handle_action() failed (e.g. a cross-tenant case_id) —
    live-verified during the hostile review with a genuine admin whose
    freeze silently no-opped while being told it succeeded. Reproduces
    that exact scenario: an admin from tenant A asks the copilot to
    freeze tenant B's case."""
    victim_case, _ = _seed_tenant("copilot-tenant-victim-10", "CASE-COPILOTV10", "TX-COPILOTV10", "copilot-victim-10")
    repository.create_user("attacker-admin-10", hash_password("pw12345"), "admin", tenant_id="copilot-tenant-attacker-10")
    attacker_headers = _login(client, "attacker-admin-10")

    reply = _chat(client, attacker_headers, "freeze this case", context_case_id=victim_case)
    assert "Action Executed" not in reply, f"FALSE SUCCESS: copilot claimed it froze a case it couldn't touch: {reply}"
    assert "Action Failed" in reply or "could not freeze" in reply.lower()


def test_copilot_freeze_still_reports_real_success_for_own_tenant(client):
    """Sanity check: the false-success fix must not turn a genuinely
    successful same-tenant freeze into a false failure either."""
    own_case, _ = _seed_tenant("copilot-tenant-own-11", "CASE-COPILOTV11", "TX-COPILOTV11", "copilot-own-admin-11")
    own_headers = _login(client, "copilot-own-admin-11")

    reply = _chat(client, own_headers, "freeze this case", context_case_id=own_case)
    assert "Action Executed" in reply, f"a genuinely successful freeze must still report success: {reply}"
