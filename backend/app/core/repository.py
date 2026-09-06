"""
SENTINEL — Repository Layer
==============================
Synchronous, direct-to-Postgres replacement for app/core/persistence.py's
background-writer-thread pattern. Every write commits before returning —
no queue, no "eventually persisted." This is the strangler-fig cutover
point (see the Phase 0 build plan): Postgres becomes the actual source of
truth; the in-memory app.core.data_store dict stays exactly as it is
today as the process-local working cache the engines (case_manager,
graph_engine, orchestrator, ...) already read/mutate directly — it's just
no longer authoritative, and it's hydrated from this repository at
startup instead of from SQLite.

Field mapping and dict shapes are unchanged from persistence.py's
_do_save_*/load_all_into_store — this is a swap of the storage
mechanism, not a redesign of what gets stored.
"""

import json
import time
from datetime import datetime as _dt

from sqlalchemy.exc import IntegrityError

from app.core.constants import ActionStatus, CaseStatus, DEFAULT_TENANT_ID
from app.core.database import SessionLocal
from app.core.db_models import ActionRecord, CaseRecord, TransactionRecord


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


class Repository:
    """One instance (see the module-level `repository` below) is all any
    caller needs — there's no per-request state here, just a thin wrapper
    around SessionLocal so every method opens, uses, and closes its own
    session (matching the short-lived-session style the rest of the app
    already uses elsewhere, e.g. app.core.deps.get_db)."""

    # ── Transactions ─────────────────────────────────────────────────────

    def save_transaction(self, tx: dict, tenant_id: str = DEFAULT_TENANT_ID) -> None:
        """Upsert a transaction row by tx_id, synchronously."""
        tx_id = tx.get("tx_id")
        if not tx_id:
            return
        db = SessionLocal()
        try:
            existing = db.query(TransactionRecord).filter_by(tx_id=tx_id).first()
            if existing:
                existing.case_id = tx.get("case_id")
                existing.risk_score = float(tx.get("risk_score", 0))
                existing.threshold = tx.get("threshold")
                if tx.get("idempotency_key"):
                    existing.idempotency_key = tx["idempotency_key"]
                existing.payload = _to_json(tx)
            else:
                record = TransactionRecord(
                    tx_id=tx_id,
                    case_id=tx.get("case_id"),
                    tenant_id=tenant_id,
                    idempotency_key=tx.get("idempotency_key"),
                    sender=tx.get("sender_account"),
                    receiver=tx.get("receiver_account"),
                    amount=float(tx.get("amount", 0)),
                    risk_score=float(tx.get("risk_score", 0)),
                    channel=tx.get("channel"),
                    threshold=tx.get("threshold"),
                    timestamp=tx.get("timestamp"),
                    payload=_to_json(tx),
                )
                db.add(record)
            db.commit()
        except IntegrityError:
            # Unique-constraint race: two concurrent POST /transaction
            # calls supplied the same idempotency_key and both passed the
            # pre-insert check in api/transactions.py before either
            # committed. Back off rather than crash the request — each
            # caller's own response was already computed from
            # run_pipeline() before this save runs, so no response is
            # lost, only this particular write is (the row that won the
            # race remains the durable one going forward).
            db.rollback()
            print(f"  [Repository] save_transaction: idempotency_key race on {tx_id}, discarding this write")
        except Exception as e:
            db.rollback()
            print(f"  [Repository] save_transaction failed: {e}")
        finally:
            db.close()

    def get_transaction_by_idempotency_key(self, idempotency_key: str | None) -> dict | None:
        """Return the persisted transaction payload for a given caller-supplied
        idempotency key, or None if no such key has been seen before. Used by
        POST /transaction to short-circuit duplicate submissions."""
        if not idempotency_key:
            return None
        db = SessionLocal()
        try:
            rec = db.query(TransactionRecord).filter_by(idempotency_key=idempotency_key).first()
            return _from_json(rec.payload) if rec else None
        finally:
            db.close()

    # ── Cases ────────────────────────────────────────────────────────────

    def save_case(self, case: dict, tenant_id: str = DEFAULT_TENANT_ID) -> None:
        """Upsert a case row by case_id, synchronously."""
        case_id = case.get("case_id")
        if not case_id:
            return
        db = SessionLocal()
        try:
            existing = db.query(CaseRecord).filter_by(case_id=case_id).first()
            if existing:
                existing.status = case.get("status", existing.status)
                existing.risk_level = float(case.get("risk_level", existing.risk_level))
                existing.total_fraud_amount = float(case.get("total_fraud_amount", existing.total_fraud_amount))
                existing.recoverable_amount = float(case.get("recoverable_amount", existing.recoverable_amount))
                existing.recovery_pct = float(case.get("recovery_pct", existing.recovery_pct))
                existing.payload = _to_json(case)
            else:
                record = CaseRecord(
                    case_id=case_id,
                    tenant_id=tenant_id,
                    status=case.get("status", CaseStatus.NEW),
                    risk_level=float(case.get("risk_level", 0)),
                    total_fraud_amount=float(case.get("total_fraud_amount", 0)),
                    recoverable_amount=float(case.get("recoverable_amount", 0)),
                    recovery_pct=float(case.get("recovery_pct", 0)),
                    golden_window_minutes=int(case.get("golden_window_minutes", 20)),
                    origin_account=case.get("origin_account"),
                    payload=_to_json(case),
                )
                db.add(record)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"  [Repository] save_case failed: {e}")
        finally:
            db.close()

    def get_case(self, case_id: str) -> dict | None:
        """Return the persisted case payload for a given case_id, or None."""
        if not case_id:
            return None
        db = SessionLocal()
        try:
            rec = db.query(CaseRecord).filter_by(case_id=case_id).first()
            return _from_json(rec.payload) if rec else None
        finally:
            db.close()

    # ── Actions ──────────────────────────────────────────────────────────

    def save_action(self, action: dict, tenant_id: str = DEFAULT_TENANT_ID) -> None:
        """Insert a new action row (actions are append-only; no update path,
        matching persistence.py's original semantics). Safe to call with
        case_id="GLOBAL" (proactive-monitor alerts) — actions.case_id has no
        FK, on purpose (see db_models.py and Alembic migration 0002)."""
        action_id = action.get("action_id")
        if not action_id:
            return
        db = SessionLocal()
        try:
            if not db.query(ActionRecord).filter_by(action_id=action_id).first():
                record = ActionRecord(
                    action_id=action_id,
                    case_id=action.get("case_id"),
                    tenant_id=tenant_id,
                    action_type=action.get("action_type"),
                    target_id=action.get("target_id") or action.get("target"),
                    status=action.get("status", ActionStatus.ACK),
                    reason=action.get("reason"),
                    timestamp=action.get("timestamp"),
                    payload=_to_json(action),
                )
                db.add(record)
                db.commit()
        except Exception as e:
            db.rollback()
            print(f"  [Repository] save_action failed: {e}")
        finally:
            db.close()

    # ── Startup restore ──────────────────────────────────────────────────

    def load_all(self, store: dict) -> None:
        """On startup: read every persisted transaction/case from Postgres
        and populate the in-memory data_store so the engines' in-process
        working cache (velocity_cache, accounts, cases, transactions) is
        fully restored — same restore semantics as the old
        persistence.load_all_into_store(), just reading from the
        repository's backing DB instead of SQLite specifically.

        Note: app.core.data_store["graphs"] is NOT restored here — graph
        state (including frozen/withdrawn node status) isn't persisted
        anywhere today. That's a pre-existing gap (real graph persistence
        is Phase 5's job), not something this repository introduces."""
        db = SessionLocal()
        try:
            # ── Restore transactions & rebuild velocity/account caches ──
            tx_count = 0
            v_cache = store.setdefault("velocity_cache", {})
            accounts = store.setdefault("accounts", {})

            for rec in db.query(TransactionRecord).all():
                payload = _from_json(rec.payload)
                if payload:
                    tx_id = payload.get("tx_id") or rec.tx_id
                    store.setdefault("transactions", {})[tx_id] = payload
                    tx_count += 1

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
                            "is_new_receiver": False,  # if it's in history, it's not new generally
                        })
                        acc["total_historical_amount"] += amount
                        acc["historical_tx_count"] += 1

            # ── Restore cases ────────────────────────────────────────────
            case_count = 0
            for rec in db.query(CaseRecord).all():
                payload = _from_json(rec.payload)
                if payload:
                    case_id = payload.get("case_id") or rec.case_id
                    store.setdefault("cases", {})[case_id] = payload
                    case_count += 1

            print(f"  [Repository] Restored {tx_count} transactions, {case_count} cases from DB [OK]")

        except Exception as e:
            print(f"  [Repository] load_all failed: {e}")
        finally:
            db.close()


# Single shared instance — see the class docstring for why one is enough.
repository = Repository()
