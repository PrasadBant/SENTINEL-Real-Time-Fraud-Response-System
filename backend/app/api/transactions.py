"""
SENTINEL — Transaction Ingestion Route
=========================================
POST /transaction: runs the scoring pipeline, broadcasts the result, and
(for cases that just escalated to HIGH_RISK) starts the EC-03 mule
withdrawal countdown for each newly-linked suspect node.
"""

import asyncio
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends

from app.api.presenters import build_tx_event, case_payload
from app.core.constants import AccountStatus, CaseStatus
from app.core.config import WITHDRAWAL_DELAY_SECONDS
from app.core.data_store import data_store
from app.core.deps import verify_simulator_key
from app.core.logging_config import CORRELATION_ID
from app.core.models.transaction import Transaction
from app.core.repository import repository
from app.services import withdrawal_tracker
from app.services.orchestrator import run_pipeline
from app.services.withdrawal_simulator import schedule_withdrawal
from app.websocket.connection_manager import manager

logger = logging.getLogger("sentinel.transactions")

router = APIRouter()


@router.post("/transaction", dependencies=[Depends(verify_simulator_key)])
async def process_tx(tx_in: Transaction) -> dict[str, Any]:
    # One correlation ID per request, threaded through every log line this
    # transaction touches (scoring, persistence, EC-03 scheduling) via the
    # CORRELATION_ID contextvar — see app/core/logging_config.py. Set
    # before anything else runs so even an early failure is traceable.
    CORRELATION_ID.set(str(uuid4()))

    # FastAPI validates the body against Transaction before this runs — bad
    # payloads (missing tx_id/amount, non-positive amount, wrong types) are
    # rejected with a 422 automatically, instead of reaching the pipeline
    # and failing deep inside with an opaque error.
    tx = tx_in.model_dump(mode="json", exclude_none=True)

    # ── Idempotency ───────────────────────────────────────────────────────
    # Prefer whatever key the caller supplied — ideally the payment rail's
    # own reference number (UPI/IMPS/NEFT), which lets us detect the *same*
    # real-world transfer arriving under a *different* tx_id (e.g. a client
    # retry after a timeout, unaware the first attempt already succeeded).
    # If none was supplied, generate a placeholder so every row still has
    # one — but a generated key can never dedupe anything: each retry
    # mints a fresh one, so this only protects requests where the caller
    # actually sends a stable reference.
    idempotency_key = tx.get("idempotency_key") or f"sentinel-{uuid4()}"
    tx["idempotency_key"] = idempotency_key

    duplicate = repository.get_transaction_by_idempotency_key(idempotency_key)
    if duplicate is not None:
        # Already processed — return the original result unchanged. No
        # re-scoring, no re-broadcast, no new EC-03 timer: a retried
        # request must not repeat the side effects of the first one.
        dup_case_id = duplicate.get("case_id")
        dup_case = data_store.get("cases", {}).get(dup_case_id) if dup_case_id else None
        if dup_case is None and dup_case_id:
            dup_case = repository.get_case(dup_case_id)
        # data_store["graphs"] is never persisted (a pre-existing gap, not
        # introduced here — see repository.load_all()'s docstring), so a
        # replay after a process restart won't have the original graph
        # available even though the first response did.
        dup_graph = data_store.get("graphs", {}).get(dup_case_id) if dup_case_id else None
        return {"transaction": duplicate, "case": dup_case, "graph": dup_graph, "recovery": None}

    result = run_pipeline(tx, data_store)

    transaction = result.get("transaction") or {}
    tx_event = build_tx_event(transaction, default_channel="UPI")
    await manager.broadcast(tx_event)

    case = result.get("case")
    if case:
        case_event = {"event": "case_updated", **case_payload(case)}
        await manager.broadcast(case_event)

        # ── Persist to Postgres (thread-pool, non-blocking) ─────────────
        try:
            _loop = asyncio.get_event_loop()
            await _loop.run_in_executor(None, repository.save_transaction, transaction)
            await _loop.run_in_executor(None, repository.save_case, case)
        except Exception as _pe:
            logger.warning("Write error: %s", _pe)

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
                    logger.info("Withdrawal timer already running for node %s — skipping duplicate", suspect_id)
                    continue
                _task = asyncio.create_task(
                    schedule_withdrawal(
                        case_id=case["case_id"],
                        suspect_node_id=suspect_id,
                        store=data_store,
                        manager=manager,
                        delay_seconds=WITHDRAWAL_DELAY_SECONDS,
                        persist_fn=repository.save_case,
                    )
                )
                withdrawal_tracker.register(_key, _task)
                logger.info("Withdrawal timer started for node %s (fires in %ss)", suspect_id, WITHDRAWAL_DELAY_SECONDS)
    else:
        # Persist transaction even without a case (thread-pool, non-blocking)
        try:
            _loop = asyncio.get_event_loop()
            await _loop.run_in_executor(None, repository.save_transaction, transaction)
        except Exception as _pe:
            logger.warning("TX write error: %s", _pe)

    return result
