import logging
import random
import time

from app.core.config import HIGH_RISK_THRESHOLD, MEDIUM_THRESHOLD
from app.core.constants import CaseStatus
from app.core import redis_client
from app.core.repository import repository
from app.engines.scoring_engine import score_transaction
from app.engines.case_manager import process_scored_tx
from app.engines.graph_engine import add_node, add_edge, get_graph
from app.engines.recovery_engine import recalculate
from app.services.reasoning_engine import generate_reasoning
from app.services.ml_risk_engine import predict_ml_score, feature_names
from app.utils.json_codec import from_json, to_json

logger = logging.getLogger("sentinel.orchestrator")


def _find_matching_case(cases, sender_id: str, receiver_id: str) -> dict | None:
    """The exact case-chain-matching predicate run_pipeline has always
    used, factored out so it can be applied identically to a local scan
    and a Postgres-sourced one (see _find_matching_case_via_postgres)
    without the two silently drifting apart."""
    return next((c for c in cases
                 if (c["origin_account"] == sender_id or sender_id in c["chain"] or receiver_id in c["chain"])
                 and c["status"] in [CaseStatus.NEW, CaseStatus.HIGH_RISK]
                 and len(c["chain"]) < c.get("max_nodes", 5)), None)


def _hydrate_case_from_postgres(case_id: str, store: dict) -> dict | None:
    """Look up a single case by id in Postgres and, if found, cache it
    into store["cases"] so this process doesn't need to repeat the
    Postgres round-trip on the next transaction that references it."""
    try:
        case = repository.get_case(case_id)
    except Exception as e:
        logger.warning("Postgres case lookup degraded for %s: %s", case_id, e)
        return None
    if case is not None:
        store.setdefault("cases", {})[case_id] = case
    return case


def _find_matching_case_via_postgres(sender_id: str, receiver_id: str, store: dict) -> dict | None:
    """Local cache missed — this replica may simply not have seen a case
    another replica already created for this sender/receiver chain.
    Pulls every case from Postgres, caches all of them locally (so
    subsequent transactions in the same chain hit the fast local path),
    and re-runs the same matching predicate. Bounded to cases only (not
    transactions) — a fallback path, not the hot path, and case volume in
    a fraud system is orders of magnitude lower than transaction volume."""
    try:
        all_cases = repository.list_cases()
    except Exception as e:
        logger.warning("Postgres case scan degraded for %s/%s: %s", sender_id, receiver_id, e)
        return None
    cache = store.setdefault("cases", {})
    for c in all_cases:
        cid = c.get("case_id")
        if cid and cid not in cache:
            cache[cid] = c
    return _find_matching_case(cache.values(), sender_id, receiver_id)


def _velocity_key(sender_id: str) -> str:
    return f"sentinel:vcache:{sender_id}"


def _account_key(account_id: str) -> str:
    return f"sentinel:account:{account_id}"


