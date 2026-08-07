"""
SENTINEL — Case Read Routes
=============================
GET /cases: full case listing (also the frontend's WebSocket-fallback
polling target). GET /export/sentinel_audit.csv: compliance-style CSV
export of all transactions and investigative actions.
"""

import csv
import io
from datetime import datetime, timezone as _tz
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.presenters import case_payload
from app.core.config import HIGH_RISK_THRESHOLD, MEDIUM_THRESHOLD
from app.core.constants import ActionStatus
from app.core.data_store import data_store
from app.core.deps import get_current_user

router = APIRouter()


@router.get("/cases")
def get_cases(user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:
    return [case_payload(case) for case in data_store.get("cases", {}).values()]


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

    tx_store = data_store.get("transactions", {})
    for tx in tx_store.values():
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
    for case in data_store.get("cases", {}).values():
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
