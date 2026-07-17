**SENTINEL**

Real-Time Fraud Response System

**BACKEND LEAD**

**Dev 1**

_Risk Engine · Case Logic · Graph Engine · Recovery Engine_

| Time Budget | ~16 hrs active |
| --- | --- |

Hackathon Edition | 19-Hour Build | Version 2.0

**Role Overview**

As Backend Lead, you are responsible for the intelligence core of SENTINEL. You own the data pipeline from raw transaction input all the way to scored, graph-tracked, recovery-estimated case outputs. The entire system's analytical credibility rests on your modules.

**Core Responsibilities**

*   Risk Scoring Engine — 4-factor weighted formula with configurable weights
*   Case Logic — detection, creation, escalation, status transitions
*   Graph Engine — per-case directed acyclic graph (DAG) of account hops
*   Recovery Engine — real-time recoverable amount tracking per case
*   Data Models — define and own all Python data structures used across the system

**19-Hour Timeline**

| Hours | Phase | Tasks | Status |
| --- | --- | --- | --- |
| 0 – 2 hr | Team Setup | Repo init, FastAPI scaffold, config.py, define data models (Transaction, Case, AccountNode, ActionLog) | 🟢 Active |
| 2 – 5 hr | Scoring Engine | Implement 4-factor risk scoring: new_receiver, amount_deviation, time_anomaly, call_flag. Weighted sum capped at 100. Return risk_score + risk_factors[]. | 🟢 Active |
| 5 – 7 hr | Case Logic | Case creation (score≥40), case escalation to HIGH_RISK (score≥70 or 2nd hop), status state machine (NEW→HIGH_RISK→ACTIONED→MONITORING→CLOSED/CLOSED_FP) | 🟢 Active |
| 7 – 10 hr | Graph + Recovery | Graph Engine: build per-case DAG, add nodes/edges on each hop, support EC-02 backfill. Recovery Engine: compute recoverable_amount from chain node balances, update on freeze/withdrawal. | 🟢 Active |
| 10 – 14 hr | Integration Support | Expose scoring/case/graph/recovery as internal Python modules. Support Dev 2 in wiring REST endpoints. Fix integration bugs. Assist frontend with mock data. | 🔵 Collab |
| 14 – 17 hr | Hop Decay + Queue | Implement B4.2 hop risk decay (0.75^n). Implement B4.4 urgency_score formula. Feed into priority queue maintained by Dev 2. | 🟢 Active |
| 17 – 19 hr | E2E + Testing | Run all 5 test scenarios (SC-01–SC-05) and edge cases (EC-01–EC-04). Fix scoring bugs. Validate assertion: all HIGH_RISK alerts have ≥2 factors. | 🔵 Collab |

**Module Specifications**

**Risk Scoring Engine — scoring\_engine.py**

Implement the following function as the core entry point:

| score_transaction(tx: dict, account: dict) → dict Returns: { risk_score: int, risk_factors: list[dict], threshold: str } |
| --- |

**Factor Weights**

| Factor | Weight | Score Logic | Config Key |
| --- | --- | --- | --- |
| new_receiver | 0.35 | 100 if receiver not in sender tx history, else 0 | W_NEW_RECEIVER |
| amount_deviation | 0.30 | min(100, (tx_amount / avg_monthly_tx) × 25) | W_AMOUNT_DEV |
| time_anomaly | 0.20 | 100 if hour(timestamp) ∈ [22:00–06:00 local], else 0 | W_TIME_ANOMALY |
| call_flag | 0.15 | 100 if telecom flagged number in last 2h, else 0 | W_CALL_FLAG |
| ⚠ All weights must be loaded from config.py — never hardcoded in scoring_engine.py. This allows judges to adjust live during demo. |
| --- |

**Case Logic — case\_manager.py**

**State Machine**

