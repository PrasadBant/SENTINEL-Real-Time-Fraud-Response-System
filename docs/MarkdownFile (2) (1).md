**REAL-TIME FRAUD RESPONSE SYSTEM**

Product Requirements Document & Functional Requirements Document

_Project Codename: SENTINEL_

Version 2.0 | Hackathon Edition | 20-Hour Build

_Enhanced for Industry Credibility & Realism_

| ⚠ SIMULATION DISCLAIMER |
| --- |
|  |
| This system is a simulation of real-world fraud response workflows, designed to demonstrate |
| feasibility and system design — NOT a production-ready deployment. All transaction data, |
| account records, agency responses, and recovery figures are synthetically generated. |
| No real banking, telecom, or law-enforcement APIs are integrated. All numerical benchmarks |
| cited from industry context are approximate estimates from public reports and may vary |
| significantly by institution, geography, and fraud type. |
| PART A — PRODUCT REQUIREMENTS DOCUMENT (PRD) |
| --- |

# A0. Data Sources & Assumptions

All quantitative claims in this document are drawn from publicly available industry reports and regulator disclosures. Where precise figures are unavailable or disputed, ranges are provided. Simulation parameters are configurable and do not imply empirical accuracy.

| Claim / Parameter | Source Basis | Simulation Value | Confidence |
| --- | --- | --- | --- |
| Volume of digital payment fraud | RBI Annual Report 2022-23; NPCI public disclosures | Not simulated | Moderate — category-level data |
| Detection-to-freeze latency | Practitioner estimates; no public benchmark exists | Simulated as 4–8 hrs (worst case) | Low — institution-specific |
| Fund recovery window | Practitioner estimates from incident post-mortems | Simulated as 20 min from hop | Low — highly variable |
| Multi-hop chain depth | FIU-IND typology reports (public) | 2–4 hops in simulation | Moderate — pattern-based |
| Risk scoring weights | Heuristic — no empirical calibration | Configurable in config.py | Low — demo-only |
| Golden window duration | Assumed; not empirically validated | 20 min default, -1 min/hop | Low — illustrative only |
| All simulation parameters are defined in a central config file (config.py / config.js). |
| --- |
| Judges and evaluators should treat all specific numbers as illustrative defaults, not validated benchmarks. |
| The system is designed so that any parameter can be adjusted without code changes. |

# A1. Problem & Context

Digital payment fraud in India has grown significantly alongside the rapid expansion of UPI, NEFT, and IMPS infrastructure. Regulators including RBI and NPCI have published frameworks (e.g., the Digital Payments Security Controls Directions, 2021) that require banks to implement fraud monitoring, but the operative challenge remains coordination speed — not detection capability.

The core failure mode is not that fraud goes undetected — most large banks have transaction monitoring systems. The failure is that detection does not translate into rapid, coordinated response. Funds move across accounts faster than inter-institutional communication channels allow. By the time a fraud signal is acted upon, the money has often moved beyond the first mule account.

| FRAMING NOTE: Specific latency figures (hours to freeze, minutes to withdrawal) vary widely |
| --- |
| across institutions, fraud types, and geographies. The figures used in this simulation are |
| conservative practitioner estimates, not published benchmarks. SENTINEL's design addresses |
| the structural coordination gap — irrespective of the exact latency numbers. |

## Context: Why Response Fails Today

| Pain Point | Current State | SENTINEL Simulates |
| --- | --- | --- |
| Detection-to-action gap | Estimated hours due to manual escalation paths | < 2 min via automated action engine (simulated) |
| Fund tracking | Per-bank visibility only; no cross-institution graph | Live graph across all simulated accounts in session |
| Inter-agency coordination | Manual calls, email, or MoU-based escalation | Simulated API events for Bank, Telecom, Police |
| Recovery estimation | Not computed in real time at most institutions | Live recoverable amount updated per hop/action |
| Explainability | Alerts often lack human-readable reasoning | Weighted factor breakdown per alert, always visible |

# A2. Users & Stakeholders

| Role | Goal | Key Screen | Primary Actions |
| --- | --- | --- | --- |
| Fraud Analyst (Bank) | Triage alerts, decide freeze | Alert Dashboard + Graph View | Freeze, Flag, Escalate |
| Police Operator (Cyber Cell) | Initiate legal freeze, track case | Case List + Action Panel | Case Alert, Coordinate |
| Telecom Supervisor | Block SIM/OTP exploit | Alert Dashboard | Flag Number |
| System (Simulator) | Generate realistic fraud flows | N/A (backend) | Auto-generates transactions |

## Secondary Stakeholders

*   Bank Management — recovery metrics and audit logs for post-incident review
*   Regulatory Bodies (RBI, NPCI) — explainability trail for flagged transactions
*   Hackathon Demo Judges — a compelling, self-explanatory real-time UI

# A3. Goals & Non-Goals

## Goals

*   Demonstrate end-to-end fraud response in under 2 minutes from detection to simulated freeze (within the simulation environment)
*   Track multi-hop fund flow (A → B → C → D) as a live graph per case
*   Compute and display recoverable fund amount in real time within the simulation
*   Simulate coordination between Bank, Telecom, and Police via mock API events with full logging
*   Produce a demo-ready UI that is self-explanatory to a non-technical audience
*   Every alert must carry an explainability breakdown — no opaque scores

## Non-Goals

