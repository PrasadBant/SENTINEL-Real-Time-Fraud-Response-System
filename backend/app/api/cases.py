"""
SENTINEL — Case Read Routes
=============================
GET /cases: full case listing (also the frontend's WebSocket-fallback
polling target). GET /export/sentinel_audit.csv: compliance-style CSV
export of all transactions and investigative actions.

Both read from Postgres (via app.core.repository), not from the
process-local data_store dict directly — hostile-review fix: with
multiple API replicas, data_store["cases"]/["transactions"] only reflect
whatever THIS process has personally created or been told about since it
booted, so a case created via a different replica would silently be
missing from these two endpoints depending on which replica happened to
serve the request. case_payload() (app/api/presenters.py) still enriches
each case with graph nodes/edges/full transaction objects from the local
data_store where available — that part remains a documented, accepted
per-replica gap (graph state isn't persisted or Redis-shared today; real
graph persistence is Phase 5's job), but case existence/status/risk
level/actions-taken are now always consistent regardless of which
replica answers the request.
"""

import csv
import io
import logging
from datetime import datetime, timezone as _tz
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.presenters import case_payload
from app.core.config import HIGH_RISK_THRESHOLD, MEDIUM_THRESHOLD
from app.core.constants import ActionStatus
from app.core.data_store import data_store
from app.core.deps import get_current_user
from app.core.repository import repository

logger = logging.getLogger("sentinel.cases")

router = APIRouter()


def _list_cases_replica_safe() -> list[dict]:
    """Postgres-backed case list — falls back to this replica's local
    cache only if Postgres itself is briefly unreachable, so a transient
    DB hiccup degrades to "this replica's own view" rather than a 500."""
    try:
        return repository.list_cases()
    except Exception as e:
        logger.warning("list_cases degraded (Postgres unavailable: %s) — falling back to local cache", e)
        return list(data_store.get("cases", {}).values())


def _list_transactions_replica_safe() -> list[dict]:
    """Same fallback shape as _list_cases_replica_safe, for transactions."""
    try:
        return repository.list_transactions()
    except Exception as e:
        logger.warning("list_transactions degraded (Postgres unavailable: %s) — falling back to local cache", e)
        return list(data_store.get("transactions", {}).values())


@router.get("/cases")
def get_cases(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
    return [case_payload(case) for case in _list_cases_replica_safe()]


@router.get("/export/sentinel_audit.csv")
def export_csv(user: dict = Depends(get_current_user)):
    """
    Generates and streams a CSV audit log from the in-memory store.
    Includes all transactions and investigative actions.
    Browser handles this as a native file download.
    """
    output = io.StringIO()
    # UTF-8 BOM so Excel opens correctly
    output.write('﻿')

    writer = csv.writer(output, lineterminator='\r\n')

    # ── Section 1: Transactions ───────────────────────────────────────────────
    writer.writerow(['SENTINEL AUDIT LOG - TRANSACTION FEED'])
    writer.writerow([
        'Tx ID', 'Timestamp', 'Channel',
        'Sender Account', 'Receiver Account',
        'Amount (INR)', 'Risk Score', 'Risk Level', 'Case ID'
    ])

    for tx in _list_transactions_replica_safe():
        score = float(tx.get("risk_score", 0))
        level = (
            "HIGH_RISK" if score >= HIGH_RISK_THRESHOLD
            else "MEDIUM" if score >= MEDIUM_THRESHOLD
            else "LOW"
        )
        writer.writerow([
            tx.get("tx_id", ""),
            tx.get("timestamp", ""),
            tx.get("channel", ""),
            tx.get("sender_account", ""),
            tx.get("receiver_account", ""),
            tx.get("amount", ""),
            score,
            level,
            tx.get("case_id", "")
        ])

    # ── Section 2: Investigative Actions ─────────────────────────────────────
    all_actions = []
    for case in _list_cases_replica_safe():
        all_actions.extend(case.get("actions_taken", []))

    if all_actions:
        writer.writerow([])
        writer.writerow(['INVESTIGATIVE ACTIONS'])
        writer.writerow([
            'Action ID', 'Case ID', 'Action Type',
            'Target Account', 'Status', 'Reason', 'Latency (ms)', 'Timestamp'
        ])
        for a in all_actions:
            writer.writerow([
                a.get("action_id", ""),
                a.get("case_id", ""),
                a.get("action_type", ""),
                a.get("target", a.get("target_id", "GLOBAL")),
                a.get("status", ActionStatus.ACK),
                a.get("reason", "System Action"),
                a.get("latency", ""),
                a.get("timestamp", "")
            ])

    output.seek(0)
    ts = datetime.now(_tz.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"sentinel_audit_{ts}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
