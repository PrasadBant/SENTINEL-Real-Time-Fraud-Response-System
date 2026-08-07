"""
SENTINEL — Copilot Conversation History
===========================================
Persists chat turns to SQLite so an investigator's copilot conversations
survive a page reload/backend restart, scoped per logged-in user (via
the JWT 'sub' claim / username) so one investigator never sees or
deletes another's history.

Unlike app/core/persistence.py's write-through cache (data_store is the
source of truth, SQLite is a best-effort mirror written on a background
thread), conversation history has no in-memory equivalent to mirror —
the DB *is* the source of truth here. Writes are synchronous rather than
queued: a chat reply is low-frequency compared to transaction ingestion,
and the history endpoints need read-your-own-write consistency (a GET
right after a POST must see the message that was just saved).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.core.db_models import ConversationRecord, CopilotMessageRecord


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _owned_conversation(db, conversation_id: str, username: str) -> ConversationRecord | None:
    """Fetch a conversation only if it exists AND belongs to username —
    the single ownership check every read/write/delete path routes
    through, so an ID belonging to another user is treated exactly like
    an unknown ID (never leaks existence, never gets written into)."""
    conv = db.query(ConversationRecord).filter_by(conversation_id=conversation_id).first()
    if conv is None or conv.username != username:
        return None
    return conv


def create_conversation(username: str) -> str:
    conversation_id = _new_id("CONV")
    db = SessionLocal()
    try:
        db.add(ConversationRecord(conversation_id=conversation_id, username=username))
        db.commit()
    finally:
        db.close()
    return conversation_id


def resolve_conversation(username: str, conversation_id: str | None) -> str:
    """Returns a conversation_id owned by username: the given one if it's
    valid and owned by them, otherwise a freshly created one. Covers three
    cases the same way — no ID given, an unknown ID, or an ID belonging to
    a different user — so a chat request never silently appends to
    someone else's thread."""
    if conversation_id:
        db = SessionLocal()
        try:
            if _owned_conversation(db, conversation_id, username) is not None:
                return conversation_id
        finally:
            db.close()
    return create_conversation(username)


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    action: dict | None = None,
    provider: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            CopilotMessageRecord(
                message_id=_new_id("MSG"),
                conversation_id=conversation_id,
                role=role,
                content=content,
                action_json=json.dumps(action) if action else None,
                provider=provider,
            )
        )
        conv = db.query(ConversationRecord).filter_by(conversation_id=conversation_id).first()
        if conv is not None:
            conv.updated_at = _now()
        db.commit()
    finally:
        db.close()


def list_conversations(username: str, limit: int = 20) -> list[dict]:
    db = SessionLocal()
    try:
        convs = (
            db.query(ConversationRecord)
            .filter_by(username=username)
            .order_by(ConversationRecord.updated_at.desc())
            .limit(limit)
            .all()
        )
        result = []
        for c in convs:
            last = c.messages[-1] if c.messages else None
            result.append(
                {
                    "conversation_id": c.conversation_id,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                    "message_count": len(c.messages),
                    "preview": last.content[:120] if last else "",
                }
            )
        return result
    finally:
        db.close()


def get_messages(username: str, conversation_id: str) -> list[dict] | None:
    """Returns the conversation's messages, or None if it doesn't exist or
    isn't owned by username (caller turns None into a 404)."""
    db = SessionLocal()
    try:
        conv = _owned_conversation(db, conversation_id, username)
        if conv is None:
            return None
        return [
            {
                "message_id": m.message_id,
                "role": m.role,
                "content": m.content,
                "action": json.loads(m.action_json) if m.action_json else None,
                "provider": m.provider,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in conv.messages
        ]
    finally:
        db.close()


def delete_conversation(username: str, conversation_id: str) -> bool:
    db = SessionLocal()
    try:
        conv = _owned_conversation(db, conversation_id, username)
        if conv is None:
            return False
        db.delete(conv)
        db.commit()
        return True
    finally:
        db.close()


def delete_all_conversations(username: str) -> int:
    db = SessionLocal()
    try:
        convs = db.query(ConversationRecord).filter_by(username=username).all()
        count = len(convs)
        for c in convs:
            db.delete(c)
        db.commit()
        return count
    finally:
        db.close()