*   No real bank, telecom, or government API integration — all external calls are mocked
*   No ML or statistical model — rule-based scoring only, with configurable weights
*   No persistent storage across sessions — in-memory state is reset on restart
*   No authentication, role-based access control, or multi-user session management
*   No mobile-responsive design — optimised for desktop demo presentation
*   No enforcement capability — the system cannot legally freeze any real account
*   No cross-institution data sharing — all accounts exist within the simulation namespace

# A4. User Stories with Acceptance Criteria

## US-01: Analyst sees live transaction feed

| As a Fraud Analyst, I want a live stream of transactions flagged with risk scores, |
| --- |
| so I can identify suspicious activity without manually reviewing all transactions. |
|  |
| AC1: Feed refreshes within 1 second of a new simulated transaction entering the pipeline. |
| AC2: Each row shows: TxID, Amount, Sender → Receiver, Channel, Risk Score (0–100), Top Reason. |
| AC3: Score ≥ 70 → red row; 40–69 → amber; < 40 → green. Color applied to Score badge. |
| AC4: Feed is capped at 100 rows; older rows scroll off without page reload. |

## US-02: Analyst sees explainable alert

| As a Fraud Analyst, I want to click any alert and see why it was flagged, |
| --- |
| so I can make a confident, defensible decision to freeze or dismiss. |
|  |
| AC1: Alert detail panel shows each scoring factor: name, weight, triggered value, contribution. |
| AC2: Human-readable reason string is generated (e.g., 'New receiver [+35] + Amount 4.2x avg [+30]'). |
| AC3: Factors listed in descending order of contribution. |
| AC4: Panel closes cleanly and returns analyst to feed without state loss. |

## US-03: Analyst tracks fund flow graph

| As a Fraud Analyst, I want to see a live money flow graph for a case (A→B→C), |
| --- |
| so I can understand chain depth and identify which node to act on first. |
|  |
| AC1: Graph renders nodes (accounts) and directed edges (transactions, labeled with amount). |
| AC2: New hops animate into the graph within 2 seconds of being scored. |
| AC3: Frozen nodes rendered with distinct visual state (grey fill + lock icon). |
| AC4: Recoverable amount displayed above graph and updates on each freeze action. |

## US-04: Analyst takes action (freeze / flag)

| As a Fraud Analyst, I want to click 'Freeze Account' or 'Flag Number' on any node, |
| --- |
| so the system logs the action and updates case status instantly. |
|  |
| AC1: Action button triggers a simulated API call within 500ms and returns ACK/NACK. |
| AC2: Log entry created: timestamp, action type, target, actor role, simulated API response. |
| AC3: Case status updates on action (e.g., HIGH_RISK → ACTIONED) and broadcasts via WebSocket. |
| AC4: Recovery estimate recalculates within 1 second of freeze action. |

## US-05: Police Operator receives case alert

| As a Police Operator, I want a structured case alert with key evidence, |
| --- |
| so I can initiate coordination without waiting for a bank call. |
|  |
| AC1: Case alert includes: Case ID, fraud amount, accounts in chain, risk score, timestamp. |
| AC2: Alert appears in Police Operator view within 30 seconds of case creation in simulation. |
| AC3: Operator acknowledges with one click; this triggers a simulated Police API event and log entry. |

## US-06: Operators see Golden Time Window

| As any operator, I want a visible countdown to likely next hop or cash-out, |
| --- |
| so I can prioritise which cases to action first. |
|  |
| AC1: Each active case displays a countdown timer (minutes remaining to simulated next hop). |
| AC2: Timer colour: green > 15 min, amber 5–15 min, red < 5 min. |
| AC3: Timer is derived from configurable hop velocity; default = 20 min from creation, -1 min per hop. |
| AC4: Timer expiry does not crash or freeze the UI; case transitions to MONITORING state. |

# A5. Key Features Mapped to Problem

| Feature | Problem It Addresses | Output / Deliverable |
| --- | --- | --- |
| Transaction Simulator | No real data source in hackathon | Continuous event stream; ≥ 2 simultaneous fraud cases |
| Risk Scoring Engine | Slow manual review; no single score | 0–100 score + contributing factors in < 100ms |
| Multi-Chain Graph Tracker | No visibility of fund movement across accounts | Live directed graph per case (A→B→C) |
| Action Recommendation Engine | No clear action pathway from alert | Clickable freeze/flag/alert buttons per case node |
| Recovery Estimator | No real-time sense of recoverable amount | ₹ recoverable displayed and updated live |
| Golden Time Window | No prioritisation mechanism | Countdown timer per case; priority queue re-sorts on it |
| Case Management | Fragmented view across fraud events | Case ID, status, timeline, linked accounts, risk level |
| Explainability Layer | Analyst distrust of opaque alerts | Factor breakdown with weights visible on every alert |
| Coordination Layer | Siloed agencies, no shared signal | Simulated Bank/Telecom/Police API events + full log |

# A6. Success Metrics

All metrics below are measured within the simulation environment. Those labelled \[SIM\] are not empirically validated against real-world benchmarks and should be interpreted as design targets for the demo scenario.

