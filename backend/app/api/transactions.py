"""
SENTINEL — Transaction Ingestion Route
=========================================
POST /transaction: runs the scoring pipeline, broadcasts the result, and
(for cases that just escalated to HIGH_RISK) starts the EC-03 mule
withdrawal countdown for each newly-linked suspect node.
"""

import asyncio
from typing import Any

from fastapi import APIRouter

from app.api.presenters import build_tx_event, case_payload
from app.core.constants import AccountStatus, CaseStatus
from app.core.config import WITHDRAWAL_DELAY_SECONDS
from app.core.data_store import data_store
from app.core.models.transaction import Transaction
from app.core.persistence import save_case, save_transaction
from app.services import withdrawal_tracker
from app.services.orchestrator import run_pipeline
from app.services.withdrawal_simulator import schedule_withdrawal
from app.websocket.connection_manager import manager

router = APIRouter()


@router.post("/transaction")
async def process_tx(tx_in: Transaction) -> dict[str, Any]:
    # FastAPI validates the body against Transaction before this runs — bad
    # payloads (missing tx_id/amount, non-positive amount, wrong types) are
    # rejected with a 422 automatically, instead of reaching the pipeline
    # and failing deep inside with an opaque error.
    tx = tx_in.model_dump(mode="json", exclude_none=True)
    result = run_pipeline(tx, data_store)

    transaction = result.get("transaction") or {}
    tx_event = build_tx_event(transaction, default_channel="UPI")
    await manager.broadcast(tx_event)

    case = result.get("case")
    if case:
        case_event = {"event": "case_updated", **case_payload(case)}
        await manager.broadcast(case_event)

        # ── Persist to SQLite (thread-pool, non-blocking) ───────────────
        try:
            _loop = asyncio.get_event_loop()
            await _loop.run_in_executor(None, save_transaction, transaction)
            await _loop.run_in_executor(None, save_case, case)
        except Exception as _pe:
            print(f"  [Persistence] Write error: {_pe}")

        # ── EC-03: Schedule mule withdrawal for new HIGH_RISK cases ──────
        if case.get("status") == CaseStatus.HIGH_RISK:
            graph = data_store.get("graphs", {}).get(case.get("case_id", ""), {})
            receiver_nodes = [
                str(n.get("account_id") or n.get("id") or n.get("accountId", ""))
                for n in graph.get("nodes", [])
                if str(n.get("account_id") or n.get("id") or n.get("accountId", ""))
                   != str(transaction.get("sender_account", ""))
                   and n.get("status", AccountStatus.ACTIVE) == AccountStatus.ACTIVE
            ]
            for suspect_id in receiver_nodes:
                _key = f"{case['case_id']}:{suspect_id}"
                # Deduplicate: skip if an active timer already exists for this node
                if withdrawal_tracker.is_active(_key):
                    print(f"  [EC-03] Withdrawal timer already running for node {suspect_id} — skipping duplicate")
                    continue
                _task = asyncio.create_task(
                    schedule_withdrawal(
                        case_id=case["case_id"],
                        suspect_node_id=suspect_id,
                        store=data_store,
                        manager=manager,
                        delay_seconds=WITHDRAWAL_DELAY_SECONDS,
                        persist_fn=save_case,
                    )
                )
                withdrawal_tracker.register(_key, _task)
                print(f"  [EC-03] Withdrawal timer started for node {suspect_id} "
                      f"(fires in {WITHDRAWAL_DELAY_SECONDS}s)")
    else:
        # Persist transaction even without a case (thread-pool, non-blocking)
        try:
            _loop = asyncio.get_event_loop()
            await _loop.run_in_executor(None, save_transaction, transaction)
        except Exception as _pe:
            print(f"  [Persistence] TX write error: {_pe}")

    return result
