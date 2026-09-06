"""
SENTINEL — Investigative Action Routes
=========================================
POST /action/{freeze,flag,alert,monitor,close,close_fp}: operator-triggered
actions against a case (or a specific account within it). `handle_action`
is also reused by the AI copilot (app/api/copilot.py) for its "freeze this
case" / "close this case" intents.
"""

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends

from app.api.presenters import case_payload, now_iso
from app.api.schemas import ActionRequest
from app.core.constants import AccountStatus, ActionStatus, ActionTypes, CaseStatus
from app.core.data_store import data_store
from app.core.deps import require_role
from app.core.repository import repository
from app.services import withdrawal_queue
from app.services.mock_apis import (
    mock_bank_freeze,
    mock_close_case,
    mock_monitor_account,
    mock_police_alert,
    mock_telecom_flag,
)
from app.websocket.connection_manager import manager

logger = logging.getLogger("sentinel.actions")

router = APIRouter()


def _get_or_hydrate_case(case_id: str) -> dict | None:
    """Look up a case locally first; if missing, fall back to Postgres
    (the durable source of truth) and cache the hit into data_store so
    later lookups in this process are local. Hostile-review fix: without
    this, an investigator's freeze/close/monitor action against a case
    another API replica created would 404 with "case_not_found" even
    though the case genuinely exists — which replica happens to serve a
    given request is an accident of load balancing, not something an
    investigator should have to know or care about.

    Note the limit of what this fixes: it restores case-level status/
    actions-taken consistency across replicas. It does NOT make a freeze's
    node-level effect (data_store["graphs"][case_id]["nodes"]) visible to
    other replicas — graph state isn't persisted or Redis-shared at all
    today (a pre-existing, documented gap; real graph persistence is
    Phase 5's job). A freeze against a case hydrated from Postgres this
    way will correctly update the case's status and audit trail, but may
    freeze zero nodes if this replica never built that case's graph."""
    case = data_store.get("cases", {}).get(case_id)
    if case is not None:
        return case
    try:
        case = repository.get_case(case_id)
    except Exception as e:
        logger.warning("Postgres case lookup degraded for %s: %s", case_id, e)
        return None
    if case is not None:
        data_store.setdefault("cases", {})[case_id] = case
    return case


def _record_action(case_id: str, action_type: str, target_id: str, status: str, reason: str | None = None) -> dict[str, Any]:
    case = _get_or_hydrate_case(case_id)
    if not case:
        return {}
    entry = {
        "action_id": f"ACT-{uuid4().hex[:10].upper()}",
        "case_id": case_id,
        "action_type": action_type,
        "target_id": target_id,
        "target": target_id,
        "status": ActionStatus.ACK if status == "SUCCESS" else ActionStatus.NACK,
        "timestamp": now_iso(),
        "reason": reason or "Operator decision",
        "latency": 0,
    }
    case.setdefault("actions_taken", []).insert(0, entry)

    # Persist the action (note: _record_action is sync, called from async context
    # via run_in_executor at the call site for heavy traffic; here we keep inline for
    # simplicity since action writes are rare compared to TX ingestion)
    try:
        repository.save_action(entry)
    except Exception as _pe:
        logger.warning("Action write error: %s", _pe)

    # Status Mapping based on actions
    if entry["status"] == ActionStatus.ACK:
        if action_type in [ActionTypes.FREEZE, ActionTypes.FLAG, ActionTypes.ALERT]:
            case["status"] = CaseStatus.ACTIONED
        elif action_type == ActionTypes.MONITOR:
            case["status"] = CaseStatus.MONITORING
        elif action_type == ActionTypes.CLOSE:
            case["status"] = CaseStatus.CLOSED
        elif action_type == ActionTypes.CLOSE_FP:
            case["status"] = CaseStatus.CLOSED_FP

    # Persist the case's updated status/actions_taken to Postgres. This
    # was a pre-existing gap, exposed rather than introduced by the
    # hostile-review fix: GET /cases (app/api/cases.py) now reads from
    # Postgres for cross-replica correctness, and its action log
    # (app/api/presenters.py's normalize_action_log) reads
    # case["actions_taken"] from the CASE payload, not a separate query —
    # so a status change or a new action-log entry that only ever lived
    # in this process's local data_store dict would otherwise appear to
    # silently revert/disappear once viewed through the Postgres-backed
    # endpoint. save_action() above only persists the audit-log row in
    # its own table; this call is what makes the case's own view of its
    # status and action history durable and visible everywhere, not just
    # in the process that happened to handle this specific action.
    try:
        repository.save_case(case)
    except Exception as _pe:
        logger.warning("Case write error: %s", _pe)

    return entry