| Metric | Target | How Measured | Label |
| --- | --- | --- | --- |
| Time-to-Detect | ≤ 5 seconds | Delta: tx_created_at → alert_rendered_at (logged per transaction) | [SIM] |
| Time-to-Action | ≤ 2 minutes | Delta: case_created_at → first_action_taken_at (per case log) | [SIM] |
| Recovery Rate | ≥ 60% of fraud amount frozen before terminal hop | frozen_amount / total_fraud_amount per closed case | [SIM] |
| False Positive Rate | ≤ 20% of HIGH_RISK cases dismissed by operator | FP_cases / total_HIGH_RISK_cases per demo session | [SIM] |
| Coordination Event Coverage | 100% of actions produce a log entry | action_log row count == button click count (automated assert) | [SIM] |
| UI Responsiveness | All updates render within 2 seconds of server event | Browser DevTools network timing; manual verification | [SIM] |
| Explainability Coverage | 100% of alerts have ≥ 2 factor entries | Automated: assert len(risk_factors) >= 2 per scored tx | [SIM] |
| NOTE: 'False Positive Rate' in this simulation is operator-driven — an analyst clicks 'Mark as False Positive'. |
| --- |
| There is no ground-truth label set. In a production system, this metric would be measured against |
| confirmed fraud case outcomes from legal or bank adjudication records — a process taking days to weeks. |

# A7. Demo Scenario (Step-by-Step)

## Setup: Two Simultaneous Fraud Chains

| Case 1 — UPI Mule Chain: |
| --- |
| Victim Acc #1001 sends ₹2,00,000 to mule Acc #2001 (new receiver, amount ~4x monthly avg). |
| Acc #2001 → Acc #3001 within simulated 4 minutes (rapid hop). Acc #3001 → simulated cash-out. |
|  |
| Case 2 — SIM Swap Pattern (simultaneous): |
| Acc #1002 → Acc #2002, flagged with telecom call-activity signal. |
| Demonstrates parallel case handling and prioritisation by golden timer. |
|  |
| Both cases run concurrently to demonstrate multi-case tracking capability. |

## Demo Walk-Through

1.  Open Live Feed — transactions stream in at configurable interval (default: every 3–5 seconds).
2.  A row turns RED — Risk Score 87 on Acc #1001→#2001. Presenter clicks it.
3.  Alert Detail opens — shows: 'New Receiver (+35pts), Amount 4.2x avg (+30pts), Off-hours (+15pts), Total = 80+'.
4.  Graph View opens — Acc #1001→#2001, ₹2L on edge. Golden Timer: 18 min. Recoverable: ₹2,00,000.
5.  Presenter clicks 'Freeze #2001' — Action Panel logs: Bank API \[ACK\], ₹1,85,000 frozen.
6.  Recovery Estimator updates: ₹2,00,000 fraud | ₹1,85,000 recoverable (92.5%).
7.  Case 2 triggers — Telecom alert fires. Police Case Alert appears in Police view.
8.  Police Operator clicks 'Acknowledge Case' — Police API event logged with timestamp.
9.  Presenter shows Action Log — full audit trail of all events, exportable as JSON.
10.  Case 2 timer hits red — demonstrates urgency prioritisation for parallel cases.

# A8. Real-World Constraints

The following constraints apply to any real-world deployment of a system like SENTINEL. They are explicitly out of scope for this hackathon prototype but are documented here to demonstrate awareness of production-readiness requirements.

## Legal & Regulatory Constraints

| Account Freezing Authority: Under Indian law (Section 17A, Prevention of Money Laundering Act), |
| --- |
| only a competent authority (court, ED, police officer above DSP rank) may direct an account freeze. |
| A bank may voluntarily hold a suspicious transaction for up to 3 working days (RBI directive) pending |
| legal direction, but a permanent or extended freeze requires judicial or executive authority. |
|  |
| Implication for SENTINEL: The 'Freeze Account' action in this system is a simulated hold request, |
| NOT a legally enforceable freeze. In production, this would initiate a compliance workflow, |
| not an instant account lock. |

## Banking System Constraints

| • Real-time inter-bank communication is not universal. The RBI's 'Fraud Registry' (operationalised |
| --- |
| under the Digital Payment Security Controls Directions) is the closest real analogue, but it is |
| asynchronous and not a real-time transaction-blocking mechanism. |
|  |
| • Core Banking System (CBS) integration for account freeze typically goes through SFMS/SWIFT messaging |
| or proprietary bank APIs — none of which are publicly accessible or free. |
|  |
| • Multi-hop tracking across banks requires data-sharing agreements (MoUs) between institutions, |
| which are not standardised in India as of 2024. |

## Telecom Coordination Challenges

| • SIM swap detection requires access to HLR (Home Location Register) queries, which telecom providers |
| --- |
| do not expose publicly. TRAI has mandated some fraud-SMS controls but not real-time API access. |
|  |
| • Number flagging in SENTINEL is simulated. In reality, a 'Do Not Disturb' or fraud-flag |
| request must go through TRAI's regulated channel or a bilateral agreement with the operator. |

## Privacy & Compliance Considerations

| • Any real deployment must comply with RBI's Master Direction on IT governance, DPDP Act 2023 |
| --- |
| (Digital Personal Data Protection), and PCI-DSS if card data is involved. |
|  |
| • Storing transaction-level data for fraud analysis without explicit data minimisation and |
| retention policies would be non-compliant. |
|  |
| • SENTINEL (simulation) stores no real PII. A production system would require data masking, |
| encryption at rest, and strict access controls before handling real transaction data. |

# A9. Risks & Mitigations

