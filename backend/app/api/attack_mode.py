"""
SENTINEL — Attack Mode Demo Trigger
======================================
POST /attack-mode: fires a scripted burst of 5 high-risk transactions to
simulate an active fraud attack, for live demos.
"""

import asyncio
import random
import string
import uuid as _uuid
from datetime import datetime, timezone as _tz
from typing import Any

from fastapi import APIRouter, Depends

from app.api.presenters import build_tx_event, case_payload
from app.core.data_store import data_store
from app.core.deps import require_role
from app.services.orchestrator import run_pipeline
from app.websocket.connection_manager import manager

router = APIRouter()

ATTACK_TEMPLATES = [
    {"is_cross_border": True, "channel": "NEFT",  "amount_range": (200000, 500000)},
    {"is_crypto_related": True, "channel": "IMPS", "amount_range": (300000, 500000)},
    {"device_changed": True, "location_changed": True, "channel": "UPI", "amount_range": (50000, 100000)},
    {"on_active_call": True, "is_scripted": True,  "channel": "CARD", "amount_range": (100000, 200000)},
    {"bulk_transfer_flag": True, "channel": "NEFT", "amount_range": (250000, 500000)},
]


def _rnd_id():
    return f"TX-{str(_uuid.uuid4())[:8].upper()}"


def _rnd_acc(prefix):
    sfx = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{sfx}-{random.randint(1000, 9999)}"


def _now():
    return datetime.now(_tz.utc).isoformat().replace("+00:00", "Z")


async def _fire_burst() -> None:
    for tpl in ATTACK_TEMPLATES:
        amount = round(random.uniform(*tpl["amount_range"]), 2)
        tx = {
            "tx_id": _rnd_id(),
            "timestamp": _now(),
            "sender_account": _rnd_acc("ACC-ATTACK"),
            "receiver_account": _rnd_acc("ACC-DRAIN"),
            "amount": amount,
            "currency": "INR",
            "channel": tpl.get("channel", "NEFT"),
            "hop_number": 0,
        }
        for k, v in tpl.items():
            if k not in ("channel", "amount_range"):
                tx[k] = v

        result = run_pipeline(tx, data_store)
        transaction = result.get("transaction") or {}
        tx_event = build_tx_event(transaction, default_channel="NEFT")
        await manager.broadcast(tx_event)
        case = result.get("case")
        if case:
            await manager.broadcast({"event": "case_updated", **case_payload(case)})
        await asyncio.sleep(0.8)


@router.post("/attack-mode")
async def trigger_attack_mode(user: dict = Depends(require_role("admin"))) -> dict[str, Any]:
    """
    Triggers a burst of 5 high-risk transactions to simulate an active fraud attack.
    Each transaction is injected directly into the pipeline and broadcast via WebSocket.
    Admin-only, matching the frontend's AttackModeToggle (disabled for viewers).
    """
    asyncio.create_task(_fire_burst())
    return {"ok": True, "message": "Attack mode burst initiated — 5 high-risk transactions injected"}