def record_velocity(sender_id: str, receiver_id: str, amount: float, tx_id: str, timestamp: float | None = None) -> dict:
    """Append a velocity-cache entry for `sender_id` to Redis (a ZSET,
    score = timestamp) and return the derived 1h/24h metrics used by
    scoring. `timestamp` defaults to "now" for live traffic;
    app.core.repository.load_all()'s startup replay passes each
    transaction's own historical timestamp instead, so replayed history
    lands at the point in the window it actually occurred at rather than
    "now" — entries older than the 24h window are pruned immediately on
    replay rather than sitting inertly in memory forever (today's
    in-memory dict never expunges them; this is a small, deliberate
    improvement, not an observable scoring change, since anything outside
    the window was already excluded from every velocity calculation).

    The ZSET member includes tx_id specifically for uniqueness: two
    entries with identical amount/receiver/timestamp (test fixtures often
    share a fixed timestamp literal) would otherwise collide and silently
    merge into one entry in a plain amount/receiver/timestamp member.

    Degrades gracefully if Redis is unreachable — hostile-review finding:
    this used to have no error handling at all, so a Redis outage turned
    every POST /transaction into a 500 even though the transaction itself
    scored and persisted to Postgres fine. On failure, returns a
    conservative "treat this as an isolated, first-time transaction"
    result (velocity 1, no cross-referencing) rather than raising —
    scoring continues with degraded (not wrong-direction) velocity
    signals instead of not happening at all. Logged at WARNING so the
    degradation is visible without needing a debugger.
    """
    now_ts = time.time()
    ts = now_ts if timestamp is None else timestamp
    key = _velocity_key(sender_id)

    try:
        r = redis_client.get_redis()
        r.zremrangebyscore(key, "-inf", now_ts - 86400)
        entry = {"tx_id": tx_id, "timestamp": ts, "amount": amount, "receiver": receiver_id}
        r.zadd(key, {to_json(entry): ts})
        r.expire(key, 90000)  # ~25h safety margin — today's dict never expires a quiet sender

        v_cache_1h = []
        unique_receivers_24h = set()
        for member, score in r.zrange(key, 0, -1, withscores=True):
            e = from_json(member)
            if not e:
                continue
            if now_ts - score <= 3600:
                v_cache_1h.append(e)
            if now_ts - score <= 86400:
                unique_receivers_24h.add(e.get("receiver"))

        return {
            "tx_velocity": len(v_cache_1h),
            "amount_1h": sum(e.get("amount", 0.0) for e in v_cache_1h),
            "receivers_24h": len(unique_receivers_24h),
        }
    except Exception as e:
        logger.warning("record_velocity degraded for %s (Redis unavailable: %s) — scoring this transaction as isolated", sender_id, e)
        return {"tx_velocity": 1, "amount_1h": amount, "receivers_24h": 1}


def _default_account(account_id: str, amount: float, velocity: dict) -> dict:
    """The "brand new account" shape both save_account() and its Redis-
    unavailable fallback below produce — factored out so the degraded
    path can't silently drift from the normal one."""
    return {
        "account_id": account_id,
        "total_historical_amount": amount,
        "historical_tx_count": 1,
        "avg_monthly_tx_amount": amount,
        "current_balance_sim": round(random.uniform(50000, 250000), 2),
        "status": "active",
        "is_new_receiver": True,  # first time seen
        "tx_velocity": velocity["tx_velocity"],
        "amount_1h": velocity["amount_1h"],
        "receivers_24h": velocity["receivers_24h"],
    }


def get_account(account_id: str) -> dict | None:
    """Read-only account lookup — does NOT create/persist a missing
    account. Mirrors run_pipeline's pre-existing receiver-account lookup
    behavior exactly (see below): a receiver with no account record gets
    a fresh sparse dict built at read time, on every call, never written
    back — a pre-existing quirk (receiver accounts before Phase 1 were
    never actually saved into store["accounts"] either), preserved as-is
    rather than silently changed by this migration.

    Degrades to None (== "not found", the same value a genuinely missing
    account produces) if Redis is unreachable — the caller's own "not
    found" fallback already handles that case correctly, so no separate
    degraded branch is needed here."""
    try:
        raw = redis_client.get_redis().get(_account_key(account_id))
        return from_json(raw) if raw else None
    except Exception as e:
        logger.warning("get_account degraded for %s (Redis unavailable: %s) — treating as not-found", account_id, e)
        return None


def save_account(account_id: str, amount: float, velocity: dict) -> dict:
    """Create-or-update the sender-side account record in Redis and
    return it. Called once per transaction for the sender (always
    persisted — unlike get_account's receiver-side read path above).

    Degrades gracefully if Redis is unreachable: returns a freshly-built
    account dict (same shape as a brand-new account) WITHOUT persisting
    it, so scoring can proceed with a complete, well-shaped account
    object instead of raising. The account's historical totals won't
    reflect reality for this one transaction if Redis was down — an
    accepted, logged trade-off; the alternative is failing the request
    entirely for a transaction that Postgres would otherwise process and
    persist correctly.
    """
    key = _account_key(account_id)
    try:
        r = redis_client.get_redis()
        account = from_json(r.get(key)) or None
        if not account:
            account = _default_account(account_id, amount, velocity)
        else:
            account["total_historical_amount"] = account.get("total_historical_amount", 0.0) + amount
            account["historical_tx_count"] = account.get("historical_tx_count", 0) + 1
            account["avg_monthly_tx_amount"] = account["total_historical_amount"] / account["historical_tx_count"]
            account["is_new_receiver"] = False
            account["tx_velocity"] = velocity["tx_velocity"]
            account["amount_1h"] = velocity["amount_1h"]
            account["receivers_24h"] = velocity["receivers_24h"]
        r.set(key, to_json(account))
        return account
    except Exception as e:
        logger.warning("save_account degraded for %s (Redis unavailable: %s) — using an unpersisted fallback account", account_id, e)
        return _default_account(account_id, amount, velocity)