| Risk | Severity | Probability | Mitigation |
| --- | --- | --- | --- |
| Graph rendering lags with many hops | High | Medium | Cap chain depth at 5 hops; use Cytoscape.js with WebWorker rendering |
| Simulator produces unrealistic patterns | Medium | Low | Pre-define 3 scripted fraud scenarios; hardcode timing; seed with realistic amounts |
| WebSocket sync breaks UI state | High | Medium | Fallback to 2-second HTTP polling if WS disconnects; show reconnect indicator |
| Team runs short on time on UI polish | Medium | High | Backend + logic first; UI last; use shadcn/ui or Ant Design component library |
| Demo cases look identical (low visual impact) | Medium | Medium | Script 2 visually distinct patterns: different amounts, chain depth, and urgency timers |
| Judges question credibility of numbers | High | Medium | Pre-frame all figures as simulation defaults; reference A0 (Data Sources) explicitly |
| PART B — FUNCTIONAL REQUIREMENTS DOCUMENT (FRD) |
| --- |

# B1. System Architecture

## Layer Overview

| Layer | Component | Responsibility |
| --- | --- | --- |
| Input | Transaction Simulator | Emits synthetic transactions on a timer; supports scripted fraud patterns |
| Processing | Risk Scoring Engine | Applies rule weights; produces 0–100 score + human-readable reasons |
| Processing | Graph Engine | Maintains per-case directed acyclic graph of account hops; computes chain depth |
| Processing | Recovery Engine | Tracks frozen vs. in-flight funds per chain node; recomputes on every action |
| Decision | Action Engine | Receives operator commands; triggers simulated Bank/Telecom/Police API calls |
| Decision | Priority Queue | Ranks cases by urgency score (risk × time decay); re-sorts every 30s |
| Output | WebSocket Broadcaster | Pushes tx_scored, case_updated, action_taken events to React frontend |
| Output | REST API | Serves all case, graph, and action endpoints; auto-documented via FastAPI /docs |

## Component Communication Flow

| Simulator → POST /transaction → FastAPI (Input Layer) |
| --- |
| FastAPI → Risk Engine → Graph Engine → Recovery Engine → Priority Queue |
| FastAPI → WebSocket broadcast → React UI (live updates) |
| React UI → POST /action/freeze | /action/flag | /action/alert → FastAPI |
| FastAPI → Mock Bank / Telecom / Police API (in-process) → Action Log |
| FastAPI → WebSocket broadcast (case_updated) → React UI (state refresh) |

# B2. Data Models (JSON)

## Transaction

| { |
| --- |
| "tx_id": "TX-20240515-001", |
| "timestamp": "2024-05-15T14:32:00Z", |
| "sender_account": "ACC-1001", |
| "receiver_account":"ACC-2001", |
| "amount": 200000, |
| "currency": "INR", |
| "channel": "UPI", // UPI | NEFT | IMPS | RTGS |
| "is_scripted": true, // true = part of a defined fraud scenario |
| "is_fraud": null, // null = unscored; true/false after scoring |
| "risk_score": null, |
| "risk_factors": [], |
| "case_id": null // populated when linked to a case |
| } |

## Account Node

| { |
| --- |
| "account_id": "ACC-2001", |
| "account_type": "savings", // savings | current | wallet |
| "bank": "Bank_B", |
| "is_new_receiver": true, |
| "avg_monthly_tx_amount": 50000, // used for amount deviation scoring |
| "status": "active", // active | frozen | flagged | withdrawn |
| "linked_cases": ["CASE-001"], |
| "tx_history": ["TX-20240515-001"], |
| "current_balance_sim": 185000 // simulation only; not real bank data |
| } |

## Case

| { |
| --- |
| "case_id": "CASE-001", |
| "created_at": "2024-05-15T14:32:05Z", |
| "status": "HIGH_RISK", |
| // NEW | HIGH_RISK | ACTIONED | MONITORING | CLOSED | CLOSED_FP |
| "risk_level": 87, |
| "total_fraud_amount": 200000, |
| "recoverable_amount": 185000, |
| "golden_window_minutes": 18, |
| "origin_account": "ACC-1001", |
| "chain": ["ACC-1001", "ACC-2001", "ACC-3001"], |
| "transactions": ["TX-001", "TX-002"], |
| "actions_taken": [], |
| "is_scripted": true, // true = part of demo scenario |
| "timeline": [ |
| { "at": "2024-05-15T14:32:05Z", "event": "Case created", "actor": "system" } |
| ] |
| } |

## Action Log Entry

| { |
| --- |
| "action_id": "ACT-0001", |
| "case_id": "CASE-001", |
| "action_type": "FREEZE_ACCOUNT", |
| // FREEZE_ACCOUNT | FLAG_NUMBER | ALERT_BANK | ALERT_POLICE | MARK_FP |
| "target": "ACC-2001", |
| "actor_role": "analyst", |
| "timestamp": "2024-05-15T14:33:44Z", |
| "api_called": "mock://bank_b/freeze", |
| "api_response": { "status": "ACK", "frozen_amount": 185000, "latency_ms": 120 }, |
| "notes": "Manual freeze — risk score 87, golden window 18 min remaining" |
| } |

# B3. Simulated API Specification