| From | To | Trigger | Side Effect |
| --- | --- | --- | --- |
| — | NEW | score ≥ 40 on any transaction | Case created, WS notify |
| NEW | HIGH_RISK | score ≥ 70 OR 2nd hop detected | Priority queue updated, timer starts |
| HIGH_RISK | ACTIONED | Any freeze/flag/alert action taken | Recovery recalculated, WS broadcast |
| ACTIONED | MONITORING | All HIGH_RISK nodes frozen AND no new hops for 10 min | Police alerted, passive watch |
| Any | CLOSED_FP | Operator clicks 'Mark as False Positive' | FP log created, removed from queue |

**Graph Engine — graph\_engine.py**

Maintain per-case directed graph as a Python dict of nodes and edges in memory.

*   add\_node(case\_id, account\_id, account\_data) — add or update account node
*   add\_edge(case\_id, from\_acc, to\_acc, tx\_id, amount) — add directed transaction edge
*   get\_graph(case\_id) → { nodes\[\], edges\[\] } — returns serialisable graph for API
*   backfill\_chain(case\_id, tx\_history) — reconstruct chain from history (EC-02 support)

**Recovery Engine — recovery\_engine.py**

For each case, iterate chain nodes and sum balances of non-withdrawn nodes:

| recoverable_amount = Σ current_balance_sim for all nodes where status != 'withdrawn' recovery_pct = (recoverable_amount / total_fraud_amount) × 100 |
| --- |

*   Trigger recalculation: on every new hop, freeze action, or withdrawal event
*   Withdrawn nodes: set current\_balance\_sim = 0, status = 'withdrawn'
*   Frozen nodes: count balance as recovered (status = 'frozen')

**Hop Risk Decay (B4.2)**

| hop_risk = origin_score × decay_factor ^ hop_number decay_factor = 0.75 (configurable in config.py as DECAY_FACTOR) |
| --- |

Example with origin\_score = 87:

| Hop | Account | Decayed Score | Threshold |
| --- | --- | --- | --- |
| 0 (origin) | ACC-1001 | 87 | HIGH_RISK (≥70) |
| 1 | ACC-2001 | 65.3 | MEDIUM (40–69) |
| 2 | ACC-3001 | 49.0 | MEDIUM (40–69) |
| 3 | ACC-4001 | 36.7 | LOW (<40) — log only |

**Deliverables Checklist**

| Complete all items before Hour 17. Mark each as DONE on the shared tracker. |
| --- |

*   scoring\_engine.py — 4 factors, weighted sum, capped at 100
*   All weights loaded from config.py
*   risk\_factors\[\] returned with name, weight, value, contribution per factor
*   Thresholds applied: HIGH\_RISK ≥70 / MEDIUM 40–69 / LOW <40
*   case\_manager.py — full state machine with 6 transitions
*   graph\_engine.py — add\_node, add\_edge, get\_graph, backfill\_chain
*   recovery\_engine.py — recoverable\_amount calculated correctly
*   Hop decay implemented with configurable DECAY\_FACTOR
*   All SC-01–SC-05 test scenarios pass manually
*   All 4 edge cases (EC-01–EC-04) validated

**Integration Handoff**

Your modules are consumed by Dev 2's REST/WS layer. Agree on interfaces by Hour 5:

| Your Module | Called By (Dev 2) | Interface Agreement |
| --- | --- | --- |
| scoring_engine.score_transaction() | POST /transaction handler | Returns dict with risk_score, risk_factors, threshold |
| case_manager.process_scored_tx() | POST /transaction handler | Returns case object (created or updated) |
| graph_engine.get_graph() | GET /graph/:caseId | Returns { nodes[], edges[] } JSON-serialisable |
| recovery_engine.recalculate() | POST /action/freeze handler | Returns { recoverable_amount, recovery_pct } |
| 🚨 Critical: Do NOT put HTTP request handling code inside your engine modules. Keep logic pure Python so Dev 2 can wrap them independently. |
| --- |