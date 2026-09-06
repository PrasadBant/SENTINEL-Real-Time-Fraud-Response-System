"""
SENTINEL — Copilot Context Builder (RAG)
============================================
Turns app.core.data_store's live in-memory state into Markdown context
strings for the AI copilot. This is SENTINEL's actual retrieval layer:
every fact the LLM sees about cases, transactions, and dashboard
aggregates comes from here, straight out of the same data_store the
rest of the app reads/writes — never generic internet knowledge, and
never invented.

dashboard_context() deliberately re-implements the aggregate formulas
in frontend/src/pages/Dashboard.jsx (total exposure, recoverable,
channel distribution, top risk factors) server-side, so the copilot's
numbers always match what the investigator sees on screen instead of
drifting from a second, unrelated implementation.

Phase 2 hostile-review fix (CRITICAL): every function in this module
(and in app.services.copilot.intents, which shares the same
cases_for_tenant()/transactions_for_tenant() accessors below rather than
reading data_store directly) now takes tenant_id and returns only that
tenant's own cases/transactions. Previously this entire module read
data_store unfiltered — any authenticated user (even a viewer) could
have the copilot summarize, list, search, or aggregate ANY tenant's
case/transaction data, live-verified via "explain case <id>", "show
high-risk cases", "total fraud exposure", and freeform chat with no
case selected. cases_for_tenant()/transactions_for_tenant() are the
ONLY sanctioned way to read data_store["cases"]/["transactions"]
anywhere in the copilot subsystem now — every other function in both
modules goes through them, so there is exactly one place a future
change could reintroduce this bug, not a dozen scattered direct reads.
"""

from __future__ import annotations

from app.core.constants import CaseStatus, DEFAULT_TENANT_ID
from app.core.data_store import data_store
from app.services.copilot.knowledge import patterns_for_signals

# Hard caps on how much raw data gets stuffed into a single context
# string — this is a chat copilot, not a data export; keep prompts (and
# therefore latency/cost) bounded even for a case with a long chain.
MAX_TRANSACTIONS_IN_CONTEXT = 10
MAX_ACTIONS_IN_CONTEXT = 5
MAX_HIGH_RISK_CASES_IN_CONTEXT = 5


def cases_for_tenant(tenant_id: str) -> dict:
    """The single choke point for reading data_store["cases"] anywhere in
    the copilot subsystem. `.get("tenant_id", DEFAULT_TENANT_ID)` matches
    the same fallback app/api/cases.py's local-cache path uses: real
    ingested cases never carry an explicit "tenant_id" key today
    (ingestion is single-tenant — see app/api/transactions.py), so they
    correctly default to DEFAULT_TENANT_ID rather than being invisible to
    the one tenant that actually owns them."""
    return {
        cid: c for cid, c in data_store.get("cases", {}).items()
        if c.get("tenant_id", DEFAULT_TENANT_ID) == tenant_id
    }


def transactions_for_tenant(tenant_id: str) -> dict:
    """Same as cases_for_tenant, for data_store["transactions"]."""
    return {
        tid: t for tid, t in data_store.get("transactions", {}).items()
        if t.get("tenant_id", DEFAULT_TENANT_ID) == tenant_id
    }