async def handle_action(action_name: str, payload: ActionRequest) -> dict[str, Any]:
    case = _get_or_hydrate_case(payload.case_id)
    target_id = payload.account_id or payload.target_id or "GLOBAL"
    if not case:
        return {
            "ok": False,
            "event": "action_taken",
            "case_id": payload.case_id,
            "action": action_name,
            "target_id": target_id,
            "status": ActionStatus.NACK,
            "error": "case_not_found",
        }

    if action_name == "freeze":
        api_response = mock_bank_freeze(target_id, case.get("recoverable_amount", 0.0))
        graph = data_store.get("graphs", {}).get(payload.case_id, {})
        edges = graph.get("edges", [])

        def get_downstream(start_id):
            downstream = {start_id}
            queue = [start_id]
            while queue:
                curr = queue.pop(0)
                for edge in edges:
                    src = str(edge.get("source") or edge.get("from"))
                    tgt = str(edge.get("target") or edge.get("to"))
                    if src == curr and tgt not in downstream:
                        downstream.add(tgt)
                        queue.append(tgt)
            return downstream

        if target_id == "GLOBAL" or target_id == "SUSPECTS":
            to_freeze = {str(edge.get("target") or edge.get("to")) for edge in edges}
        else:
            to_freeze = get_downstream(str(target_id))

        for node in graph.get("nodes", []):
            acc_id = str(node.get("account_id") or node.get("id") or node.get("accountId"))
            if acc_id in to_freeze:
                node["status"] = AccountStatus.FROZEN
                # EC-03: cancel any pending withdrawal timer for this now-frozen node
                _key = f"{payload.case_id}:{acc_id}"
                if await withdrawal_queue.cancel(_key):
                    logger.info("Withdrawal task cancelled for frozen node %s", acc_id)
    elif action_name == "flag":
        api_response = mock_telecom_flag(target_id)
    elif action_name == "monitor":
        api_response = mock_monitor_account(target_id)
    elif action_name == "close":
        api_response = mock_close_case(payload.case_id, "RESOLVED")
    elif action_name == "close_fp":
        api_response = mock_close_case(payload.case_id, "FALSE_POSITIVE")
    else:
        api_response = mock_police_alert(payload.case_id, {"reason": payload.reason or "Escalation requested"})

    status = api_response.get("status", "FAILED")
    action_entry = _record_action(payload.case_id, action_name.upper(), target_id, status, payload.reason)
    response = {
        "ok": status == "SUCCESS",
        "event": "action_taken",
        "case_id": payload.case_id,
        "action": action_name,
        "target_id": target_id,
        "status": action_entry.get("status", ActionStatus.NACK),
        "action_id": action_entry.get("action_id"),
        "timestamp": action_entry.get("timestamp", now_iso()),
    }

    await manager.broadcast(response)
    await manager.broadcast({"event": "case_updated", **case_payload(case)})
    return response


# All investigative actions are admin-only, matching the frontend's existing
# role gate (ActionButton/ActionPanel disable these for viewers) — now
# actually enforced server-side instead of only cosmetically in the UI.
_require_admin = require_role("admin")


@router.post("/action/freeze")
async def freeze_action(payload: ActionRequest, user: dict = Depends(_require_admin)) -> dict[str, Any]:
    return await handle_action("freeze", payload)


@router.post("/action/flag")
async def flag_action(payload: ActionRequest, user: dict = Depends(_require_admin)) -> dict[str, Any]:
    return await handle_action("flag", payload)


@router.post("/action/alert")
async def alert_action(payload: ActionRequest, user: dict = Depends(_require_admin)) -> dict[str, Any]:
    return await handle_action("alert", payload)


@router.post("/action/monitor")
async def monitor_action(payload: ActionRequest, user: dict = Depends(_require_admin)) -> dict[str, Any]:
    return await handle_action("monitor", payload)


@router.post("/action/close")
async def close_action(payload: ActionRequest, user: dict = Depends(_require_admin)) -> dict[str, Any]:
    return await handle_action("close", payload)


@router.post("/action/close_fp")
async def close_fp_action(payload: ActionRequest, user: dict = Depends(_require_admin)) -> dict[str, Any]:
    return await handle_action("close_fp", payload)
