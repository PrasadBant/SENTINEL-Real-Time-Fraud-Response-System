import asyncio
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv()

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.data_store import data_store
from app.core.database import init_db
from app.core.persistence import save_transaction, save_case, save_action, load_all_into_store
from app.services.mock_apis import mock_bank_freeze, mock_police_alert, mock_telecom_flag, mock_monitor_account, mock_close_case
from app.services.orchestrator import run_pipeline
from app.services.withdrawal_simulator import schedule_withdrawal
from app.core.config import WITHDRAWAL_DELAY_SECONDS

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SENTINEL - Real-Time Fraud Response System")

@app.on_event("startup")
async def on_startup() -> None:
    """Initialize the database and restore in-memory state from SQLite."""
    init_db()
    load_all_into_store(data_store)
    
    # Spawn Phase 4: Global Graph Analytics background task
    from app.services.global_graph_analyzer import run_global_graph_analyzer
    asyncio.create_task(run_global_graph_analyzer(manager, data_store))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections = [ws for ws in self.active_connections if ws is not websocket]

    async def broadcast(self, message: dict[str, Any]) -> None:
        failed: list[WebSocket] = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                failed.append(ws)
        for ws in failed:
            self.disconnect(ws)


manager = ConnectionManager()

# EC-03: tracks in-flight withdrawal tasks keyed by "case_id:node_id"
# to prevent duplicate timers for the same suspect node.
_pending_withdrawals: dict[str, asyncio.Task] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_nodes(nodes: Any) -> list[dict[str, Any]]:
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
                "status": node.get("status", "active"),
                "balance": float(node.get("balance", 0.0)),
            }
        )
    return normalized


def _normalize_edges(edges: Any) -> list[dict[str, Any]]:
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


def _normalize_action_log(case: dict[str, Any]) -> list[dict[str, Any]]:
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
                "status": entry.get("status", "ACK"),
                "timestamp": entry.get("timestamp") or _now_iso(),
                "reason": entry.get("reason", "System Action"),
                "latency": int(entry.get("latency", 0)),
            }
        )
    return normalized


def _case_payload(case: dict[str, Any]) -> dict[str, Any]:
    case_id = case.get("case_id", "")
    graph = data_store.get("graphs", {}).get(case_id, {"nodes": [], "edges": []})
    nodes = _normalize_nodes(graph.get("nodes", []))
    edges = _normalize_edges(graph.get("edges", []))
    # Fetch full transaction objects linked to this case
    tx_ids = case.get("transactions", [])
    tx_store = data_store.get("transactions", {})
    transactions = [tx_store[tid] for tid in tx_ids if tid in tx_store]

    return {
        "case_id": case_id,
        "status": case.get("status", "NEW"),
        "primary_tx_id": case.get("primary_tx_id", ""), # Expose primary TX
        "nodes": nodes,
        "edges": edges,
        "transactions": transactions, # Added full objects
        "recoverable_amount": float(case.get("recoverable_amount", 0.0)),
        "recovery_pct": float(case.get("recovery_pct", 0.0)),
        "actionLog": _normalize_action_log(case),
        "risk_level": float(case.get("risk_level", 0.0)),
        "golden_window_minutes": int(case.get("golden_window_minutes", 0)),
        "total_fraud_amount": float(case.get("total_fraud_amount", 0.0)),
        "chain": case.get("chain", []),
    }


class ActionRequest(BaseModel):
    case_id: str
    account_id: str | None = None
    target_id: str | None = None
    reason: str | None = None


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "Sentinel API is healthy"}