def case_context(case_id: str, tenant_id: str) -> str:
    """Full Markdown context for one case: status, risk, mule chain,
    transactions, and actions already taken. Used both as LLM context and
    as the basis for the deterministic 'summarize case' structured intent.
    Returns the same "not found" message for a case that genuinely
    doesn't exist and one that exists but belongs to a different tenant —
    existence isn't leaked, matching app.core.repository.get_case_for_tenant's
    behavior."""
    case = cases_for_tenant(tenant_id).get(case_id)
    if not case:
        return f"No case found with ID `{case_id}`."

    txs_by_id = transactions_for_tenant(tenant_id)
    tx_ids = case.get("transactions", [])
    txs = [txs_by_id[t] for t in tx_ids if t in txs_by_id]

    lines = [
        f"**Case ID:** {case['case_id']}",
        f"**Status:** {case.get('status', 'UNKNOWN')}",
        f"**Risk Level:** {case.get('risk_level', 0)}%",
        f"**Urgency Score:** {case.get('urgency_score', 0):.1f}",
        f"**Golden Window:** {case.get('golden_window_minutes', 0)} minutes "
        "(time before mule-chain funds are typically withdrawn)",
        f"**Total Fraud Amount:** Rs.{case.get('total_fraud_amount', 0):,.2f}",
        f"**Recoverable Amount:** Rs.{case.get('recoverable_amount', 0):,.2f}",
        f"**Origin Account:** {case.get('origin_account', 'N/A')}",
        f"**Mule Chain ({len(case.get('chain', []))} accounts):** "
        + " -> ".join(case.get("chain", [])),
        f"**Transactions Involved:** {len(txs)}",
    ]

    if txs:
        lines.append("\n**Transaction Details:**")
        for tx in txs[:MAX_TRANSACTIONS_IN_CONTEXT]:
            factors = ", ".join(
                f["name"] for f in tx.get("risk_factors", []) if f.get("contribution", 0) > 0
            )
            lines.append(
                f"- `{tx.get('tx_id')}`: Rs.{tx.get('amount', 0):,.2f} via {tx.get('channel', 'N/A')} "
                f"from `{tx.get('sender_account')}` to `{tx.get('receiver_account')}` "
                f"- risk {tx.get('risk_score', 0)}% ({tx.get('threshold', 'LOW')})"
                + (f" - flags: {factors}" if factors else "")
            )
        if len(txs) > MAX_TRANSACTIONS_IN_CONTEXT:
            lines.append(f"- ...and {len(txs) - MAX_TRANSACTIONS_IN_CONTEXT} more.")

        fired_signals = {
            f["name"] for tx in txs for f in tx.get("risk_factors", []) if f.get("contribution", 0) > 0
        }
        matched_patterns = patterns_for_signals(fired_signals)
        if matched_patterns:
            lines.append(
                "\n**Likely Pattern(s):** " + ", ".join(p.name for p in matched_patterns)
            )

    actions = case.get("actions_taken", [])
    if actions:
        lines.append(f"\n**Actions Already Taken:** {len(actions)}")
        for a in actions[-MAX_ACTIONS_IN_CONTEXT:]:
            action_label = a.get("action_type") or a.get("action") or "ACTION"
            target = a.get("target_id") or a.get("target") or "GLOBAL"
            lines.append(f"- {action_label} on {target}")

    return "\n".join(lines)


def transaction_context(tx_id: str, tenant_id: str) -> str:
    """Full Markdown context for one transaction, including the scoring
    engine's risk-factor breakdown — this is what backs 'explain this
    transaction'/'why was TX-XXXX flagged' answers."""
    tx = transactions_for_tenant(tenant_id).get(tx_id)
    if not tx:
        return f"No transaction found with ID `{tx_id}`."

    factors = sorted(
        tx.get("risk_factors", []), key=lambda f: f.get("contribution", 0), reverse=True
    )
    contributing = [f for f in factors if f.get("contribution", 0) > 0]
    if contributing:
        factor_lines = "\n".join(
            f"  - {f['name'].replace('_', ' ')}: value {f.get('value', 0)}, "
            f"weight {f.get('weight', 0)}, contributed {f.get('contribution', 0)} points"
            for f in contributing
        )
    else:
        factor_lines = "  - No individual risk factor contributed materially; score is baseline."

    return (
        f"**Transaction ID:** {tx['tx_id']}\n"
        f"**Amount:** Rs.{tx.get('amount', 0):,.2f}\n"
        f"**Channel:** {tx.get('channel', 'N/A')}\n"
        f"**Sender:** {tx.get('sender_account', 'Unknown')}\n"
        f"**Receiver:** {tx.get('receiver_account', 'Unknown')}\n"
        f"**Timestamp:** {tx.get('timestamp', 'N/A')}\n"
        f"**Risk Score:** {tx.get('risk_score', 0)}% ({tx.get('threshold', 'LOW')})\n"
        f"**Rule Engine Score:** {tx.get('rule_score', 0)}\n"
        f"**ML Model Score:** {tx.get('ml_score', 0)}\n"
        f"**Top Reason:** {tx.get('reason', 'N/A')}\n"
        f"**Contributing Risk Factors:**\n{factor_lines}\n"
        f"**Linked Case:** {tx.get('case_id') or 'None'}"
    )


