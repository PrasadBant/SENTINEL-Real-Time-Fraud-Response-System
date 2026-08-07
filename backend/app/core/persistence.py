"""
SENTINEL — Persistence Layer
==============================
Write-through cache helpers: all reads stay in the fast in-memory
data_store dict; writes are mirrored to SQLite via SQLAlchemy.

On startup, load_all_into_store() reads the DB back into memory so
state survives backend restarts.
"""

import json
from app.core.constants import ActionStatus, CaseStatus
from app.core.database import SessionLocal
from app.core.db_models import TransactionRecord, CaseRecord, ActionRecord


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_json(obj: dict) -> str:
    """Safely serialize a dict to JSON string, skipping non-serialisable values."""
    try:
        return json.dumps(obj, default=str)
    except Exception:
        return "{}"


def _from_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


import queue
import threading

# ── Background Writer Thread ──────────────────────────────────────────────────
_write_queue = queue.Queue()

def _db_writer_worker():
    while True:
        try:
            task = _write_queue.get()
            if task is None:
                break
            func, arg = task
            func(arg)
            _write_queue.task_done()
        except Exception as e:
            print(f"  [Persistence Worker] Error: {e}")

_worker_thread = threading.Thread(target=_db_writer_worker, daemon=True)
_worker_thread.start()


# ── Write functions ───────────────────────────────────────────────────────────

def save_transaction(tx: dict) -> None:
    """Enqueue a transaction record for background DB insertion."""
    _write_queue.put((_do_save_transaction, tx))

def _do_save_transaction(tx: dict) -> None:
    tx_id = tx.get("tx_id")
    if not tx_id:
        return
    db = SessionLocal()
    try:
        existing = db.query(TransactionRecord).filter_by(tx_id=tx_id).first()
        if existing:
            existing.case_id    = tx.get("case_id")
            existing.risk_score = float(tx.get("risk_score", 0))
            existing.threshold  = tx.get("threshold")
            existing.payload    = _to_json(tx)
        else:
            record = TransactionRecord(
                tx_id      = tx_id,
                case_id    = tx.get("case_id"),
                sender     = tx.get("sender_account"),
                receiver   = tx.get("receiver_account"),
                amount     = float(tx.get("amount", 0)),
                risk_score = float(tx.get("risk_score", 0)),
                channel    = tx.get("channel"),
                threshold  = tx.get("threshold"),
                timestamp  = tx.get("timestamp"),
                payload    = _to_json(tx),
            )
            db.add(record)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"  [Persistence] _do_save_transaction failed: {e}")
    finally:
        db.close()


def save_case(case: dict) -> None:
    """Enqueue a case record for background DB insertion."""
    _write_queue.put((_do_save_case, case))

def _do_save_case(case: dict) -> None:
    case_id = case.get("case_id")
    if not case_id:
        return
    db = SessionLocal()
    try:
        existing = db.query(CaseRecord).filter_by(case_id=case_id).first()
        if existing:
            existing.status              = case.get("status", existing.status)
            existing.risk_level          = float(case.get("risk_level", existing.risk_level))
            existing.total_fraud_amount  = float(case.get("total_fraud_amount", existing.total_fraud_amount))
            existing.recoverable_amount  = float(case.get("recoverable_amount", existing.recoverable_amount))
            existing.recovery_pct        = float(case.get("recovery_pct", existing.recovery_pct))
            existing.payload             = _to_json(case)
        else:
            record = CaseRecord(
                case_id               = case_id,
                status                = case.get("status", CaseStatus.NEW),
                risk_level            = float(case.get("risk_level", 0)),
                total_fraud_amount    = float(case.get("total_fraud_amount", 0)),
                recoverable_amount    = float(case.get("recoverable_amount", 0)),
                recovery_pct          = float(case.get("recovery_pct", 0)),
                golden_window_minutes = int(case.get("golden_window_minutes", 20)),
                origin_account        = case.get("origin_account"),
                payload               = _to_json(case),
            )
            db.add(record)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"  [Persistence] _do_save_case failed: {e}")
    finally:
        db.close()


def save_action(action: dict) -> None:
    """Enqueue a new action record for background DB insertion."""
    _write_queue.put((_do_save_action, action))

def _do_save_action(action: dict) -> None:
    action_id = action.get("action_id")
    if not action_id:
        return
    db = SessionLocal()
    try:
        if not db.query(ActionRecord).filter_by(action_id=action_id).first():
            record = ActionRecord(
                action_id   = action_id,
                case_id     = action.get("case_id"),
                action_type = action.get("action_type"),
                target_id   = action.get("target_id") or action.get("target"),
                status      = action.get("status", ActionStatus.ACK),
                reason      = action.get("reason"),
                timestamp   = action.get("timestamp"),
                payload     = _to_json(action),
            )
            db.add(record)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"  [Persistence] _do_save_action failed: {e}")
    finally:
        db.close()


# ── Startup restore ───────────────────────────────────────────────────────────

def load_all_into_store(store: dict) -> None:
    """
    On startup: read all persisted records from SQLite and populate
    the in-memory data_store so the application state is fully restored.
    """
    db = SessionLocal()
    try:
        from datetime import datetime as _dt
        import time
        
        # ── Restore transactions & build caches ──────────────────────────
        tx_count = 0
        v_cache = store.setdefault("velocity_cache", {})
        accounts = store.setdefault("accounts", {})
        
        for rec in db.query(TransactionRecord).all():
            payload = _from_json(rec.payload)
            if payload:
                tx_id = payload.get("tx_id") or rec.tx_id
                store.setdefault("transactions", {})[tx_id] = payload
                tx_count += 1
                
                # Rebuild Stateful Aggregates
                sender_id = payload.get("sender_account")
                if sender_id:
                    ts_str = payload.get("timestamp", "")
                    amount = float(payload.get("amount", 0.0))
                    receiver = payload.get("receiver_account")
                    try:
                        dt = _dt.fromisoformat(ts_str.replace("Z", "+00:00"))
                        ts = dt.timestamp()
                    except Exception:
                        ts = time.time()
                        
                    cache_list = v_cache.setdefault(sender_id, [])
                    cache_list.append({"timestamp": ts, "amount": amount, "receiver": receiver})
                    
                    acc = accounts.setdefault(sender_id, {
                        "account_id": sender_id,
                        "status": "active",
                        "total_historical_amount": 0.0,
                        "historical_tx_count": 0,
                        "is_new_receiver": False # If it's in history, it's not new generally
                    })
                    acc["total_historical_amount"] += amount
                    acc["historical_tx_count"] += 1

        # ── Restore cases ─────────────────────────────────────────────────
        case_count = 0
        for rec in db.query(CaseRecord).all():
            payload = _from_json(rec.payload)
            if payload:
                case_id = payload.get("case_id") or rec.case_id
                store.setdefault("cases", {})[case_id] = payload
                case_count += 1

        print(f"  [Persistence] Restored {tx_count} transactions, {case_count} cases from DB [OK]")

    except Exception as e:
        print(f"  [Persistence] load_all_into_store failed: {e}")
    finally:
        db.close()
