"""
SENTINEL — EC-03 Mule Withdrawal Simulator
============================================
Implements PRD requirement EC-03: if an investigator does NOT freeze a
suspect node within the Golden Window, the mule automatically withdraws
the funds — setting balance to 0, status to 'withdrawn', and dropping
the recoverable amount.

Usage (called from app/api/transactions.py):
    asyncio.create_task(
        schedule_withdrawal(case_id, suspect_node_id, store, manager,
                            delay_seconds=WITHDRAWAL_DELAY_SECONDS)
    )
"""

import asyncio
from datetime import datetime, timezone

from app.api.presenters import case_payload
from app.core.constants import AccountStatus
from app.engines.recovery_engine import recalculate


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def schedule_withdrawal(
    case_id: str,
    suspect_node_id: str,
    store: dict,
    manager,  # ConnectionManager — avoids circular import by typing as Any
    delay_seconds: int = 40,
    persist_fn=None,  # optional save_case callable injected from main.py
) -> None:
    """
    Wait for the Golden Window. If the suspect node is still not frozen
    by then, execute the mule withdrawal automatically.

    Args:
        case_id:         The fraud case this node belongs to.
        suspect_node_id: Account ID of the suspect mule node to watch.
        store:           The in-memory data_store dict.
        manager:         WebSocket ConnectionManager for live broadcast.
        delay_seconds:   Countdown before withdrawal fires (default: 40s).
        persist_fn:      Optional callable(case) for DB persistence.
    """
    await asyncio.sleep(delay_seconds)

    # ── Re-fetch live state after the delay ──────────────────────────────
    graph = store.get("graphs", {}).get(case_id, {})
    nodes = graph.get("nodes", [])

    target_node = None
    for node in nodes:
        nid = str(node.get("account_id") or node.get("id") or node.get("accountId", ""))
        if nid == str(suspect_node_id):
            target_node = node
            break

    if target_node is None:
        # Node removed or case cleaned up — nothing to do
        return

    current_status = target_node.get("status", AccountStatus.ACTIVE)

    # ── Guard: investigator already froze this node ───────────────────────
    if current_status in (AccountStatus.FROZEN, AccountStatus.WITHDRAWN):
        print(
            f"  [EC-03] Withdrawal ABORTED — node {suspect_node_id} "
            f"already {current_status} (investigator acted in time!)"
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

    print(
        f"  [EC-03] ⚠  Mule withdrawal executed! "
        f"Node={suspect_node_id}  Case={case_id}  "
        f"Lost=₹{prev_balance:,.2f}"
    )

    # Recalculate recovery with the node now zeroed
    case = store.get("cases", {}).get(case_id, {})
    if case:
        recovery = recalculate(case_id, store)

        # Append timeline event
        case.setdefault("timeline", []).append({
            "at":    _now_iso(),
            "event": f"mule_withdrawal: {suspect_node_id} drained ₹{prev_balance:,.2f}",
            "actor": "system_ec03",
        })

        # Persist updated case if a save function was provided
        if persist_fn:
            try:
                persist_fn(case)
            except Exception as _e:
                print(f"  [EC-03] Persistence error: {_e}")

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
