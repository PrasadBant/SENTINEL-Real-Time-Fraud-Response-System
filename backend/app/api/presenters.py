"""
SENTINEL — Response Presenters
=================================
Shapes internal data_store dicts into the wire format the frontend
expects (camelCase/snake_case aliases, defaulted fields, etc.). Used by
every router that returns transaction or case data, and by the
WebSocket broadcast payloads.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.constants import AccountStatus, ActionStatus, CaseStatus
from app.core.data_store import data_store


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_nodes(nodes: Any) -> list[dict[str, Any]]:
    if not isinstance(nodes, list):
        return []
    normalized = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        account_id = node.get("account_id") or node.get("accountId") or node.get("id")
        if not account_id:
            continue
        normalized.append(
            {
                "account_id": str(account_id),
                "accountId": str(account_id),
                "id": str(account_id),
                "status": node.get("status", AccountStatus.ACTIVE),
                "balance": float(node.get("balance", 0.0)),
            }
        )
    return normalized


def normalize_edges(edges: Any) -> list[dict[str, Any]]:
    if not isinstance(edges, list):
        return []
    normalized = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = edge.get("source") or edge.get("from")
        target = edge.get("target") or edge.get("to")
        tx_id = edge.get("tx_id") or edge.get("id") or f"{source}-{target}"
        if not source or not target:
            continue
        normalized.append(
            {
                "id": str(tx_id),
                "tx_id": str(tx_id),
                "source": str(source),
                "target": str(target),
                "from": str(source),
                "to": str(target),
                "amount": float(edge.get("amount", 0.0)),
                "timestamp": edge.get("timestamp"),
            }
        )
    return normalized


def normalize_action_log(case: dict[str, Any]) -> list[dict[str, Any]]:
    raw = case.get("actionLog")
    if isinstance(raw, list):
        return raw
    raw = case.get("actions_taken")
    if not isinstance(raw, list):
        return []
    normalized = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        target_id = entry.get("target_id") or entry.get("target") or "GLOBAL"
        normalized.append(
            {
                "action_id": str(entry.get("action_id") or f"action_{uuid4().hex[:10]}"),
                "case_id": entry.get("case_id") or case.get("case_id"),
                "action_type": str(entry.get("action_type") or "").upper(),
                "action": str(entry.get("action") or entry.get("action_type") or "").lower(),
                "target_id": target_id,
                "target": target_id,
                "status": entry.get("status", ActionStatus.ACK),
                "timestamp": entry.get("timestamp") or now_iso(),
                "reason": entry.get("reason", "System Action"),
                "latency": int(entry.get("latency", 0)),
            }
        )
    return normalized


def case_payload(case: dict[str, Any]) -> dict[str, Any]:
    case_id = case.get("case_id", "")
    graph = data_store.get("graphs", {}).get(case_id, {"nodes": [], "edges": []})
    nodes = normalize_nodes(graph.get("nodes", []))
    edges = normalize_edges(graph.get("edges", []))
    # Fetch full transaction objects linked to this case
    tx_ids = case.get("transactions", [])
    tx_store = data_store.get("transactions", {})
    transactions = [tx_store[tid] for tid in tx_ids if tid in tx_store]

    return {
        "case_id": case_id,
        "status": case.get("status", CaseStatus.NEW),
        "primary_tx_id": case.get("primary_tx_id", ""),  # Expose primary TX
        "nodes": nodes,
        "edges": edges,
        "transactions": transactions,  # Added full objects
        "recoverable_amount": float(case.get("recoverable_amount", 0.0)),
        "recovery_pct": float(case.get("recovery_pct", 0.0)),
        "actionLog": normalize_action_log(case),
        "risk_level": float(case.get("risk_level", 0.0)),
        "golden_window_minutes": int(case.get("golden_window_minutes", 0)),
        "total_fraud_amount": float(case.get("total_fraud_amount", 0.0)),
        "chain": case.get("chain", []),
    }


def build_tx_event(transaction: dict[str, Any], default_channel: str = "UPI") -> dict[str, Any]:
    """
    Shape a scored transaction into the "tx_scored" WebSocket broadcast
    payload. Shared by both POST /transaction and POST /attack-mode, which
    previously built this same ~15-field dict independently (and could
    silently drift from each other).
    """
    return {
        "event": "tx_scored",
        "tx_id": transaction.get("tx_id", ""),
        "case_id": transaction.get("case_id", ""),
        "risk_score": float(transaction.get("risk_score", 0.0)),
        "amount": float(transaction.get("amount", 0.0)),
        "sender_account": transaction.get("sender_account", "UNKNOWN"),
        "receiver_account": transaction.get("receiver_account", "UNKNOWN"),
        "channel": transaction.get("channel", default_channel),
        "risk_factors": transaction.get("risk_factors", []),
        "threshold": transaction.get("threshold", "LOW"),
        "reason": transaction.get("reason", "Low risk pattern"),
        "full_reason": transaction.get("full_reason", ""),
        "confidence": transaction.get("confidence", "LOW"),
        "ml_score": transaction.get("ml_score", 0),
        "rule_score": transaction.get("rule_score", 0),
        "ml_feature_importance": transaction.get("ml_feature_importance", {}),
        "gnn_available": transaction.get("gnn_available", False),
    }
