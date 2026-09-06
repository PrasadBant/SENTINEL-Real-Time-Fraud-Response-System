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

import logging
import time
from datetime import datetime as _dt, timezone as _tz

from sqlalchemy.exc import IntegrityError

from app.core.constants import ActionStatus, CaseStatus, DEFAULT_TENANT_ID
from app.core.database import SessionLocal
from app.core.db_models import ActionRecord, CaseRecord, TransactionRecord, UserRecord
from app.utils.json_codec import from_json as _from_json, to_json as _to_json

# NOTE: app.services.orchestrator is imported lazily, inside load_all()
# below, not here at module level. orchestrator.py needs to import THIS
# module (to fall back to Postgres for cross-replica case lookups — see
# the hostile-review fix in orchestrator.py's case-resolution code) —
# a top-level `repository -> orchestrator -> repository` cycle would
# make one of the two modules fail to import. Deferring this one import
# to call time (by which point both modules are fully loaded) breaks
# the cycle without changing behavior.

logger = logging.getLogger("sentinel.repository")


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
            logger.warning("save_transaction: idempotency_key race on %s, discarding this write", tx_id)
        except Exception as e:
            db.rollback()
            logger.error("save_transaction failed: %s", e)
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

    def get_transaction(self, tx_id: str) -> dict | None:
        """Return the persisted transaction payload for a given tx_id, or
        None. Used as the cross-replica fallback when a case's transaction
        list (app/api/presenters.py's case_payload()) references a tx_id
        this process never personally scored — e.g. it was processed by a
        different API replica."""
        if not tx_id:
            return None
        db = SessionLocal()
        try:
            rec = db.query(TransactionRecord).filter_by(tx_id=tx_id).first()
            return _from_json(rec.payload) if rec else None
        finally:
            db.close()

    def list_all_transactions(self) -> list[dict]:
        """Return every persisted transaction payload, across every tenant.
        Pipeline-internal use only (repository.load_all()'s startup
        restore) — never reachable from a user-supplied request, so it's
        deliberately not tenant-filtered. User-facing reads must use
        list_transactions(tenant_id) below instead."""
        db = SessionLocal()
        try:
            return [p for rec in db.query(TransactionRecord).all() if (p := _from_json(rec.payload))]
        finally:
            db.close()

    def list_transactions(self, tenant_id: str) -> list[dict]:
        """Return every persisted transaction payload belonging to one
        tenant. Phase 2 object-level authorization: this is what makes
        GET /export's CSV audit log (app/api/cases.py) show only the
        requesting investigator's own tenant's data, not every tenant's —
        tenant_id is required (no default) so a call site can't
        accidentally fall back to "everyone's data" by omission."""
        db = SessionLocal()
        try:
            return [
                p for rec in db.query(TransactionRecord).filter_by(tenant_id=tenant_id).all()
                if (p := _from_json(rec.payload))
            ]
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
            logger.error("save_case failed: %s", e)
        finally:
            db.close()

    def get_case(self, case_id: str) -> dict | None:
        """Return the persisted case payload for a given case_id, or None
        — unscoped by tenant. Pipeline-internal use only (e.g.
        app/services/orchestrator.py's cross-replica case-chain fallback,
        app/api/transactions.py's idempotent-replay path): both operate
        on the single ingestion tenant's own data and are never driven by
        a user-supplied case_id, so there's no object-level-authorization
        concern here. A case_id an authenticated investigator supplies
        (e.g. app/api/actions.py's action handlers) must use
        get_case_for_tenant below instead — see its docstring for why."""
        if not case_id:
            return None
        db = SessionLocal()
        try:
            rec = db.query(CaseRecord).filter_by(case_id=case_id).first()
            return _from_json(rec.payload) if rec else None
        finally:
            db.close()

    def get_case_for_tenant(self, case_id: str, tenant_id: str) -> dict | None:
        """Same as get_case, but also requires the case to belong to
        tenant_id — returns None (not a distinguishable "wrong tenant"
        error) if the case exists but belongs to someone else, so
        existence isn't leaked. This is the actual IDOR fix (Phase 2):
        case_id is a guessable-ish `CASE-XXXXXXXX` string, not a
        high-entropy UUID, and every investigator action (freeze, close,
        ...) takes one directly from the request body — without this,
        any authenticated admin could act on any tenant's case just by
        supplying its id. Use this, not get_case, for any lookup driven
        by a value an authenticated user supplied."""
        if not case_id:
            return None
        db = SessionLocal()
        try:
            rec = db.query(CaseRecord).filter_by(case_id=case_id, tenant_id=tenant_id).first()
            return _from_json(rec.payload) if rec else None
        finally:
            db.close()

    def list_all_cases(self) -> list[dict]:
        """Return every persisted case payload, across every tenant. This
        is what makes case-chain matching in app/services/orchestrator.py
        correct across multiple API replicas: data_store["cases"] alone
        only holds whatever this one process has personally created or
        been told about since it booted, so a case another replica
        created would otherwise be invisible here. Pipeline-internal use
        only — never reachable from a user-supplied request (matching is
        keyed off sender/receiver account, not anything the requester
        picks), so it's deliberately not tenant-filtered. User-facing
        reads must use list_cases(tenant_id) below instead."""
        db = SessionLocal()
        try:
            return [p for rec in db.query(CaseRecord).all() if (p := _from_json(rec.payload))]
        finally:
            db.close()

    def list_cases(self, tenant_id: str) -> list[dict]:
        """Return every persisted case payload belonging to one tenant.
        Phase 2 object-level authorization: this is what makes GET /cases
        (app/api/cases.py) show only the requesting investigator's own
        tenant's cases, not every tenant's — tenant_id is required (no
        default) so a call site can't accidentally fall back to
        "everyone's data" by omission."""
        db = SessionLocal()
        try:
            return [
                p for rec in db.query(CaseRecord).filter_by(tenant_id=tenant_id).all()
                if (p := _from_json(rec.payload))
            ]
        finally:
            db.close()

    # ── Users (Phase 2) ─────────────────────────────────────────────────

    def get_user_by_username(self, username: str) -> dict | None:
        """Return {"username", "tenant_id", "password_hash", "role"} for a
        login account, or None. Used by app/core/users.py::authenticate()
        on every login attempt."""
        if not username:
            return None
        db = SessionLocal()
        try:
            rec = db.query(UserRecord).filter_by(username=username).first()
            if not rec:
                return None
            return {
                "username": rec.username,
                "tenant_id": rec.tenant_id,
                "password_hash": rec.password_hash,
                "role": rec.role,
            }
        finally:
            db.close()

    def create_user(self, username: str, password_hash: str, role: str, tenant_id: str = DEFAULT_TENANT_ID) -> bool:
        """Insert a new login account. Idempotent by design, not just by
        accident: returns False (logged, not raised) if the username
        already exists, rather than erroring — this is what lets
        seed_default_users() below call it unconditionally on every boot
        without needing its own "does this already exist" check first."""
        db = SessionLocal()
        try:
            if db.query(UserRecord).filter_by(username=username).first():
                return False
            db.add(UserRecord(username=username, tenant_id=tenant_id, password_hash=password_hash, role=role))
            db.commit()
            return True
        except IntegrityError:
            # Race: two processes (e.g. two API replicas booting
            # simultaneously) both saw "doesn't exist" and both tried to
            # insert it. Whichever loses the unique-constraint race just
            # doesn't create a duplicate — not an error, same idempotent
            # intent as the check above, just covering the TOCTOU gap.
            db.rollback()
            return False
        except Exception as e:
            db.rollback()
            logger.error("create_user failed for %s: %s", username, e)
            return False
        finally:
            db.close()

    def touch_last_login(self, username: str) -> None:
        """Best-effort — a failure here must never block a successful
        login."""
        db = SessionLocal()
        try:
            rec = db.query(UserRecord).filter_by(username=username).first()
            if rec:
                rec.last_login = _dt.now(_tz.utc)
                db.commit()
        except Exception as e:
            db.rollback()
            logger.warning("touch_last_login failed for %s: %s", username, e)
        finally:
            db.close()

    def seed_default_users(self) -> None:
        """Bootstrap the admin/viewer accounts from ADMIN_USERNAME/PASSWORD
        + VIEWER_USERNAME/PASSWORD env vars (app.core.users' existing
        fail-closed checks already guarantee these are set) — called once
        from main.py's lifespan, right after run_migrations(). A no-op
        past the first boot: create_user() above is idempotent, so this
        only ever creates the two rows once and does nothing on every
        subsequent restart, deliberately NOT re-hashing/overwriting on
        every boot — the DB row, not the env var, is the durable source
        of truth for a login account's password from here on."""
        # Deferred import: app.core.users imports THIS module indirectly
        # via app.core.security only, no cycle today, but kept deferred
        # to match this file's existing lazy-import convention for
        # cross-layer imports (see the module-level comment near the top
        # of this file re: the orchestrator import).
        from app.core.security import hash_password
        from app.core.users import ADMIN_USERNAME, ADMIN_PASSWORD, VIEWER_USERNAME, VIEWER_PASSWORD

        if self.create_user(ADMIN_USERNAME, hash_password(ADMIN_PASSWORD), "admin"):
            logger.info("Seeded default admin user %s", ADMIN_USERNAME)
        if self.create_user(VIEWER_USERNAME, hash_password(VIEWER_PASSWORD), "viewer"):
            logger.info("Seeded default viewer user %s", VIEWER_USERNAME)

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
            logger.error("save_action failed: %s", e)
        finally:
            db.close()

    # ── Startup restore ──────────────────────────────────────────────────

    def load_all(self, store: dict) -> None:
        """On startup: read every persisted transaction/case from Postgres
        and populate the in-memory data_store's cases/transactions, and
        Redis's velocity_cache/accounts (see app/services/orchestrator.py)
        — same restore semantics as the old persistence.load_all_into_store(),
        just reading from the repository's backing DB and replaying through
        the exact same orchestrator.record_velocity()/save_account() helpers
        live traffic uses, instead of a second, separately-maintained
        rebuild implementation.

        Transaction and case restoration are independent steps, and each
        record within them is independently guarded (see
        _restore_transactions/_restore_cases below): a Redis outage (or
        one corrupt record) must not silently abort restoration of
        everything else — a startup-time Redis hiccup used to leave
        data_store completely empty (0 transactions AND 0 cases restored,
        logged only as a single generic "load_all failed") because the
        whole method shared one try/except around both loops. Now
        record_velocity()/save_account() also degrade gracefully on their
        own (see orchestrator.py) — this per-record isolation is a second,
        independent layer of defense, not a substitute for that fix.

        Note: app.core.data_store["graphs"] is NOT restored here — graph
        state (including frozen/withdrawn node status) isn't persisted
        anywhere today. That's a pre-existing gap (real graph persistence
        is Phase 5's job), not something this repository introduces."""
        db = SessionLocal()
        try:
            tx_count = self._restore_transactions(db, store)
            case_count = self._restore_cases(db, store)
            logger.info("Restored %s transactions, %s cases from DB [OK]", tx_count, case_count)
        except Exception as e:
            # Belt-and-suspenders: _restore_transactions/_restore_cases
            # already guard every record individually, so reaching here
            # means something failed outside either loop (e.g. the query
            # itself). Still don't let it take the other one down with it.
            logger.error("load_all failed: %s", e)
        finally:
            db.close()

    def _restore_transactions(self, db, store: dict) -> int:
        """Restore every persisted transaction into store["transactions"]
        and replay it through orchestrator's Redis-backed velocity/account
        helpers. Each record is isolated in its own try/except: one bad
        payload or one Redis error must not stop the rest of the
        transactions (or the separate case restore that follows) from
        loading — record_velocity()/save_account() already degrade
        gracefully on a Redis failure rather than raising (see
        orchestrator.py), so this per-record guard mainly protects against
        an unexpected/future failure mode, not the common one."""
        # Deferred import — see the module-level comment near the top of
        # this file explaining why this can't be a top-level import.
        from app.services import orchestrator

        tx_count = 0
        for rec in db.query(TransactionRecord).all():
            try:
                payload = _from_json(rec.payload)
                if not payload:
                    continue
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

                    velocity = orchestrator.record_velocity(sender_id, receiver, amount, tx_id, timestamp=ts)
                    orchestrator.save_account(sender_id, amount, velocity)
            except Exception as e:
                logger.warning("Failed to restore transaction %s: %s", getattr(rec, "tx_id", "?"), e)
                continue
        return tx_count

    def _restore_cases(self, db, store: dict) -> int:
        """Restore every persisted case into store["cases"], independently
        of transaction restoration above — runs (and completes) even if
        _restore_transactions failed entirely, and one bad case record
        doesn't stop the rest."""
        case_count = 0
        for rec in db.query(CaseRecord).all():
            try:
                payload = _from_json(rec.payload)
                if not payload:
                    continue
                case_id = payload.get("case_id") or rec.case_id
                store.setdefault("cases", {})[case_id] = payload
                case_count += 1
            except Exception as e:
                logger.warning("Failed to restore case %s: %s", getattr(rec, "case_id", "?"), e)
                continue
        return case_count


# Single shared instance — see the class docstring for why one is enough.
repository = Repository()
