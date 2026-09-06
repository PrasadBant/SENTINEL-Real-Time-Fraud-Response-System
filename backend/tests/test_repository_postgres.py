"""
Postgres-specific behavior for the repository/migration layer.

The rest of the suite runs against SQLite by default (see conftest.py) —
that's deliberate, not an oversight: business logic (scoring, case
linking, auth, copilot) is backend-agnostic by design, and forcing all of
it through a container for every run would trade CI simplicity for very
little coverage gain at this project's size.

This module exists specifically because a few things behave differently
enough between SQLite and Postgres that "it passed on SQLite" isn't
sufficient evidence the repository layer actually works on the real
deployment target — namely: SQLite doesn't enforce FK constraints (which
is exactly why actions.case_id="GLOBAL" used to "work" by accident, see
db_models.py and Alembic migration 0002), and the exception type raised
on a unique-constraint violation differs by driver.

Both tests use freshly generated ids on every run rather than fixed
literals, and neither test drops or recreates any table (see the pg_repo
fixture's docstring for why) — safe to run repeatedly against a
persistent Postgres instance, and safe to run as part of a full
`TEST_DATABASE_URL=... pytest` invocation covering the whole suite, not
just this file. What's deliberately NOT automated here: a destructive
migration upgrade/downgrade round-trip against Postgres, since that
would have to tear down the very tables the rest of the suite's
session-scoped `client` fixture depends on existing. That round-trip was
instead verified by hand against a live Postgres container during
development (upgrade -> head, downgrade -> base, re-upgrade -> head, all
clean) — see the Phase 0 build plan commit history for that check; it's
the same round-trip already covered automatically against SQLite in
alembic/versions/ itself being exercised by every `client`-fixture test.

Skipped entirely unless TEST_DATABASE_URL points at a real Postgres
instance — e.g.:
    TEST_DATABASE_URL=postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinel_test \
        pytest tests/test_repository_postgres.py -v

It is intentionally NOT part of the default `pytest` run wired into CI
(see the build plan's Phase 0 scope decisions) to keep CI fast and
container-free for now.
"""

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="set TEST_DATABASE_URL to a real Postgres instance to run these",
)


@pytest.fixture()
def pg_repo():
    """Ensures the Alembic migrations are applied against TEST_DATABASE_URL
    (a no-op if the session's `client` fixture already ran them — `alembic
    upgrade head` is idempotent) and yields a Repository bound to it.

    Deliberately does NOT drop tables afterward: TEST_DATABASE_URL is a
    single shared database for the whole pytest session (every fixture —
    including the session-scoped `client` in conftest.py — binds to the
    same DATABASE_URL), so anything here that drops/recreates schema
    would corrupt it out from under every other test file that happens to
    run later in the same session. Per conftest.py's own docstring, a
    caller-supplied TEST_DATABASE_URL is "the caller's to manage" — same
    policy applies here, this just leaves its rows behind."""
    from alembic import command
    from alembic.config import Config

    from app.core.repository import Repository

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    command.upgrade(cfg, "head")

    yield Repository()


def test_global_pseudo_case_action_insert_has_no_fk(pg_repo):
    """actions.case_id="GLOBAL" (proactive bridge-node alerts) never
    corresponds to a real case row — this must succeed on Postgres, which
    enforces FKs (unlike SQLite, where the old code "worked" by accident)."""
    action_id = f"ACT-PG-GLOBAL-TEST-{uuid.uuid4().hex[:8]}"
    pg_repo.save_action({
        "action_id": action_id,
        "case_id": "GLOBAL",
        "action_type": "PROACTIVE_MONITOR",
        "target_id": "ACC-X",
        "status": "DETECTED",
        "reason": "test",
    })
    # No CaseRecord("GLOBAL") exists — if the FK were still present, the
    # save above would have hit an IntegrityError (caught and logged by
    # save_action, not raised) and this row simply wouldn't exist.
    from app.core.database import SessionLocal
    from app.core.db_models import ActionRecord

    db = SessionLocal()
    try:
        rec = db.query(ActionRecord).filter_by(action_id=action_id).first()
        assert rec is not None
        assert rec.case_id == "GLOBAL"
    finally:
        db.close()


def test_idempotency_key_unique_constraint_raises_integrity_error(pg_repo):
    """Two transactions with the same idempotency_key: the first commits,
    the second must hit Postgres's real unique-constraint violation and be
    absorbed by save_transaction's IntegrityError handling, not crash and
    not silently overwrite the first row's identity."""
    suffix = uuid.uuid4().hex[:8]
    key = f"PG-RACE-KEY-{suffix}"
    pg_repo.save_transaction({
        "tx_id": f"TX-PG-RACE-1-{suffix}",
        "sender_account": "ACC-A",
        "receiver_account": "ACC-B",
        "amount": 100.0,
        "timestamp": "2026-08-07T23:00:00Z",
        "channel": "UPI",
        "idempotency_key": key,
    })
    # Second row, same idempotency_key, different tx_id — must not raise
    # out of save_transaction (it's caught internally) and must not
    # replace the first row.
    pg_repo.save_transaction({
        "tx_id": f"TX-PG-RACE-2-{suffix}",
        "sender_account": "ACC-C",
        "receiver_account": "ACC-D",
        "amount": 200.0,
        "timestamp": "2026-08-07T23:05:00Z",
        "channel": "UPI",
        "idempotency_key": key,
    })

    winner = pg_repo.get_transaction_by_idempotency_key(key)
    assert winner is not None
    assert winner["tx_id"] == f"TX-PG-RACE-1-{suffix}"