@app.post("/transaction")
async def process_tx(request: Request) -> dict[str, Any]:
    tx = await request.json()
    result = run_pipeline(tx, data_store)

    transaction = result.get("transaction") or {}
    tx_event = {
        "event": "tx_scored",
        "tx_id": transaction.get("tx_id", ""),
        "case_id": transaction.get("case_id", ""),
        "risk_score": float(transaction.get("risk_score", 0.0)),
        "amount": float(transaction.get("amount", 0.0)),
        "sender_account": transaction.get("sender_account", "UNKNOWN"),
        "receiver_account": transaction.get("receiver_account", "UNKNOWN"),
        "channel": transaction.get("channel", "UPI"),
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
    await manager.broadcast(tx_event)

    case = result.get("case")
    if case:
        case_event = {"event": "case_updated", **_case_payload(case)}
        await manager.broadcast(case_event)

        # ── Persist to SQLite (thread-pool, non-blocking) ───────────────
        try:
            _loop = asyncio.get_event_loop()
            await _loop.run_in_executor(None, save_transaction, transaction)
            await _loop.run_in_executor(None, save_case, case)
        except Exception as _pe:
            print(f"  [Persistence] Write error: {_pe}")

        # ── EC-03: Schedule mule withdrawal for new HIGH_RISK cases ──────
        if case.get("status") == "HIGH_RISK":
            graph = data_store.get("graphs", {}).get(case.get("case_id", ""), {})
            receiver_nodes = [
                str(n.get("account_id") or n.get("id") or n.get("accountId", ""))
                for n in graph.get("nodes", [])
                if str(n.get("account_id") or n.get("id") or n.get("accountId", ""))
                   != str(transaction.get("sender_account", ""))
                   and n.get("status", "active") == "active"
            ]
            for suspect_id in receiver_nodes:
                _key = f"{case['case_id']}:{suspect_id}"
                # Deduplicate: skip if an active timer already exists for this node
                existing = _pending_withdrawals.get(_key)
                if existing and not existing.done():
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
                _pending_withdrawals[_key] = _task
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


@app.get("/cases")
def get_cases() -> list[dict[str, Any]]:
    return [_case_payload(case) for case in data_store.get("cases", {}).values()]


@app.get("/export/sentinel_audit.csv")
def export_csv():
    """
    Generates and streams a CSV audit log from the in-memory store.
    Includes all transactions and investigative actions.
    Browser handles this as a native file download.
    """
    from fastapi.responses import StreamingResponse
    import io, csv
    from datetime import datetime, timezone as _tz

    output = io.StringIO()
    # UTF-8 BOM so Excel opens correctly
    output.write('\ufeff')

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
        level = "HIGH_RISK" if score >= 70 else "MEDIUM" if score >= 40 else "LOW"
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
                a.get("status", "ACK"),
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


def _record_action(case_id: str, action_type: str, target_id: str, status: str, reason: str | None = None) -> dict[str, Any]:
    case = data_store.get("cases", {}).get(case_id)
    if not case:
        return {}
    entry = {
        "action_id": f"ACT-{uuid4().hex[:10].upper()}",
        "case_id": case_id,
        "action_type": action_type,
        "target_id": target_id,
        "target": target_id,
        "status": "ACK" if status == "SUCCESS" else "NACK",
        "timestamp": _now_iso(),
        "reason": reason or "Operator decision",
        "latency": 0,
    }
    case.setdefault("actions_taken", []).insert(0, entry)
    
    # Persist the action to SQLite (note: _record_action is sync, called from async context
    # via run_in_executor at the call site for heavy traffic; here we keep inline for
    # simplicity since action writes are rare compared to TX ingestion)
    try:
        save_action(entry)
    except Exception as _pe:
        print(f"  [Persistence] Action write error: {_pe}")
    
    # Status Mapping based on actions
    if entry["status"] == "ACK":
        if action_type in ["FREEZE", "FLAG", "ALERT"]:
            case["status"] = "ACTIONED"
        elif action_type == "MONITOR":
            case["status"] = "MONITORING"
        elif action_type == "CLOSE":
            case["status"] = "CLOSED"
        elif action_type == "CLOSE_FP":
            case["status"] = "CLOSED_FP"
            
    return entry


async def _handle_action(action_name: str, payload: ActionRequest) -> dict[str, Any]:
    case = data_store.get("cases", {}).get(payload.case_id)
    target_id = payload.account_id or payload.target_id or "GLOBAL"
    if not case:
        return {
            "ok": False,
            "event": "action_taken",
            "case_id": payload.case_id,
            "action": action_name,
            "target_id": target_id,
            "status": "NACK",
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
                node["status"] = "frozen"
                # EC-03: cancel any pending withdrawal timer for this now-frozen node
                _key = f"{payload.case_id}:{acc_id}"
                _task = _pending_withdrawals.get(_key)
                if _task and not _task.done():
                    _task.cancel()
                    print(f"  [EC-03] Withdrawal task cancelled for frozen node {acc_id}")
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
        "status": action_entry.get("status", "NACK"),
        "action_id": action_entry.get("action_id"),
        "timestamp": action_entry.get("timestamp", _now_iso()),
    }

    await manager.broadcast(response)
    await manager.broadcast({"event": "case_updated", **_case_payload(case)})
    return response


@app.post("/action/freeze")
async def freeze_action(payload: ActionRequest) -> dict[str, Any]:
    return await _handle_action("freeze", payload)


@app.post("/action/flag")
async def flag_action(payload: ActionRequest) -> dict[str, Any]:
    return await _handle_action("flag", payload)


@app.post("/action/alert")
async def alert_action(payload: ActionRequest) -> dict[str, Any]:
    return await _handle_action("alert", payload)


@app.post("/action/monitor")
async def monitor_action(payload: ActionRequest) -> dict[str, Any]:
    return await _handle_action("monitor", payload)


@app.post("/action/close")
async def close_action(payload: ActionRequest) -> dict[str, Any]:
    return await _handle_action("close", payload)


@app.post("/action/close_fp")
async def close_fp_action(payload: ActionRequest) -> dict[str, Any]:
    return await _handle_action("close_fp", payload)


@app.post("/attack-mode")
async def trigger_attack_mode() -> dict[str, Any]:
    """
    Triggers a burst of 5 high-risk transactions to simulate an active fraud attack.
    Each transaction is injected directly into the pipeline and broadcast via WebSocket.
    """
    import asyncio, random, string, uuid as _uuid
    from datetime import datetime, timezone as _tz

    def _rnd_id():
        return f"TX-{str(_uuid.uuid4())[:8].upper()}"

    def _rnd_acc(prefix):
        sfx = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"{prefix}-{sfx}-{random.randint(1000,9999)}"

    def _now():
        return datetime.now(_tz.utc).isoformat().replace("+00:00", "Z")

    ATTACK_TEMPLATES = [
        {"is_cross_border": True, "channel": "NEFT",  "amount_range": (200000, 500000)},
        {"is_crypto_related": True, "channel": "IMPS", "amount_range": (300000, 500000)},
        {"device_changed": True, "location_changed": True, "channel": "UPI", "amount_range": (50000, 100000)},
        {"on_active_call": True, "is_scripted": True,  "channel": "CARD", "amount_range": (100000, 200000)},
        {"bulk_transfer_flag": True, "channel": "NEFT", "amount_range": (250000, 500000)},
    ]

    async def _fire_burst():
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
            tx_event = {
                "event": "tx_scored",
                "tx_id": transaction.get("tx_id", ""),
                "case_id": transaction.get("case_id", ""),
                "risk_score": float(transaction.get("risk_score", 0.0)),
                "amount": float(transaction.get("amount", 0.0)),
                "sender_account": transaction.get("sender_account", "UNKNOWN"),
                "receiver_account": transaction.get("receiver_account", "UNKNOWN"),
                "channel": transaction.get("channel", "NEFT"),
                "risk_factors": transaction.get("risk_factors", []),
                "threshold": transaction.get("threshold", "LOW"),
                "reason": transaction.get("reason", "Low risk pattern"),
                "full_reason": transaction.get("full_reason", ""),
                "confidence": transaction.get("confidence", "LOW"),
                "ml_score": transaction.get("ml_score", 0),
                "rule_score": transaction.get("rule_score", 0),
                "ml_feature_importance": transaction.get("ml_feature_importance", {})
            }
            await manager.broadcast(tx_event)
            case = result.get("case")
            if case:
                await manager.broadcast({"event": "case_updated", **_case_payload(case)})
            await asyncio.sleep(0.8)

    asyncio.create_task(_fire_burst())
    return {"ok": True, "message": "Attack mode burst initiated — 5 high-risk transactions injected"}


class CopilotRequest(BaseModel):
    message: str
    context_case_id: str | None = None

@app.post("/api/copilot")
async def copilot_chat(req: CopilotRequest) -> dict[str, Any]:
    import os
    
    # 1. Gather Context (RAG)
    context_data = "No specific case selected. The user is asking a general question."
    if req.context_case_id:
        case = data_store.get("cases", {}).get(req.context_case_id)
        if case:
            context_data = f"**Case ID:** {case['case_id']}\n**Status:** {case['status']}\n**Risk Level:** {case.get('risk_level', 0)}%\n"
            # Add transaction context
            tx_ids = case.get("transactions", [])
            txs = [data_store.get("transactions", {}).get(t) for t in tx_ids if t in data_store.get("transactions", {})]
            if txs:
                context_data += f"**Transactions involved:** {len(txs)}\n"
                context_data += "**Latest Transaction Details:**\n"
                latest_tx = txs[0]
                context_data += f"- Amount: {latest_tx.get('amount', 0)} INR\n"
                context_data += f"- Sender: {latest_tx.get('sender_account', 'Unknown')}\n"
                context_data += f"- Receiver: {latest_tx.get('receiver_account', 'Unknown')}\n"
                context_data += f"- Type: {latest_tx.get('type', 'N/A')}\n"

    # 2. Check Intent for Tool Calling
    user_msg = req.message.lower()
    action_taken = None
    reply = ""

    # Simple intent parsing for Hackathon demo
    if "freeze" in user_msg and req.context_case_id:
        # Execute FREEZE Tool
        action_payload = ActionRequest(case_id=req.context_case_id, target_id="GLOBAL", reason="AI Copilot Action")
        await _handle_action("freeze", action_payload)
        reply = f"✅ **Action Executed:** I have applied a **FREEZE** on all accounts associated with Case `{req.context_case_id}` to prevent further fund movement."
        action_taken = {"type": "FREEZE_ACCOUNTS", "case_id": req.context_case_id}
    elif "close" in user_msg and req.context_case_id:
        action_payload = ActionRequest(case_id=req.context_case_id, reason="AI Copilot closed")
        await _handle_action("close", action_payload)
        reply = f"✅ **Action Executed:** Case `{req.context_case_id}` has been **closed** and marked as resolved."
        action_taken = {"type": "CLOSE_CASE", "case_id": req.context_case_id}
    else:
        hf_api_key = os.getenv("HF_API_KEY")
        hf_success = False
        
        if hf_api_key:
            try:
                import urllib.request
                import json
                # Use the Hugging Face serverless inference API with standard Chat Completions
                url = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-7B-Instruct/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {hf_api_key}",
                    "Content-Type": "application/json"
                }
                
                system_prompt = (
                    "You are 'Sentinel AI', an elite, highly professional enterprise fraud intelligence assistant. "
                    "Your goal is to provide concise, data-driven, and highly actionable insights to fraud analysts. "
                    "Use Markdown formatting (bolding, bullet points) to make your responses extremely engaging and easy to read. "
                    "Always maintain a confident, professional, and analytical tone. Keep responses under 150 words."
                )
                
                payload = {
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"User Request: '{req.message}'\n\nContext Data:\n{context_data}\n\nPlease provide your professional analysis."}
                    ],
                    "max_tokens": 300,
                    "temperature": 0.3,
                    "top_p": 0.9
                }
                
                req_obj = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
                with urllib.request.urlopen(req_obj, timeout=5.0) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    if "choices" in result and len(result["choices"]) > 0:
                        reply = result["choices"][0]["message"]["content"].strip()
                        hf_success = True
            except Exception as e:
                # Fallback on failure (e.g., DNS error, proxy block, timeout, or rate limit)
                print(f"[Copilot Warning] Hugging Face API failed: {e}. Falling back to local AI.")
                # Force hf_success to False explicitly to trigger offline fallback
                hf_success = False
                
        if not hf_success:
            # High-quality dynamic simulator for offline fallback/missing token
            case_id = req.context_case_id or "UNKNOWN"
            if req.context_case_id and req.context_case_id in data_store.get("cases", {}):
                case = data_store["cases"][req.context_case_id]
                risk = case.get("risk_level", 50)
                tx_ids = case.get("transactions", [])
                txs = [data_store.get("transactions", {}).get(t) for t in tx_ids if t in data_store.get("transactions", {})]
                amount = txs[0].get("amount", 0.0) if txs else 0.0
                sender = txs[0].get("sender_account", "N/A") if txs else "N/A"
                receiver = txs[0].get("receiver_account", "N/A") if txs else "N/A"
                
                if risk >= 70:
                    reply = f"**[Sentinel Offline AI]** Analysis of Case `{case_id}` indicates **high-risk** activity (Risk: {risk}%). \n\nThe transaction of **{amount} INR** from `{sender}` to `{receiver}` shows strong patterns of mule routing. \n\nI recommend freezing the destination account and alerting the recipient bank immediately."
                else:
                    reply = f"**[Sentinel Offline AI]** Case `{case_id}` exhibits **moderate risk** indicators (Risk: {risk}%). \n\nThe transaction of **{amount} INR** from `{sender}` to `{receiver}` deviates from the sender's average historical velocity. \n\nI recommend placing the receiver account on monitoring and reviewing further hops."
            else:
                msg_lower = req.message.lower()
                if "what" in msg_lower and "sentinel" in msg_lower:
                    reply = "**[Sentinel Offline AI]** Sentinel is a Real-Time Fraud Response System. It monitors transactions, constructs behavioral graphs, and applies machine learning to detect and mitigate fraudulent activities instantaneously."
                elif "how" in msg_lower and "freeze" in msg_lower:
                    reply = "**[Sentinel Offline AI]** To freeze a suspect account, select a case from the dashboard and use the **FREEZE** action. This will simulate an API call to the destination bank to hold the funds."
                elif "hello" in msg_lower or "hi" in msg_lower:
                    reply = "**[Sentinel Offline AI]** Hello! I am Sentinel's AI Copilot. I am currently running in offline mode. Please select a specific case from the graph for me to analyze, or ask me general questions about Sentinel."
                elif "fix" in msg_lower:
                    reply = "**[Sentinel Offline AI]** To fix network restrictions and restore the live HuggingFace AI engine, ensure your firewall allows outbound connections to `api-inference.huggingface.co`. In the meantime, I am fully capable of answering basic questions locally!"
                else:
                    reply = f"**[Sentinel Offline AI]** I am currently running in offline mode due to network restrictions. \n\nPlease select a specific case from the graph to analyze, or ask me basic questions about Sentinel. Restore the live HuggingFace AI engine for full dynamic capabilities."

    return {"reply": reply, "action": action_taken}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await websocket.send_json({"event": "connected", "status": "LIVE"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, env_file=".env")