| Endpoint | Method | Description | Key Response Fields |
| --- | --- | --- | --- |
| /transaction | POST | Accept new transaction; trigger full scoring pipeline | tx_id, risk_score, risk_factors, case_id |
| /cases | GET | Return all active cases with status and risk level | case_id, status, risk_level, recoverable_amount |
| /cases/:caseId | GET | Full case detail: chain, timeline, actions | All Case fields; graph edge list |
| /graph/:caseId | GET | Nodes + edges for graph rendering | nodes[], edges[], recoverable_amount |
| /action/freeze | POST | Freeze an account; log action; update recovery | action_id, frozen_amount, recovery_update |
| /action/flag | POST | Flag a phone/account; trigger mock Telecom API | action_id, telecom_ack |
| /action/alert | POST | Send case alert to Police mock endpoint | action_id, police_ack, case_status |
| /actions/log | GET | Full audit trail for all cases | action_log[] sorted by timestamp desc |
| /ws | WS | Real-time events: tx_scored, case_updated, action_taken | Streamed JSON event objects |

## Sample: POST /action/freeze

| Request Body: |
| --- |
| { "case_id": "CASE-001", "account_id": "ACC-2001", "actor_role": "analyst" } |
|  |
| Response 200: |
| { |
| "action_id": "ACT-0001", |
| "status": "success", |
| "frozen_amount": 185000, |
| "bank_ack": "mock://bank_b ACK at 14:33:44 — latency 120ms", |
| "recovery_update": { "recoverable_amount": 185000, "pct": 92.5 } |
| } |
|  |
| Response 422 (if account already frozen): |
| { "error": "ALREADY_FROZEN", "account_id": "ACC-2001" } |

# B4. Core Logic

## B4.1 Risk Scoring Formula

| Final Risk Score = Σ (factor_score × weight) [capped at 100] |
| --- |
|  |
| Factor Weight Score Logic |
| ───────────────────────────────────────────────────────────────── |
| new_receiver 0.35 100 if receiver not in sender's tx history; else 0 |
| amount_deviation 0.30 min(100, (tx_amount / avg_monthly_tx) × 25) |
| time_anomaly 0.20 100 if hour(tx_timestamp) ∈ [22:00–06:00 local]; else 0 |
| call_flag 0.15 100 if telecom flagged this number in last 2h; else 0 |
|  |
| Thresholds: |
| Score ≥ 70 → HIGH RISK — create/escalate case; recommend freeze |
| Score 40–69 → MEDIUM — create case; alert analyst; monitor |
| Score < 40 → LOW — log only; no case created |
|  |
| All weights are configurable in config.py without code changes. |
| Weights are heuristic; no empirical calibration has been performed. |

## B4.2 Risk Propagation Across Chain (Hop Decay)

| When a new transaction extends an existing case chain, downstream nodes inherit decayed risk: |
| --- |
|  |
| hop_risk = origin_score × decay_factor ^ hop_number |
| decay_factor = 0.75 (configurable in config.py) |
|  |
| Example — Case CASE-001, origin score = 87: |
| Hop 1 (ACC-2001): 87 × 0.75¹ = 65.3 → MEDIUM → watch |
| Hop 2 (ACC-3001): 87 × 0.75² = 49.0 → MEDIUM → alert |
| Hop 3 (ACC-4001): 87 × 0.75³ = 36.7 → LOW → log only |
|  |
| Rationale: Each additional hop introduces uncertainty about whether funds |
| still belong to the original fraud event. Decay reflects this analytically. |

## B4.3 Recovery Estimation Logic

| For each case, iterate chain nodes in order: |
| --- |
|  |
| total_fraud_amount = amount at origin transaction |
| recoverable_amount = Σ current_balance_sim for all non-withdrawn, non-terminal nodes |
|  |
| Node is 'terminal/withdrawn' if: status = withdrawn OR simulated_withdrawal_event received. |
| Node is 'frozen' if: status = frozen (balance locked; counts as recovered). |
| Node is 'in-flight' if: funds received but not yet forwarded or withdrawn. |
|  |
| Recovery % = (recoverable_amount / total_fraud_amount) × 100 |
|  |
| Update triggers: every new hop transaction, every freeze/flag action, every withdrawal event. |
| Note: 'balance' is a simulation construct, not a real bank balance. |

## B4.4 Priority Queue for Actions

| urgency_score = case_risk_score × (1 + 1 / max(golden_window_minutes, 1)) |
| --- |
|  |
| Cases are sorted descending by urgency_score. |
| Golden window = simulated minutes until next likely hop or cash-out. |
| Default: 20 minutes from case creation, minus 1 minute per hop observed. |
|  |
| Action Panel always surfaces top-3 cases by urgency with one-click actions. |
| Queue re-sorts every 30 seconds OR on any case state change (via WS event). |
|  |
| Tie-breaking: higher risk_score wins. Further tie: earlier created_at wins. |

# B5. Case State Transitions

| From | To | Trigger Condition | Side Effect |
| --- | --- | --- | --- |
| — | NEW | Risk score ≥ 40 on any transaction | Case created; analyst notified via WS event |
| NEW | HIGH_RISK | Risk score ≥ 70 OR second hop detected in chain | Priority queue updated; golden timer starts |
| NEW / HIGH_RISK | ACTIONED | Any freeze, flag, or alert action taken by operator | Action logged; recovery estimate recalculated; WS broadcast |
| ACTIONED | MONITORING | All HIGH_RISK nodes frozen AND no new hops for 10 min | Police alerted; case enters passive watch mode |
| MONITORING | CLOSED | Manual operator close OR golden window fully expired | Final recovery % logged; case marked archived |
| Any | CLOSED_FP | Operator clicks 'Mark as False Positive' | Score factors logged for review; case removed from active queue |

