"""
SENTINEL — Copilot Structured Intents
=========================================
Deterministic, data-exact answers for questions the LLM shouldn't be
trusted to compute or transcribe from context on its own — lookups,
counts, and sums are done here in Python against data_store directly,
not asked of an LLM that could round a number wrong or hallucinate a
transaction ID. match_structured_intent() returns a formatted Markdown
reply for anything it recognizes, or None so copilot.py falls through
to the freeform LLM path (context_builder.build_for_request()).

Domain note: SENTINEL is bank-transfer/mule-chain fraud (sender/
receiver accounts, channels, hop chains) — there is no merchant/
product/card-fraud data model here, so intents are scoped to what the
system actually tracks (see the "Adapt to SENTINEL's real domain"
decision this phase was built under).

This module intentionally does NOT handle the admin-gated freeze/close
action intents — those stay in copilot.py, unchanged, with their own
role check. Everything here is read-only.
"""

from __future__ import annotations

import re

from app.core.constants import CaseStatus
from app.core.data_store import data_store
from app.services.copilot.context_builder import case_context, dashboard_context, transaction_context

_TX_ID_RE = re.compile(r"\bTX-[A-Za-z0-9]{3,}\b", re.IGNORECASE)
_CASE_ID_RE = re.compile(r"\bCASE-[A-Za-z0-9]{3,}\b", re.IGNORECASE)
_ACCOUNT_ID_RE = re.compile(r"\bACC-[A-Za-z0-9-]{3,}\b", re.IGNORECASE)
_AMOUNT_RE = re.compile(
    r"(?:over|above|greater than|more than|at least)\s*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)",
    re.IGNORECASE,
)
_CHANNELS = ("UPI", "IMPS", "NEFT", "CARD")

_HIGH_RISK_LIST_PHRASES = ("high-risk cases", "high risk cases", "open cases", "open high-risk")
_NEXT_STEP_PHRASES = (
    "what should i investigate",
    "what to investigate",
    "investigate next",
    "next case",
    "priority case",
    "what next",
)
_DASHBOARD_PHRASES = (
    "total exposure",
    "average risk score",
    "average fraud score",
    "how much fraud",
    "total fraud",
    "how many cases",
    "how many transactions",
    "recoverable amount",
    "estimated loss",
    "dashboard stat",
    "channel distribution",
    "top risk factor",
)
_SEARCH_VERBS = ("show", "list", "find", "search", "filter", "which transactions", "all transactions")
_SENDER_RISK_PHRASES = ("highest risk sender", "riskiest sender", "highest-risk sender")
_RECEIVER_RISK_PHRASES = ("highest risk receiver", "riskiest receiver", "highest-risk receiver")


def _find_tx_id(message: str) -> str | None:
    m = _TX_ID_RE.search(message)
    return m.group(0).upper() if m else None


def _find_case_id(message: str) -> str | None:
    m = _CASE_ID_RE.search(message)
    return m.group(0).upper() if m else None


def _find_account_id(message: str) -> str | None:
    m = _ACCOUNT_ID_RE.search(message)
    return m.group(0).upper() if m else None


def _explain_transaction(tx_id: str) -> str:
    context = transaction_context(tx_id)
    if context.startswith("No transaction"):
        return context
    return f"**Transaction Analysis — `{tx_id}`**\n\n{context}"


def _summarize_case(case_id: str) -> str:
    context = case_context(case_id)
    if context.startswith("No case"):
        return context
    return f"**Case Summary — `{case_id}`**\n\n{context}"


def _list_high_risk_cases() -> str:
    cases = [c for c in data_store.get("cases", {}).values() if c.get("status") == CaseStatus.HIGH_RISK]
    if not cases:
        return "There are currently no open HIGH_RISK cases."
    cases.sort(key=lambda c: c.get("urgency_score", 0), reverse=True)
    lines = [f"**Open High-Risk Cases ({len(cases)}):**\n"]
    for c in cases[:10]:
        lines.append(
            f"- `{c['case_id']}`: risk {c.get('risk_level', 0)}%, urgency {c.get('urgency_score', 0):.1f}, "
            f"Rs.{c.get('total_fraud_amount', 0):,.2f} at stake, "
            f"golden window {c.get('golden_window_minutes', 0)}min"
        )
    if len(cases) > 10:
        lines.append(f"- ...and {len(cases) - 10} more.")
    return "\n".join(lines)