def dashboard_context(tenant_id: str) -> str:
    """Server-side mirror of Dashboard.jsx's client-side aggregate
    formulas, so copilot answers about system-wide stats always match
    what's on screen — "system-wide" meaning this tenant's own system,
    never another tenant's aggregates folded in."""
    cases = list(cases_for_tenant(tenant_id).values())
    txs = list(transactions_for_tenant(tenant_id).values())

    total_fraud = sum(c.get("total_fraud_amount", 0.0) for c in cases)
    total_recoverable = sum(c.get("recoverable_amount", 0.0) for c in cases)
    estimated_loss = total_fraud - total_recoverable

    status_counts: dict[str, int] = {}
    for c in cases:
        status = c.get("status", "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1

    channel_counts: dict[str, int] = {}
    for tx in txs:
        channel = tx.get("channel", "UNKNOWN")
        channel_counts[channel] = channel_counts.get(channel, 0) + 1

    factor_counts: dict[str, int] = {}
    for tx in txs:
        for f in tx.get("risk_factors", []):
            factor_counts[f["name"]] = factor_counts.get(f["name"], 0) + 1
    top_factors = sorted(factor_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]

    avg_risk = (sum(tx.get("risk_score", 0) for tx in txs) / len(txs)) if txs else 0.0

    lines = [
        f"**Total Cases:** {len(cases)}",
        "**Case Status Breakdown:** "
        + (", ".join(f"{k}: {v}" for k, v in status_counts.items()) or "none"),
        f"**Total Transactions Processed:** {len(txs)}",
        f"**Average Transaction Risk Score:** {avg_risk:.1f}%",
        f"**Total Exposure (fraud amount across all cases):** Rs.{total_fraud:,.2f}",
        f"**Total Recoverable:** Rs.{total_recoverable:,.2f}",
        f"**Estimated Loss:** Rs.{estimated_loss:,.2f}",
        "**Channel Distribution:** "
        + (", ".join(f"{k}: {v}" for k, v in channel_counts.items()) or "none"),
        "**Top Risk Factors:** "
        + (
            ", ".join(f"{name.replace('_', ' ')} ({count})" for name, count in top_factors)
            or "none"
        ),
    ]
    return "\n".join(lines)


def general_context(tenant_id: str) -> str:
    """No specific case selected — summarize the current overall picture
    (dashboard stats + top high-risk cases) instead of a static
    'no context' placeholder, so the copilot stays useful without a
    selection. Scoped to tenant_id's own cases only."""
    cases = list(cases_for_tenant(tenant_id).values())
    if not cases:
        return "No cases exist yet. The system has not detected any fraud activity."

    high_risk = [c for c in cases if c.get("status") == CaseStatus.HIGH_RISK]
    high_risk_sorted = sorted(
        high_risk, key=lambda c: c.get("urgency_score", 0), reverse=True
    )[:MAX_HIGH_RISK_CASES_IN_CONTEXT]

    lines = [
        "No specific case is selected. Current overall picture:",
        dashboard_context(tenant_id),
    ]
    if high_risk_sorted:
        lines.append("\n**Top High-Risk Cases by Urgency:**")
        for c in high_risk_sorted:
            lines.append(
                f"- `{c['case_id']}`: risk {c.get('risk_level', 0)}%, "
                f"urgency {c.get('urgency_score', 0):.1f}, "
                f"Rs.{c.get('total_fraud_amount', 0):,.2f} at stake, "
                f"golden window {c.get('golden_window_minutes', 0)}min"
            )
    return "\n".join(lines)


def build_for_request(context_case_id: str | None, tenant_id: str) -> str:
    """Entry point for copilot.py's freeform (non-structured-intent) LLM
    path: case-specific context when a case is selected, otherwise a
    system-wide (this tenant's own system) summary."""
    if context_case_id:
        return case_context(context_case_id, tenant_id)
    return general_context(tenant_id)