# B6. UI Specification

## Screen 1 — Live Transaction Feed

*   Columns: TxID | Timestamp | Channel | Sender → Receiver | Amount | Risk Score | Top Reason | Action
*   Risk Score: coloured badge (Red ≥70 / Amber 40–69 / Green <40)
*   Rows animate in from top (newest first); maximum 100 rows; smooth scroll
*   Click any row → opens Alert Detail side panel (no page navigation)
*   Header bar: tx/min rate | active cases count | total at-risk amount

## Screen 2 — Alert Dashboard

*   Card grid, sorted descending by urgency score
*   Each card: Case ID | Risk Score | Chain depth | Fraud Amount | Recoverable | Golden Timer
*   Timer colour: green > 15 min, amber 5–15 min, red < 5 min
*   Click card → expands inline to show chain accounts + factor breakdown
*   Quick Action buttons per card: Freeze Lead Node | Alert Police | Escalate

## Screen 3 — Graph View (per Case)

*   Library: Cytoscape.js — lightweight, no server dependency, supports live re-layout
*   Nodes: coloured by status (active = blue, frozen = grey + lock icon, flagged = orange)
*   Directed edges: labelled with amount (₹) and transaction timestamp
*   New hops animate in; frozen nodes update visually without full re-render
*   Side panel: Recovery progress bar | Chain stats | Per-node action buttons

## Screen 4 — Action Panel

*   Persistent right sidebar (visible on Alert Dashboard and Graph View)
*   Surfaces top-3 urgent cases with one-click: Freeze | Flag | Alert Police
*   Each action shows confirmation inline: 'Bank\_B ACK — ₹1.85L frozen \[120ms\]'
*   Scrollable action log stream below: latest 20 events with timestamps

## Screen 5 — Case List

*   Table: Case ID | Status | Risk | Chain Depth | Fraud Amt | Recovery % | Created At | Actions
*   Filterable by status: NEW / HIGH\_RISK / ACTIONED / MONITORING / CLOSED / CLOSED\_FP
*   Click row → full case detail (same as Alert Dashboard card expand)
*   Export button → downloads action log as JSON for audit trail demonstration

# B7. Event Flow (End-to-End)

| Step | Stage | Process | Output |
| --- | --- | --- | --- |
| 1 | Simulator emits | POST /transaction with scripted or random tx payload | Transaction object stored in memory |
| 2 | Scoring | Apply 4 rule weights → weighted sum → cap at 100 | risk_score + risk_factors[] with contributions |
| 3 | Case logic | score ≥ 40: create or find existing case; link tx to chain | Case object created or updated |
| 4 | Graph update | Add/update node and directed edge in case DAG | Graph state updated in memory |
| 5 | Recovery calc | Recompute recoverable_amount across all chain nodes | Updated recovery figures per case |
| 6 | Priority sort | Re-sort priority queue by urgency_score | Updated top-3 list for Action Panel |
| 7 | WS broadcast | Emit tx_scored + case_updated events to all connected clients | React UI re-renders feed, dashboard, graph |
| 8 | Operator action | POST /action/freeze → Action Engine validates → mock API call | Simulated ACK/NACK + action log entry |
| 9 | State change | Case status updated (e.g., HIGH_RISK → ACTIONED) | WS broadcast case_updated to all clients |
| 10 | Recovery update | Recalculate recovery post-freeze; update graph node status | Updated % pushed to UI within 1 second |

# B8. Edge Cases & Handling

## EC-01: Multiple Parallel Fraud Chains

| Scenario: Two unrelated fraud cases active simultaneously. |
| --- |
| Handling: |
| • Each case maintains its own isolated graph under a unique case_id namespace. |
| • Priority queue ranks both cases independently on urgency_score. |
| • WS events include case_id; frontend filters per-case without cross-contamination. |
| • Simulator scripts at least 2 overlapping cases in the default demo scenario. |

## EC-02: Late Detection (Post First Hop)

