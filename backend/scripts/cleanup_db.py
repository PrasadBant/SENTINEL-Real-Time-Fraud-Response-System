"""
SENTINEL — Database Cleanup
==============================
One-off maintenance script for backend/sentinel.db. Removes rows that
should never have ended up in the persisted database:

  1. Copilot conversations (and their messages) created by the pytest
     suite's rate-limit fixtures (username LIKE 'rate-limit-%') — see
     tests/conftest.py, which historically ran the test suite against
     the real sentinel.db, so every local `pytest` run accumulated more
     of these permanently.

  2. Orphaned `actions` rows whose case_id doesn't refer to any row in
     `cases` (excluding the "GLOBAL" sentinel value used for
     case-independent actions like PROACTIVE_MONITOR). This is a
     symptom of the best-effort, non-durable background write queue in
     app/core/persistence.py: if the process restarts (or a case-save
     silently fails) while an action referencing that case has already
     been written, the case row never lands but the action does.

Defaults to a dry run that only prints what it would delete. Pass
--apply to actually commit the deletes.

Usage:
    python scripts/cleanup_db.py            # dry run
    python scripts/cleanup_db.py --apply     # actually delete
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.core.db_models import ActionRecord, CaseRecord, ConversationRecord

TEST_USERNAME_PATTERN = "rate-limit-%"


def find_test_conversations(db):
    return (
        db.query(ConversationRecord)
        .filter(ConversationRecord.username.like(TEST_USERNAME_PATTERN))
        .all()
    )


def find_orphaned_actions(db):
    case_ids = {c.case_id for c in db.query(CaseRecord.case_id).all()}
    return [
        a
        for a in db.query(ActionRecord).all()
        if a.case_id and a.case_id != "GLOBAL" and a.case_id not in case_ids
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Actually delete rows (default: dry run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        convs = find_test_conversations(db)
        msg_count = sum(len(c.messages) for c in convs)
        orphan_actions = find_orphaned_actions(db)

        print(f"Test conversations (username LIKE '{TEST_USERNAME_PATTERN}'): "
              f"{len(convs)} conversations, {msg_count} messages")
        for c in convs[:5]:
            print(f"  - {c.conversation_id} ({c.username}, {len(c.messages)} msgs)")
        if len(convs) > 5:
            print(f"  ... and {len(convs) - 5} more")

        print(f"\nOrphaned actions (case_id not in cases, excl. GLOBAL): {len(orphan_actions)}")
        for a in orphan_actions:
            print(f"  - {a.action_id} -> case_id={a.case_id} ({a.action_type}, {a.status})")

        if not convs and not orphan_actions:
            print("\nNothing to clean up.")
            return

        if not args.apply:
            print("\nDry run — no changes made. Re-run with --apply to delete.")
            return

        for c in convs:
            db.delete(c)  # cascades to copilot_messages via the ORM relationship
        for a in orphan_actions:
            db.delete(a)
        db.commit()
        print(f"\nDeleted {len(convs)} conversations ({msg_count} messages) "
              f"and {len(orphan_actions)} orphaned actions.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
