"""
SENTINEL — Fraud Domain Knowledge Base
==========================================
Static reference content for the copilot's "what is X / how does X
work" questions, scoped to SENTINEL's actual domain: real-time bank
transfers and mule chains — not generic e-commerce/card-fraud examples
(see the "Adapt to SENTINEL's real domain" decision the Copilot rebuild
was built under).

Every pattern here ties back to the live risk_factors
app.engines.scoring_engine actually produces (the `signals` field), so
an answer isn't just a textbook definition — it tells the investigator
what SENTINEL itself would show them, and patterns_for_signals() lets
other structured intents (explain-transaction, recommend-next-case)
cross-reference a case's actual fired signals against this knowledge
base to give pattern-specific, not generic, recommendations.

This is deterministic, hand-authored content, not LLM-generated — same
reasoning as Phase B's data lookups: an investigator-facing knowledge
base should not hallucinate, and it must answer identically whether or
not a live LLM provider is configured (MockProvider/offline mode).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FraudPattern:
    name: str
    aliases: tuple[str, ...]
    summary: str
    how_it_works: str
    # Names as they appear in a transaction's risk_factors list (see
    # app/engines/scoring_engine.py) that this pattern typically surfaces as.
    signals: tuple[str, ...]
    investigate: tuple[str, ...]


_PATTERNS: tuple[FraudPattern, ...] = (
    FraudPattern(
        name="Money Muling / Mule Chains",
        aliases=("mule chain", "money mule", "muling", "mule account", "money laundering"),
        summary=(
            "A chain of accounts (often opened with stolen or purchased identities) used to "
            "move stolen funds through several hops to obscure the money trail before final "
            "cash-out or crypto conversion."
        ),
        how_it_works=(
            "Stolen funds enter at an origin account, then move rapidly through a chain of "
            "'mule' accounts (SENTINEL tracks this as `chain` / `hop_number` on a case) — each "
            "hop makes the money harder to trace back. SENTINEL applies a decay factor to the "
            "risk score at each hop (DECAY_FACTOR in scoring_engine.py) since later hops are "
            "structurally further from the origin fraud but still complicit. A 'golden window' "
            "(golden_window_minutes on each case) tracks how long investigators have before the "
            "terminal mule account withdraws or cashes out the funds."
        ),
        signals=("new_receiver", "bulk_transfer", "amount_deviation"),
        investigate=(
            "Trace the full `chain` on the case to find the terminal (most recent) receiving account.",
            "Freeze the terminal account before its golden window expires.",
            "Check for bulk_transfer_flag / rapid fan-out to multiple receivers, a common muling signature.",
            "Alert the receiving bank if the terminal account is at a different institution.",
        ),
    ),
    FraudPattern(
        name="SIM Swap Fraud",
        aliases=("sim swap", "sim-swap", "sim swapping"),
        summary=(
            "An attacker convinces a telecom carrier to port a victim's phone number to a SIM "
            "they control, then uses that number to intercept OTPs/2FA and take over the "
            "victim's bank accounts."
        ),
        how_it_works=(
            "Once the attacker controls the victim's phone number, they can reset banking app "
            "credentials and approve OTP-based transaction authorization as if they were the "
            "victim. This typically shows up as a sudden device change and/or location change "
            "on a previously stable account, often followed immediately by high-value transfers "
            "to a new, never-seen-before receiver."
        ),
        signals=("device_anomaly", "new_receiver", "first_time_payee"),
        investigate=(
            "Check whether device_changed/location_changed fired alongside a new, never-seen receiver.",
            "Cross-reference with the account's historical velocity pattern in dashboard stats.",
            "If confirmed, freeze immediately — SIM swap victims typically have no idea a takeover is in progress.",
            "Recommend the victim's bank flag the account for mandatory re-verification before any further transfers.",
        ),
    ),
    FraudPattern(
        name="Account Takeover (ATO)",
        aliases=("account takeover", "ato fraud"),
        summary=(
            "An attacker gains unauthorized control of a legitimate account (via phishing, "
            "credential stuffing, malware, or SIM swap) and transacts as the real owner."
        ),
        how_it_works=(
            "ATO is the broader category SIM swap fraud falls under. SENTINEL's signals for it: "
            "on_active_call (the classic 'stay on the phone with a scammer while I transfer this' "
            "social-engineering pattern), is_remote_access_active (screen-sharing/remote-desktop "
            "scams), is_scripted (automated, non-human transaction timing), and device/location "
            "changes. Any of these alongside a large, unusual-for-this-account amount is a strong "
            "ATO signal."
        ),
        signals=("call_flag", "remote_access", "device_anomaly", "scripted_behavior"),
        investigate=(
            "Look for on_active_call or is_remote_access_active — both point to live social "
            "engineering, not just a compromised credential replayed later.",
            "Freeze and contact the account holder directly (not via the phone number on file, in "
            "case that's also compromised) to confirm.",
            "Recommend a full credential reset, not just blocking this one transaction.",
        ),
    ),
    FraudPattern(
        name="Cross-Border Fraud",
        aliases=("cross border", "cross-border", "international fraud"),
        summary=(
            "Funds routed to a foreign account or intermediary specifically to complicate "
            "recovery — cross-border transfers are much harder to freeze or reverse once they "
            "clear, since it requires cooperation from a foreign bank/jurisdiction."
        ),
        how_it_works=(
            "SENTINEL flags is_cross_border transactions with an automatic cross_border_risk "
            "contribution, and treats them as an instant-escalation signal (they also force "
            "new_receiver and amount_deviation to their maximum in the scoring engine) because "
            "the recovery window is so much shorter than a domestic mule chain."
        ),
        signals=("cross_border_risk", "new_receiver", "amount_deviation"),
        investigate=(
            "Treat these as the highest urgency in the queue — domestic freezes are fast; "
            "cross-border recovery depends on correspondent-bank cooperation and moves much slower.",
            "Alert the receiving country's correspondent bank / SWIFT recall process immediately.",
            "Check if this is hop 0 of a larger chain (an early cross-border hop is often deliberate "
            "obfuscation before the funds move further).",
        ),
    ),
    FraudPattern(
        name="Velocity Attacks",
        aliases=("velocity attack", "velocity spike", "velocity fraud", "rapid transactions"),
        summary=(
            "An unusually rapid burst of transactions from one account — either draining it fast "
            "before a freeze can happen, or 'fanning out' stolen funds across many receivers at once."
        ),
        how_it_works=(
            "SENTINEL's velocity_flag forces both time_anomaly and amount_deviation to elevated "
            "floors, and bulk_transfer_flag (many outgoing transfers in a short window) adds its "
            "own risk contribution. Velocity spikes are often the clearest real-time signal that an "
            "attacker is racing to move funds before detection — most fraud engines (SENTINEL "
            "included) treat velocity as a near-mandatory escalation trigger."
        ),
        signals=("velocity_spike", "bulk_transfer", "time_anomaly"),
        investigate=(
            "Velocity spikes are time-critical — check the case's golden_window_minutes immediately.",
            "Freeze proactively rather than waiting for full confirmation; the cost of a false "
            "positive freeze is much lower than a missed fast drain.",
            "Look at bulk_transfer_flag to see if funds are fanning out to multiple mule accounts "
            "simultaneously rather than a single chain.",
        ),
    ),
    FraudPattern(
        name="Crypto Drain",
        aliases=("crypto drain", "crypto fraud", "cryptocurrency fraud", "crypto related", "crypto risk"),
        summary=(
            "Funds moved toward a cryptocurrency on-ramp/exchange as the final step of laundering "
            "— crypto conversion is often the last hop before funds become effectively unrecoverable."
        ),
        how_it_works=(
            "SENTINEL's is_crypto_related flag pushes amount_deviation and new_receiver to their "
            "maximum and elevates time_anomaly, reflecting that a crypto off-ramp is one of the "
            "highest-severity signals in the engine — once funds convert to crypto, conventional "
            "bank-side recovery mechanisms (freezes, SWIFT recalls) no longer apply."
        ),
        signals=("crypto_risk", "amount_deviation", "new_receiver"),
        investigate=(
            "Treat crypto-related hops as top priority — this is frequently the last recoverable "
            "moment before funds leave the traditional banking system entirely.",
            "Freeze the sending account immediately rather than waiting to confirm the receiving "
            "exchange account.",
            "If funds have already converted, escalate to blockchain-analytics/law-enforcement "
            "channels — SENTINEL's own recovery mechanisms only cover bank-side accounts.",
        ),
    ),
    FraudPattern(
        name="Card Testing",
        aliases=("card testing", "carding"),
        summary=(
            "An attacker validates a batch of stolen card/account numbers by running many small "
            "transactions in quick succession, discarding the ones that fail and using the "
            "confirmed-valid ones for larger fraud afterward."
        ),
        how_it_works=(
            "In SENTINEL's channel model this shows up on the CARD channel as a bulk_transfer_flag "
            "burst of small, round-number (is_round_number) transactions to a first-time payee in a "
            "tight time window — individually low-risk amounts, but the pattern (volume + timing + "
            "round numbers) is the tell, not any single transaction."
        ),
        signals=("bulk_transfer", "amount_deviation"),
        investigate=(
            "Look across recent CARD-channel transactions for a burst of small, round amounts to "
            "new payees rather than judging any one transaction in isolation.",
            "Recommend blocking the card/account for further authorizations, not just this one "
            "transaction — the larger fraudulent charge is usually still coming.",
        ),
    ),
    FraudPattern(
        name="Synthetic Identity Fraud",
        aliases=("synthetic identity", "fake identity fraud"),
        summary=(
            "An account opened with a fabricated or blended identity (real + fake identity "
            "elements) specifically to receive and launder stolen funds, rather than a "
            "genuinely compromised real customer."
        ),
        how_it_works=(
            "SENTINEL doesn't perform identity verification itself, so this pattern surfaces "
            "indirectly: a receiving account with no prior transaction history (is_new_receiver) "
            "that immediately starts receiving large, first-time-payee transfers is the closest "
            "proxy signal available — a synthetic identity has no real transaction history to "
            "build a baseline from, unlike a takeover of a genuine long-standing account."
        ),
        signals=("new_receiver", "first_time_payee"),
        investigate=(
            "A brand-new receiver account with no transaction history that's already the target "
            "of a large transfer is a red flag independent of any single transaction's amount.",
            "Check whether this account appears as the origin or an early hop on other open cases "
            "— synthetic mule accounts are frequently reused across multiple fraud rings.",
        ),
    ),
)

# General concepts an investigator might ask about that aren't detected by
# SENTINEL's data model (no merchant/chargeback data exists here) but still
# deserve a correct, honest answer rather than silence or a guess.
_GENERAL_CONCEPTS: dict[str, str] = {
    "friendly fraud": (
        "**Friendly fraud** is when a legitimate customer disputes a charge they actually "
        "authorized (claiming it was unauthorized) to get a refund while keeping the goods or "
        "service. It's a merchant/chargeback-side concept — SENTINEL doesn't model merchant "
        "transactions or chargebacks (it tracks bank-to-bank transfers), so it has no direct "
        "detection signal for this here. Included for reference only."
    ),
    "chargeback fraud": (
        "**Chargeback fraud** is the abuse of a card network's chargeback/dispute process to "
        "reverse a legitimate charge fraudulently. Like friendly fraud, this requires a merchant/"
        "card-network data model SENTINEL doesn't have — included for reference only."
    ),
}

# Built once at import time: risk_factor name -> the pattern that "owns" it
# (the first pattern in _PATTERNS declaring that signal), so a case's fired
# risk_factors can be cross-referenced back to plain-English fraud patterns.
_SIGNAL_TO_PATTERN: dict[str, FraudPattern] = {}
for _pattern in _PATTERNS:
    for _signal in _pattern.signals:
        _SIGNAL_TO_PATTERN.setdefault(_signal, _pattern)


def find_pattern(message: str) -> FraudPattern | None:
    """First fraud pattern whose alias appears in message, or None."""
    msg = message.lower()
    for pattern in _PATTERNS:
        if any(alias in msg for alias in pattern.aliases):
            return pattern
    return None


def find_general_concept(message: str) -> str | None:
    """A hand-written definition for a concept SENTINEL doesn't model, or None."""
    msg = message.lower()
    for key, definition in _GENERAL_CONCEPTS.items():
        if key in msg:
            return definition
    return None


def patterns_for_signals(signal_names: list[str] | set[str]) -> list[FraudPattern]:
    """
    Maps a set of fired risk_factor names (e.g. from a transaction's
    risk_factors list) back to the fraud patterns they're associated
    with, deduplicated and in a stable order. Used to give
    pattern-specific investigation guidance instead of generic
    boilerplate wherever a case/transaction's actual signals are known.
    """
    matched: list[FraudPattern] = []
    for name in sorted(signal_names):
        pattern = _SIGNAL_TO_PATTERN.get(name)
        if pattern and pattern not in matched:
            matched.append(pattern)
    return matched


def format_pattern_reply(pattern: FraudPattern) -> str:
    lines = [
        f"**{pattern.name}**",
        "",
        pattern.summary,
        "",
        "**How it works:**",
        pattern.how_it_works,
        "",
        "**SENTINEL signals that surface this pattern:** " + ", ".join(pattern.signals),
        "",
        "**Investigation steps:**",
    ]
    lines += [f"{i + 1}. {step}" for i, step in enumerate(pattern.investigate)]
    return "\n".join(lines)