| Scenario: First hop already occurred before detection (e.g., #1001→#2001→#3001; #3001 detected first). |
| --- |
| Handling: |
| • Backfill: when #3001 is scored, the engine walks back tx_history to reconstruct the origin. |
| • Chain is rebuilt retroactively; all prior nodes added to the case graph. |
| • Golden window = 20 min − (simulated minutes since origin tx timestamp). |
| • If window already expired, case transitions immediately to MONITORING state. |

## EC-03: Partial Recovery

| Scenario: Freeze on Hop-2 node, but Hop-3 has already performed a simulated withdrawal. |
| --- |
| Handling: |
| • Simulator emits a 'withdrawal_event' for terminal nodes after a configurable delay. |
| • Recovery engine sets current_balance_sim = 0 for withdrawn nodes. |
| • Recovery % reflects only frozen nodes; withdrawn nodes are shown as 'Lost'. |
| • UI shows: 'Recovered: ₹1.8L | Lost to withdrawal: ₹0.2L | Total: ₹2.0L'. |

## EC-04: False Positive Handling

| Scenario: High score on a legitimate unusual transaction (e.g., property purchase, salary credit). |
| --- |
| Handling: |
| • Score 40–69 (MEDIUM) triggers 'warn-only' — no auto-action, analyst review required. |
| • Analyst can click 'Mark as False Positive'; case transitions to CLOSED_FP. |
| • FP log records: contributing factors, weights, and operator rationale field. |
| • No auto-freeze without operator confirmation; this design choice prevents harm to real users. |
| • FP rate tracked per session (see A6 Success Metrics). |

# B9. Design Decisions & Trade-offs

This section documents the key architectural choices made for the hackathon build and the reasoning behind each decision. These trade-offs are explicit and intentional — not oversights.

## Rule-Based Scoring vs. ML

| Decision: Use deterministic rule-based scoring with configurable weights. |
| --- |
|  |
| Why not ML? |
| • No labelled training dataset available in a 20-hour build. |
| • ML models require validation, calibration, and explainability wrappers — all expensive to build. |
| • A rules engine produces 100% explainable outputs by construction, which is a demo requirement. |
| • Rules can be adjusted live during the demo without retraining. |
|  |
| Trade-off accepted: Rule-based systems have lower recall on novel fraud patterns. |
| This is acceptable for a simulation demo, not a production fraud engine. |

## In-Memory Storage vs. Database

| Decision: All state stored in Python dicts/lists; no database. |
| --- |
|  |
| Why not MongoDB or PostgreSQL? |
| • Zero setup time; no schema migrations or connection management. |
| • Sufficient for a demo session (< 1,000 transactions, < 20 cases). |
| • No data persistence needed — each demo run starts fresh. |
|  |
| Trade-off accepted: State is lost on server restart. Not suitable for production |
| or multi-session use. Migrating to MongoDB would require replacing the in-memory |
| dict with pymongo calls — the interface layer is already abstracted for this. |

## Simulated APIs vs. Real Integrations

| Decision: All Bank, Telecom, and Police API calls are in-process mock functions. |
| --- |
|  |
| Why not real APIs? |
| • No public APIs exist for bank account freeze or telecom HLR queries. |
| • Real integration would require legal agreements, credentials, and compliance sign-off. |
| • Mock APIs allow full control of response timing, error conditions, and ACK behaviour. |
|  |
| Trade-off accepted: The system cannot demonstrate real-world integration latency or |
| failure modes. The architecture is designed so that mock functions can be replaced |
| with real HTTP clients without changing the Action Engine interface. |

## Frontend Stack Choice (React + Cytoscape.js)

| Decision: React (Vite) for UI; Cytoscape.js for graph; shadcn/ui for components. |
| --- |
|  |
| Alternatives considered: |
| • Vue.js: Comparable, but team familiarity with React is higher. |
| • D3.js for graph: More flexible but significantly more code for same output. |
| • Neo4j Bloom / Gephi: Too heavy; not embeddable in a web UI without a server. |
|  |
| Trade-off accepted: Cytoscape.js has limited 3D and physics simulation capability. |
| For a demo with ≤ 10 nodes per case, this is not a constraint. |

# B10. Testing Strategy

Given the 20-hour build window, testing is focused on correctness of core logic and demo reliability rather than full test coverage. The following approach is used:

## Simulated Fraud Scenarios

| Scenario ID | Description | Expected Outcome | Pass Condition |
| --- | --- | --- | --- |
| SC-01 | Single-hop UPI fraud: Acc-1001 → Acc-2001, ₹2L, new receiver, off-hours | Risk score ≥ 70; case created; HIGH_RISK | Case in HIGH_RISK within 3s |
| SC-02 | Multi-hop chain: Acc-1001→2001→3001→4001, funds move every 5 min | Each hop adds node to graph; recovery declines per hop | Graph updates within 2s per hop |
| SC-03 | Parallel cases: SC-01 + SIM swap case simultaneously | Both cases in priority queue; independent timers | No cross-case data contamination |
| SC-04 | Low-risk transaction: ₹5,000 to known receiver, peak hours | Score < 40; no case created; green row in feed | No case entry created |
| SC-05 | False positive: ₹50,000 salary credit (known sender) | Score 40–60; MEDIUM; warn-only; FP dismissal flow | FP log entry created on dismiss |

## Edge Case Validation

*   Late detection (EC-02): Manually trigger Hop-3 first; verify chain backfill completes within 2s
*   Partial recovery (EC-03): Trigger withdrawal event after freeze; verify Recovery % updates
*   Expired golden window: Let timer reach 0; verify case transitions to MONITORING without crash
*   Double freeze attempt: Freeze same account twice; verify 422 response and no duplicate log entry
*   WS disconnection: Kill WS connection mid-demo; verify fallback polling activates

## Basic Stress Testing

*   Volume test: Run simulator at 10x normal rate (1 tx/sec); verify scoring pipeline does not queue backlog
*   Concurrency test: Simulate 5 simultaneous cases; verify priority queue sorts correctly
*   Memory check: Run for 10 minutes; verify in-memory state does not grow unboundedly

| NOTE: No automated test framework (pytest/Jest) is strictly required for the hackathon. |
| --- |
| The above scenarios should be verified manually as part of the 19–20 hour demo rehearsal phase. |
| A basic pytest suite for the scoring engine and recovery logic is recommended as a stretch goal. |

# B11. Limitations

The following limitations are explicit and known. They are documented here to demonstrate intellectual honesty and awareness of the gap between a simulation prototype and a production system.

| 1. NO REAL BANK INTEGRATION |
| --- |
| All account data, transaction records, and freeze confirmations are synthetic. |
| No real bank account is affected by any action in this system. |
| Production deployment would require CBS integration, bilateral MoUs, and legal authorisation. |
|  |
| 2. NO LEGAL ENFORCEMENT CAPABILITY |
| The 'Freeze Account' action simulates a bank hold request — it carries no legal weight. |
| A real account freeze under Indian law requires authority from a competent judicial or |
| executive body (PMLA Section 17A, CrPC Section 102). This system cannot initiate that process. |
|  |
| 3. SIMULATION-ONLY ACCURACY |
| Risk scoring weights are heuristic defaults. No backtesting against real fraud datasets |
| has been performed. Real-world false positive and recall rates are unknown. |
| The scoring engine may produce inaccurate results if applied to real transaction data. |
|  |
| 4. NO AUTHENTICATION OR MULTI-USER SUPPORT |
| All users share the same session and can see and modify all cases. |
| There is no role-based access control, audit trail per user, or session isolation. |
|  |
| 5. IN-MEMORY STATE ONLY |
| All data is lost on server restart. Not suitable for multi-session or multi-day use. |
|  |
| 6. SINGLE-INSTITUTION SCOPE |
| The simulation operates as if all accounts are within one logical namespace. |
| Real multi-hop fraud crosses multiple banks, which requires inter-bank data sharing |
| agreements not modelled here. |

# B12. Tech Stack & 20-Hour Build Plan

## Tech Stack

| Layer | Technology | Rationale |
| --- | --- | --- |
| Backend API | FastAPI (Python 3.11) | Async support, auto-docs at /docs, minimal boilerplate |
| WebSocket | FastAPI WebSocket (built-in) | No extra library; matches backend stack; sufficient for demo load |
| Storage | Python dict/list (in-memory) | Zero setup; reset per session; see B9 trade-off rationale |
| Frontend | React 18 + Vite | Fast HMR; component model suits dashboard layout |
| UI Components | shadcn/ui or Ant Design | Pre-built tables, cards, badges; avoids styling time sink |
| Graph Rendering | Cytoscape.js | Lightweight; embeddable; supports live node/edge updates |
| Charts | Recharts | Simple progress bars and trend lines for recovery meter |

## Build Order (20 Hours)

| Hours | Phase | Tasks | Owner |
| --- | --- | --- | --- |
| 0–2 | Setup | Repo init; FastAPI scaffold; data models; WS skeleton; config.py | Full team |
| 2–5 | Core Backend | Risk scoring engine; case logic; graph engine; recovery engine | 2 backend devs |
| 5–7 | Simulator | Transaction generator; 3 scripted fraud scenarios; WS emit loop | 1 backend dev |
| 7–10 | APIs + Actions | All REST endpoints; action engine; mock APIs; priority queue | 1–2 devs |
| 10–14 | Frontend Core | Live Feed; Alert Dashboard; Case List; WebSocket integration | 1–2 frontend devs |
| 14–17 | Graph + Actions | Cytoscape graph view; Action Panel; freeze/flag buttons; timer UI | 1 frontend dev |
| 17–19 | Polish + E2E | End-to-end test with full demo script; UI cleanup; edge case checks | Full team |
| 19–20 | Demo Rehearsal | Full 10-step walkthrough; fix critical blockers only; freeze scope | Full team |

# B13. Future Scope

The following capabilities represent a realistic production roadmap if SENTINEL were to evolve beyond the hackathon prototype. These are not commitments for the current build.

## Phase 1 — Intelligence Improvement (3–6 months)

| • ML-based anomaly detection: Train a gradient-boosted classifier on real fraud datasets |
| --- |
| (e.g., bank's internal labelled records) to replace or augment rule-based scoring. |
| Maintain rule engine as a fallback for explainability. |
|  |
| • Behavioural profiling: Build per-account baseline models (spend patterns, active hours, |
| typical counterparties) for more accurate amount-deviation and time-anomaly scoring. |
|  |
| • Graph-based risk propagation: Use GNN (Graph Neural Network) models for chain-level |
| risk inference rather than simple exponential decay. |

## Phase 2 — Real Integration (6–18 months)

| • Bank API integration: Integrate with CBS (Finacle, BankFlex, or proprietary) via secured |
| --- |
| internal APIs for real account queries, hold requests, and transaction enrichment. |
|  |
| • RBI Fraud Registry: Consume and contribute to the centralised registry for cross-bank |
| fraud signals without bilateral MoUs per institution. |
|  |
| • Telecom integration: Work with TRAI-mandated channels for SIM swap alerts and number |
| flagging. Explore MNAP (Mobile Number Assignee Portal) access. |
|  |
| • Police integration: API linkage with NCRP (National Cybercrime Reporting Portal) for |
| automated FIR initiation from high-confidence fraud cases. |

## Phase 3 — Scalability & Governance (18+ months)

| • Replace in-memory state with Apache Kafka (event streaming) + MongoDB/PostgreSQL. |
| --- |
| • Multi-tenant architecture: isolate data per bank; role-based access per institution. |
| • Cross-border expansion: integrate with SWIFT gpi for international mule chain tracking. |
| • Regulatory reporting: auto-generate STR (Suspicious Transaction Report) drafts for FIU-IND. |
| • Audit and compliance module: tamper-evident action logs for regulatory inspection. |

_SENTINEL v2.0 | PRD + FRD | Hackathon Edition | Simulation Only — Not for Production Use_