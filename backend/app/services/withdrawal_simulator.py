"""
SENTINEL — EC-03 Mule Withdrawal Scenario Timer
===================================================
Implements PRD requirement EC-03: if an investigator does NOT freeze a
suspect node within the Golden Window, the mule automatically withdraws
the funds — setting balance to 0, status to 'withdrawn', and dropping
the recoverable amount.

This is a simulated SLA countdown, not a fraud-detection signal: it
doesn't observe or infer anything about real mule behavior, it just
enforces a fixed deadline the platform itself defines (WITHDRAWAL_DELAY_
SECONDS). Calling it "detection" anywhere would overstate what it does —
worth being explicit about, since the demo/scenario framing (a simulated
attacker draining funds on a clock) can otherwise read as more than it
is.

Runs as an Arq job (see app/services/withdrawal_queue.py for scheduling/
cancellation) embedded in the same process as the API — not a separate
worker container. That matters for this specific function: its fire-time
re-fetch below reads app.core.data_store["graphs"], which isn't
persisted or Redis-shared today (a pre-existing gap — see
app/core/repository.py's load_all() docstring; real graph persistence is
Phase 5's job). A genuinely separate worker process would have no way to
see that state at all, which would make the fire-time guard below always
miss — i.e. always execute the withdrawal even if the node was frozen in
time. Embedding sidesteps that; the job function is otherwise unchanged
from the pre-Arq schedule_withdrawal it replaces.

Residual gap once the API is actually scaled to multiple replicas (the
docker-compose api container_name fix makes this newly possible): each
replica embeds its OWN worker, and Arq's atomic dequeue means ANY
replica's worker may end up firing a job another replica originally
scheduled. "Embedded in the same process as the API" only guarantees
"the same process that's *running* this job", not "the same process
that scheduled it" — so the fire-time guard below can still miss (return
a no-op, or in the worst case execute a withdrawal a different replica's
graph would have shown as frozen) if the job is picked up by a replica
that never built this case's graph. This is the same fundamental
graph-not-shared limitation as the single-instance case, just newly
reachable across replicas instead of only across a restart — closing it
for real means either sharing graph/node state (Phase 5) or routing a
job back to its originating replica specifically, both explicitly out of
scope for this fix pass.
"""

import logging
from datetime import datetime, timezone

from app.api.presenters import case_payload
from app.core.constants import AccountStatus
from app.core.data_store import data_store
from app.core.logging_config import CORRELATION_ID
from app.core.metrics import EC03_JOBS_FIRED_TOTAL
from app.core.repository import repository
from app.engines.recovery_engine import recalculate
from app.websocket.connection_manager import manager

logger = logging.getLogger("sentinel.ec03")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def run_withdrawal_job(ctx, case_id: str, suspect_node_id: str, correlation_id: str) -> None:
    """
    Arq job body (see app/services/withdrawal_queue.schedule) — fires
    after the Golden Window delay Arq's own `_defer_by` enforces. If the
    suspect node is still not frozen by then, executes the mule
    withdrawal.

    Args:
        ctx:             Arq's own per-job context dict — not app state.
        case_id:         The fraud case this node belongs to.
        suspect_node_id: Account ID of the suspect mule node to watch.
        correlation_id:  Threaded through every log line this job emits —
                          set explicitly here (not inherited automatically)
                          since a contextvar can't cross the boundary from
                          the original request into a Redis-persisted job
                          consumed by a later worker-loop iteration.
    """
    CORRELATION_ID.set(correlation_id)

    # ── Re-fetch live state now ────────────────────────────────────────
    graph = data_store.get("graphs", {}).get(case_id, {})
    nodes = graph.get("nodes", [])

    target_node = None
    for node in nodes:
        nid = str(node.get("account_id") or node.get("id") or node.get("accountId", ""))
        if nid == str(suspect_node_id):
            target_node = node
            break

    if target_node is None:
        # Node/case not visible in this process's data_store — either it
        # was genuinely cleaned up, or (see module docstring) the process
        # restarted since this job was scheduled and graph state doesn't
        # survive that. Either way, nothing safe to act on; no-op.
        logger.info("Withdrawal job fired for %s but node/graph not found — no-op", suspect_node_id)
        return

    current_status = target_node.get("status", AccountStatus.ACTIVE)

    # ── Guard: investigator already froze this node ───────────────────────
    if current_status in (AccountStatus.FROZEN, AccountStatus.WITHDRAWN):
        logger.info(
            "Withdrawal ABORTED — node %s already %s (investigator acted in time!)",
            suspect_node_id, current_status,
        )
        await manager.broadcast({
            "event": "withdrawal_prevented",
            "case_id": case_id,
            "suspect_node_id": suspect_node_id,
            "message": (
                f"✅ Golden Window saved! Mule withdrawal on {suspect_node_id} "
                f"was prevented — node was already {current_status}."
            ),
            "timestamp": _now_iso(),
        })
        return

    # ── Execute the withdrawal ────────────────────────────────────────────
    prev_balance = float(target_node.get("balance", 0.0))
    target_node["status"]  = AccountStatus.WITHDRAWN
    target_node["balance"] = 0.0
    EC03_JOBS_FIRED_TOTAL.inc()

    logger.warning(
        "Mule withdrawal executed! Node=%s Case=%s Lost=₹%s",
        suspect_node_id, case_id, f"{prev_balance:,.2f}",
    )

    # Recalculate recovery with the node now zeroed
    case = data_store.get("cases", {}).get(case_id, {})
    if case:
        recovery = recalculate(case_id, data_store)

        # Append timeline event
        case.setdefault("timeline", []).append({
            "at":    _now_iso(),
            "event": f"mule_withdrawal: {suspect_node_id} drained ₹{prev_balance:,.2f}",
            "actor": "system_ec03",
        })

        # Persist updated case. Exceptions here are deliberately swallowed,
        # not re-raised: letting this propagate would trigger Arq's retry
        # machinery and could re-broadcast an already-completed withdrawal
        # on retry. Only genuine infra failures (e.g. Redis unreachable,
        # which would surface earlier via withdrawal_queue) should be
        # retryable — a Postgres write failure here shouldn't be.
        try:
            repository.save_case(case)
        except Exception as _e:
            logger.error("Persistence error: %s", _e)

        # Broadcast withdrawal event to all connected dashboards
        await manager.broadcast({
            "event":            "withdrawal_event",
            "case_id":          case_id,
            "suspect_node_id":  suspect_node_id,
            "amount_lost":      prev_balance,
            "new_recovery_pct": recovery.get("recovery_pct", 0.0),
            "message": (
                f"⚠ Mule withdrawal executed on {suspect_node_id}! "
                f"₹{prev_balance:,.2f} drained — recovery window closed."
            ),
            "timestamp": _now_iso(),
        })

        # Also push a case_updated event so the UI graph refreshes
        try:
            await manager.broadcast({"event": "case_updated", **case_payload(case)})
        except Exception:
            pass  # non-critical — next TX will refresh anyway