def _recommend_next() -> str:
    active = [
        c
        for c in data_store.get("cases", {}).values()
        if c.get("status") in (CaseStatus.NEW, CaseStatus.HIGH_RISK)
    ]
    if not active:
        return "No active cases need investigation right now — the queue is clear."
    top = max(active, key=lambda c: c.get("urgency_score", 0))
    return (
        f"**Recommended next case: `{top['case_id']}`**\n\n"
        f"This case has the highest urgency score ({top.get('urgency_score', 0):.1f}) in the queue — "
        f"risk {top.get('risk_level', 0)}%, Rs.{top.get('total_fraud_amount', 0):,.2f} at stake, "
        f"~{top.get('golden_window_minutes', 0)} minutes left in the golden window before "
        "mule-chain withdrawal risk peaks.\n\n"
        "**Suggested steps:**\n"
        "1. Review the mule chain and identify the current terminal (receiving) account.\n"
        "2. Freeze the destination account if risk is HIGH_RISK and evidence is strong.\n"
        "3. Alert the receiving bank if the account is external.\n"
        "4. Escalate to a human analyst if cross-border or ambiguous."
    )


def _dashboard_stats_answer() -> str:
    return f"**Current Dashboard Statistics:**\n\n{dashboard_context()}"


def _highest_risk_account(role: str) -> str:
    """role: 'sender_account' or 'receiver_account'."""
    txs = list(data_store.get("transactions", {}).values())
    agg: dict[str, dict] = {}
    for t in txs:
        acc = t.get(role)
        if not acc:
            continue
        entry = agg.setdefault(acc, {"total_amount": 0.0, "max_risk": 0, "count": 0})
        entry["total_amount"] += t.get("amount", 0.0)
        entry["max_risk"] = max(entry["max_risk"], t.get("risk_score", 0))
        entry["count"] += 1
    if not agg:
        return "No transactions recorded yet."
    top_acc, stats = max(agg.items(), key=lambda kv: kv[1]["max_risk"])
    label = "sender" if role == "sender_account" else "receiver"
    return (
        f"**Highest-risk {label} account: `{top_acc}`**\n\n"
        f"- Peak risk score seen: {stats['max_risk']}%\n"
        f"- Transactions involving this account as {label}: {stats['count']}\n"
        f"- Total amount moved: Rs.{stats['total_amount']:,.2f}"
    )


def _search_transactions(message: str) -> str | None:
    msg_lower = message.lower()
    if not any(v in msg_lower for v in _SEARCH_VERBS):
        return None  # not phrased as a search — let the LLM path handle it

    channel = next((c for c in _CHANNELS if c.lower() in msg_lower), None)
    account = _find_account_id(message)
    amount_match = _AMOUNT_RE.search(message)
    min_amount = float(amount_match.group(1).replace(",", "")) if amount_match else None

    if not (channel or account or min_amount):
        return None  # a search verb alone isn't enough — no actual filter given

    txs = list(data_store.get("transactions", {}).values())
    if channel:
        txs = [t for t in txs if t.get("channel") == channel]
    if account:
        txs = [t for t in txs if t.get("sender_account") == account or t.get("receiver_account") == account]
    if min_amount is not None:
        txs = [t for t in txs if t.get("amount", 0) >= min_amount]

    filters_desc = ", ".join(
        f
        for f in [
            f"channel={channel}" if channel else None,
            f"account={account}" if account else None,
            f"amount>=Rs.{min_amount:,.0f}" if min_amount is not None else None,
        ]
        if f
    )

    if not txs:
        return f"No transactions match that search ({filters_desc})."

    txs.sort(key=lambda t: t.get("risk_score", 0), reverse=True)
    lines = [f"**Transaction Search ({filters_desc}) — {len(txs)} match(es):**\n"]
    for t in txs[:10]:
        lines.append(
            f"- `{t.get('tx_id')}`: Rs.{t.get('amount', 0):,.2f} via {t.get('channel')} "
            f"from `{t.get('sender_account')}` to `{t.get('receiver_account')}` "
            f"- risk {t.get('risk_score', 0)}%"
        )
    if len(txs) > 10:
        lines.append(f"- ...and {len(txs) - 10} more.")
    return "\n".join(lines)


def match_structured_intent(message: str) -> str | None:
    """
    Returns a deterministic Markdown reply for a recognized structured
    intent, or None if the message doesn't match anything here (in which
    case copilot.py falls through to the freeform LLM path).

    Order matters: specific ID lookups first (most unambiguous), then
    named aggregate questions, then the search verb (most permissive,
    checked last so it doesn't shadow the others).
    """
    msg_lower = message.lower()

    tx_id = _find_tx_id(message)
    if tx_id:
        return _explain_transaction(tx_id)

    case_id = _find_case_id(message)
    if case_id:
        return _summarize_case(case_id)

    if any(p in msg_lower for p in _SENDER_RISK_PHRASES):
        return _highest_risk_account("sender_account")

    if any(p in msg_lower for p in _RECEIVER_RISK_PHRASES):
        return _highest_risk_account("receiver_account")

    if any(p in msg_lower for p in _HIGH_RISK_LIST_PHRASES):
        return _list_high_risk_cases()

    if any(p in msg_lower for p in _NEXT_STEP_PHRASES):
        return _recommend_next()

    if any(p in msg_lower for p in _DASHBOARD_PHRASES):
        return _dashboard_stats_answer()

    return _search_transactions(message)
