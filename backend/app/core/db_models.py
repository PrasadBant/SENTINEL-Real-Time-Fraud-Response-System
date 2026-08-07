"""
SENTINEL — SQLAlchemy ORM Models
==================================
Core tables:
  - transactions  (one row per processed transaction)
  - cases         (one row per fraud case)
  - actions       (one row per investigative action taken)

JSON payload columns store the full in-memory dict so that
load_all_into_store() can faithfully restore state after a restart.

Copilot history tables (own source of truth — see
app/services/copilot/history.py, not the write-through data_store
pattern above):
  - copilot_conversations  (one row per chat thread, owned by a user)
  - copilot_messages       (one row per turn in a conversation)
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Text, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class TransactionRecord(Base):
    __tablename__ = "transactions"

    tx_id        = Column(String, primary_key=True, index=True)
    case_id      = Column(String, nullable=True, index=True)
    sender       = Column(String, nullable=True)
    receiver     = Column(String, nullable=True)
    amount       = Column(Float, default=0.0)
    risk_score   = Column(Float, default=0.0)
    channel      = Column(String, nullable=True)
    threshold    = Column(String, nullable=True)
    timestamp    = Column(String, nullable=True)
    created_at   = Column(DateTime, default=_now)
    # Full serialized dict (JSON string) for complete restore
    payload      = Column(Text, nullable=True)

    def __repr__(self):
        return f"<TX {self.tx_id} score={self.risk_score}>"


class CaseRecord(Base):
    __tablename__ = "cases"

    case_id              = Column(String, primary_key=True, index=True)
    status               = Column(String, default="NEW")
    risk_level           = Column(Float, default=0.0)
    total_fraud_amount   = Column(Float, default=0.0)
    recoverable_amount   = Column(Float, default=0.0)
    recovery_pct         = Column(Float, default=0.0)
    golden_window_minutes= Column(Integer, default=20)
    origin_account       = Column(String, nullable=True)
    created_at           = Column(DateTime, default=_now)
    updated_at           = Column(DateTime, default=_now, onupdate=_now)
    # Full serialized dict (JSON string) for complete restore
    payload              = Column(Text, nullable=True)

    actions              = relationship("ActionRecord", back_populates="case",
                                        cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Case {self.case_id} status={self.status}>"


class ActionRecord(Base):
    __tablename__ = "actions"

    action_id   = Column(String, primary_key=True, index=True)
    case_id     = Column(String, ForeignKey("cases.case_id"), nullable=True, index=True)
    action_type = Column(String, nullable=True)
    target_id   = Column(String, nullable=True)
    status      = Column(String, default="ACK")
    reason      = Column(String, nullable=True)
    timestamp   = Column(String, nullable=True)
    created_at  = Column(DateTime, default=_now)
    # Full serialized dict (JSON string)
    payload     = Column(Text, nullable=True)

    case        = relationship("CaseRecord", back_populates="actions")

    def __repr__(self):
        return f"<Action {self.action_id} type={self.action_type}>"


class ConversationRecord(Base):
    __tablename__ = "copilot_conversations"

    conversation_id = Column(String, primary_key=True, index=True)
    # JWT 'sub' claim (see app.core.deps.get_current_user) — scopes history
    # per logged-in investigator so one user never sees another's chats.
    username         = Column(String, nullable=False, index=True)
    created_at       = Column(DateTime, default=_now)
    updated_at       = Column(DateTime, default=_now, onupdate=_now)

    messages = relationship(
        "CopilotMessageRecord",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="CopilotMessageRecord.created_at",
    )

    def __repr__(self):
        return f"<Conversation {self.conversation_id} user={self.username}>"


class CopilotMessageRecord(Base):
    __tablename__ = "copilot_messages"

    message_id      = Column(String, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("copilot_conversations.conversation_id"), nullable=False, index=True)
    role             = Column(String, nullable=False)  # "user" | "assistant"
    content          = Column(Text, nullable=False)
    # Serialized action_taken dict (e.g. FREEZE_ACCOUNTS), if this turn
    # executed one — mirrors the "action" field in the /api/copilot/chat
    # response.
    action_json      = Column(Text, nullable=True)
    # Which tier answered: "action" (freeze/close), "structured" (a
    # deterministic intent from app.services.copilot.intents), an
    # AIProvider.name (e.g. "anthropic", "mock"), or "offline_fallback".
    # Assistant messages only.
    provider         = Column(String, nullable=True)
    created_at       = Column(DateTime, default=_now)

    conversation = relationship("ConversationRecord", back_populates="messages")

    def __repr__(self):
        return f"<Message {self.message_id} role={self.role}>"