def run_pipeline(tx: dict, store: dict) -> dict:
    """
    Main integration pipeline processing a single transaction
    through all core SENTINEL engines sequentially.

    Stays a plain synchronous function, called unawaited from the async
    POST /transaction handler, by deliberate Phase 1 design (see the
    build plan) — the velocity/account Redis calls below are therefore
    blocking I/O on the request's event-loop thread. Accepted trade-off:
    Redis is co-located and sub-millisecond, and a real async rewrite of
    the whole pipeline (this function plus case_manager/graph_engine/
    recovery_engine) is a larger, separate project than this phase. If
    this ever becomes a measured bottleneck, that's the fix — not
    sprinkling asyncio.to_thread piecemeal around individual calls here.
    """

    # FIX 4: Safe Graph Initialization
    if "graphs" not in store:
        store["graphs"] = {}

    sender_id = tx.get("sender_account")
    receiver_id = tx.get("receiver_account")
    amount = float(tx.get("amount", 0.0))

    # --- Stateful Velocity Streaming (now Redis-backed, see record_velocity) ---
    velocity = record_velocity(sender_id, receiver_id, amount, tx.get("tx_id"))
    real_velocity = velocity["tx_velocity"]
    amount_1h = velocity["amount_1h"]
    receivers_24h = velocity["receivers_24h"]

    account = save_account(sender_id, amount, velocity)

    # Expose to simulator_meta for downstream scoring hooks
    if "simulator_meta" not in tx:
        tx["simulator_meta"] = {}
    tx["simulator_meta"]["tx_velocity"] = real_velocity
    tx["simulator_meta"]["receivers_24h"] = receivers_24h
    tx["simulator_meta"]["amount_1h"] = amount_1h
        
    # 1b. Try to find an existing active case to inherit origin_score.
    #
    # Falls back to Postgres (the durable source of truth) when not found
    # in this process's local cache, and hydrates any hit back into
    # store["cases"] — necessary once more than one API replica exists.
    # Two concrete failure modes this fixes (hostile-review finding):
    #   1. A later hop in a chain is explicitly tagged with a case_id
    #      (e.g. by the simulator) that a DIFFERENT replica created.
    #      Without this fallback, case_manager.py's store["cases"][case_id]
    #      lookup KeyErrors — an unhandled 500 for a perfectly legitimate
    #      continuation transaction.
    #   2. A fresh transaction with no case_id, whose sender/receiver
    #      already belongs to a case another replica created, would
    #      silently fork into a duplicate case instead of joining the one
    #      that already exists — same root cause, quieter symptom.
    # Postgres lookups here are guarded the same way the Redis calls
    # above are: a Postgres hiccup during this *fallback* degrades to
    # "no match found" (the exact pre-fix behavior) rather than raising,
    # so a flaky fallback lookup can't turn into a new failure mode of
    # its own.
    case_id = tx.get("case_id")
    case = None
    if case_id:
        case = store.get("cases", {}).get(case_id)
        if case is None:
            case = _hydrate_case_from_postgres(case_id, store)
        if case is None:
            # Given case_id resolves nowhere — neither locally nor via
            # Postgres (a genuinely bogus/stale id, or a Postgres outage
            # during the fallback above). case_manager.py unconditionally
            # does store["cases"][case_id] whenever tx["case_id"] is
            # truthy, with no existence check of its own — leaving a
            # phantom case_id set here would KeyError there. Clearing it
            # lets case_manager.py fall through to its normal "no case_id"
            # path and start a fresh case instead, which is the correct,
            # safe behavior for an id that can't be resolved either way.
            tx.pop("case_id", None)
            case_id = None
    else:
        # Fallback: Find case where sender or receiver is already in a chain
        receiver_id = tx.get("receiver_account")
        case = _find_matching_case(store.get("cases", {}).values(), sender_id, receiver_id)
        if case is None:
            case = _find_matching_case_via_postgres(sender_id, receiver_id, store)
        if case:
            tx["case_id"] = case["case_id"]

    if case:
        tx["origin_score"] = case.get("origin_score", 0)

    # 2. Call scoring_engine
    score_output = score_transaction(tx, account)
    rule_score = score_output.get("risk_score", 0)
    ml_score = rule_score
    final_score = rule_score

    try:
        # 4a. Random Forest Inference (or Emulator fallback)
        ml_score = predict_ml_score(float(rule_score), tx, account)
        logger.info("Rule score %s, ML score %s", rule_score, round(ml_score, 1))

        # 5. Hybrid Fusion: 60% ML + 40% Rule (graph GNN will refine later)
        final_score = int(0.6 * ml_score + 0.4 * rule_score)
    except Exception as e:
        logger.warning("ML scoring failed, falling back to rule score: %s", e)
        final_score = rule_score
        ml_score = rule_score

    score_output["risk_score"] = final_score
    score_output["rule_score"] = int(rule_score)
    score_output["ml_score"] = int(ml_score)

    # Feature Importance (Explainability — Dynamic Per-Transaction)
    # Step 1: Map rule factor contributions onto feature slots
    risk_factors = score_output.get("risk_factors", [])
    name_map = {
        "new_receiver":     "is_new_receiver",
        "amount_deviation": "amount",
        "time_anomaly":     "hour",
        "call_flag":        "call_flag",
        "velocity_spike":   "velocity",
        "bulk_transfer":    "chain_depth",
        "cross_border_risk":"amount",
        "device_anomaly":   "is_new_receiver",
        "crypto_risk":      "call_flag",
        "remote_access":    "call_flag",
        "scripted_behavior":"call_flag",
        "first_time_payee": "is_new_receiver",
    }

    raw = {fn: 0.0 for fn in feature_names}
    for f in risk_factors:
        mapped = name_map.get(f["name"], None)
        if mapped and mapped in raw:
            raw[mapped] += float(f.get("contribution", 0))

    # Step 2: Add per-transaction raw signal so every tx has unique values
    # even when no rule factors fired (eliminates equal-weight fallback)
    try:
        from datetime import datetime as _dt
        sim_meta = tx.get("simulator_meta", {})

        ts = tx.get("timestamp", "")
        try:
            dt = _dt.fromisoformat(ts.replace("Z", "+00:00"))
            hour_val = dt.hour / 23.0
        except Exception:
            hour_val = 0.5

        amount_val   = min(float(tx.get("amount", 0)) / 500000.0, 1.0)

        # Read velocity from simulator_meta first, then account
        velocity_raw = sim_meta.get("tx_velocity", account.get("tx_velocity", 1))
        velocity_val = min(float(velocity_raw) / 15.0, 1.0)

        # Read is_new_receiver from simulator_meta first, then account
        is_new_raw   = sim_meta.get("is_new_receiver", account.get("is_new_receiver", False))
        is_new_val   = 1.0 if is_new_raw else 0.08

        call_val     = 1.0 if tx.get("on_active_call", False) else 0.04
        hop_val      = min(float(tx.get("hop_number", 0)) / 5.0, 1.0)

        # Small base weight so rule contributions dominate when present
        SIGNAL_SCALE = 5.0
        raw["amount"]          += amount_val   * SIGNAL_SCALE
        raw["hour"]            += hour_val     * SIGNAL_SCALE
        raw["is_new_receiver"] += is_new_val   * SIGNAL_SCALE
        raw["velocity"]        += velocity_val * SIGNAL_SCALE
        raw["call_flag"]       += call_val     * SIGNAL_SCALE
        raw["chain_depth"]     += hop_val      * SIGNAL_SCALE
    except Exception:
        pass

    # Step 3: Normalize to percentages summing to 1.0
    total_raw = sum(raw.values())
    if total_raw > 0:
        importance = {k: round(v / total_raw, 4) for k, v in raw.items()}
    else:
        import random as _rnd
        importance = {fn: round(1/len(feature_names) + _rnd.uniform(-0.02, 0.02), 4)
                      for fn in feature_names}

    score_output["ml_feature_importance"] = dict(
        sorted(importance.items(), key=lambda x: x[1], reverse=True)
    )

    # Update threshold based on final hybrid score.
    # BUGFIX: this used to hardcode 70/40 independently of
    # config.HIGH_RISK_THRESHOLD (60) / MEDIUM_THRESHOLD (40), which
    # scoring_engine.py already uses correctly. That meant a transaction
    # scoring 60-69 was escalated internally as HIGH_RISK (case status,
    # EC-03 withdrawal timer) but displayed/exported to investigators as
    # "MEDIUM" — now unified on the single config source of truth.
    if final_score >= HIGH_RISK_THRESHOLD:
        score_output["threshold"] = "HIGH_RISK"
    elif final_score >= MEDIUM_THRESHOLD:
        score_output["threshold"] = "MEDIUM"
    else:
        score_output["threshold"] = "LOW"
    
    reason_data = generate_reasoning(score_output.get("risk_factors", []))
    score_output["reason"] = reason_data["short_reason"]
    score_output["full_reason"] = reason_data["full_reason"]
    
    score = score_output["risk_score"]
    confidence = "HIGH" if score >= 70 else "MEDIUM" if score >= 40 else "LOW"
    score_output["confidence"] = confidence
    
    logger.info(
        "Scored transaction %s: %s (rule=%s ml=%s) reason=%s",
        tx.get("tx_id"), score, int(rule_score), int(ml_score), score_output["reason"],
    )

    # 3. Update transaction with score results
    tx["risk_score"] = score_output.get("risk_score")
    tx["rule_score"] = score_output.get("rule_score")
    tx["ml_score"] = score_output.get("ml_score")
    tx["risk_factors"] = score_output.get("risk_factors")
    tx["threshold"] = score_output.get("threshold")
    tx["top_reason"] = score_output.get("top_reason")
    tx["reason"] = score_output["reason"]
    tx["full_reason"] = score_output["full_reason"]
    tx["confidence"] = score_output["confidence"]
    tx["ml_feature_importance"] = score_output.get("ml_feature_importance", {})


    # 4. Call case_manager
    case = process_scored_tx(tx, score_output, store)
    
    # FIX 1: ORIGIN SCORE PERSISTENCE (Moved after process_scored_tx)
    if tx.get("hop_number", 0) == 0:
        tx["origin_score"] = tx.get("rule_score", 0)
        if case:
            case["origin_score"] = tx.get("rule_score", 0)
    
    graph = None
    recovery = None

    # 5. GRAPH ENGINE (IMPORTANT)
    # Only triggered if a case was created or escalated
    if case:
        case_id = case["case_id"]
        
        # FIX 2: RECEIVER FALLBACK (RECOVERY FIX)
        receiver_id = tx.get("receiver_account")
        receiver_account = get_account(receiver_id)
        if not receiver_account:
            amount = float(tx.get("amount", 0.0))
            receiver_account = {
                "account_id": receiver_id,
                # Initialization: Start with enough balance to cover the fraud inflow
                "current_balance_sim": round(amount * random.uniform(0.9, 1.1), 2),
                "status": "withdrawn" if receiver_id.startswith("ACC-EXIT") else "active"
            }
            
        # Add Nodes to Graph
        add_node(case_id, account, store)
        add_node(case_id, receiver_account, store)
        
        # Add Edge representing the transaction flow
        amount = float(tx.get("amount", 0.0))
        add_edge(case_id, sender_id, receiver_id, tx.get("tx_id"), amount, store)
        
        # Fetch finalized graph
        graph = get_graph(case_id, store)

        # GNN re-scoring was removed: it ran a randomly-initialized,
        # never-trained PyTorch Geometric network (FraudGraphSAGE) and
        # blended its output into the displayed score — indistinguishable
        # from noise, not real graph-based inference. The XGBoost-based
        # hybrid score computed above (predict_ml_score) is what's shown.
        score_output["gnn_available"] = False
        tx["gnn_available"] = False

        # 6. Call recovery_engine
        recovery = recalculate(case_id, store)

    # 7. Store transaction globally
    tx_id = tx.get("tx_id")
    if tx_id:
        if "transactions" not in store:
            store["transactions"] = {}
        store["transactions"][tx_id] = tx

    # Final formatted output
    return {
        "transaction": tx,
        "case": case,
        "graph": graph,
        "recovery": recovery
    }
