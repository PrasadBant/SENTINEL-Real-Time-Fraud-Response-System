**SENTINEL**

Real-Time Fraud Response System

**BACKEND DEV**

**Dev 2**

*Setup · Simulator · REST APIs · WebSocket · Action Engine*

|                 |                     |
|-----------------|---------------------|
| **Time Budget** | **\~18 hrs active** |

Hackathon Edition \| 19-Hour Build \| Version 2.0

**Role Overview**

As Backend Developer, you own everything that connects the intelligence engines (Dev 1\'s modules) to the outside world. You build the transaction simulator, all REST endpoints, the WebSocket broadcaster, the Action Engine, the Priority Queue, and the mock agency APIs. You are the glue layer of SENTINEL.

**Core Responsibilities**

- Project setup --- repo, FastAPI scaffold, config.py, dev environment

- Transaction Simulator --- synthetic fraud event generator with 3 scripted scenarios

- REST API --- all 8+ endpoints as specified in B3

- WebSocket Broadcaster --- real-time event push to React frontend

- Action Engine --- process freeze/flag/alert commands, call mock agency APIs

- Priority Queue --- urgency-sorted case list, re-sort every 30s

- Mock Agency APIs --- Bank, Telecom, Police in-process mock functions

**19-Hour Timeline**

|                 |                                  |                                                                                                                                                                                                                      |            |
|-----------------|----------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|
| **Hours**       | **Phase**                        | **Tasks**                                                                                                                                                                                                            | **Status** |
| **0 -- 2 hr**   | **Full Team Setup**              | Init Git repo, FastAPI project structure, install dependencies, define config.py with all configurable params, create shared data_store.py (in-memory dicts), scaffold WebSocket endpoint                            | 🟡 Setup   |
| **2 -- 5 hr**   | **Transaction Simulator**        | Build simulator.py: random tx generator + 3 scripted fraud scenarios (SC-01 UPI chain, SC-02 multi-hop, SC-03 SIM swap). Emit POST /transaction on configurable interval (default 3--5s). Add is_scripted flag.      | 🟢 Active  |
| **5 -- 7 hr**   | **WebSocket + Core APIs**        | Implement WebSocket /ws endpoint. Build POST /transaction handler that calls Dev 1\'s scoring/case/graph/recovery modules. Emit tx_scored + case_updated events via WS after every processed transaction.            | 🟢 Active  |
| **7 -- 10 hr**  | **REST Endpoints + Actions**     | Implement GET /cases, GET /cases/:id, GET /graph/:caseId, GET /actions/log. Build POST /action/freeze, /action/flag, /action/alert with mock Bank/Telecom/Police API functions. Log all actions to action_log\[\].   | 🟢 Active  |
| **10 -- 14 hr** | **Priority Queue + Integration** | Implement urgency_score formula and priority queue. Re-sort every 30s and on WS case_updated event. Integrate all Dev 1 modules. Run SC-01 end-to-end. Support Dev 3/4 with mock API responses for frontend testing. | 🔵 Collab  |
| **14 -- 17 hr** | **Edge Cases + Fallback**        | Implement WS fallback: if WS drops, activate HTTP polling every 2s (poll /cases). Implement EC-03 withdrawal event simulation. Add withdrawal_event emitter to simulator with configurable delay.                    | 🟢 Active  |
| **17 -- 19 hr** | **E2E + Demo Rehearsal**         | Run full 10-step demo script. Fix critical blockers. Validate all 5 test scenarios and all API response formats. Confirm action log exports as valid JSON.                                                           | 🔵 Collab  |

**API Specification**

**REST Endpoints (B3)**

|                |            |                                                         |                                                 |
|----------------|------------|---------------------------------------------------------|-------------------------------------------------|
| **Endpoint**   | **Method** | **Description**                                         | **Key Response Fields**                         |
| /transaction   | POST       | Accept new tx; trigger scoring pipeline                 | tx_id, risk_score, risk_factors, case_id        |
| /cases         | GET        | Return all active cases                                 | case_id, status, risk_level, recoverable_amount |
| /cases/:caseId | GET        | Full case detail: chain, timeline, actions              | All Case fields + graph edge list               |
| /graph/:caseId | GET        | Nodes + edges for graph rendering                       | nodes\[\], edges\[\], recoverable_amount        |
| /action/freeze | POST       | Freeze account; update recovery                         | action_id, frozen_amount, recovery_update       |
| /action/flag   | POST       | Flag phone/account; mock Telecom API                    | action_id, telecom_ack                          |
| /action/alert  | POST       | Send Police case alert                                  | action_id, police_ack, case_status              |
| /actions/log   | GET        | Full audit trail, sorted desc by timestamp              | action_log\[\] array                            |
| /ws            | WS         | Real-time events: tx_scored, case_updated, action_taken | Streamed JSON event objects                     |

**WebSocket Event Schema**

**tx_scored event**

|                                                                                                                                                              |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| { \"event\": \"tx_scored\", \"tx_id\": \"TX-001\", \"risk_score\": 87, \"case_id\": \"CASE-001\", \"risk_factors\": \[\...\], \"threshold\": \"HIGH_RISK\" } |

**case_updated event**

|                                                                                                                                                      |
|------------------------------------------------------------------------------------------------------------------------------------------------------|
| { \"event\": \"case_updated\", \"case_id\": \"CASE-001\", \"status\": \"HIGH_RISK\", \"recoverable_amount\": 185000, \"golden_window_minutes\": 18 } |

**action_taken event**

|                                                                                                                                                                                                                       |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| { \"event\": \"action_taken\", \"action_id\": \"ACT-001\", \"case_id\": \"CASE-001\", \"action_type\": \"FREEZE_ACCOUNT\", \"target\": \"ACC-2001\", \"api_response\": { \"status\": \"ACK\", \"latency_ms\": 120 } } |

**Mock Agency API Functions**

Implement these as in-process Python functions in mock_apis.py --- NOT real HTTP calls:

|                                      |                             |                                                                         |
|--------------------------------------|-----------------------------|-------------------------------------------------------------------------|
| **Function**                         | **Simulates**               | **Returns**                                                             |
| mock_bank_freeze(account_id, amount) | Bank CBS freeze request     | { \"status\": \"ACK\", \"frozen_amount\": amount, \"latency_ms\": 120 } |
| mock_telecom_flag(number)            | Telecom number flag request | { \"status\": \"ACK\", \"flagged\": true, \"latency_ms\": 80 }          |
| mock_police_alert(case_id, evidence) | NCRP case alert             | { \"status\": \"ACK\", \"case_ref\": \"POL-001\", \"latency_ms\": 200 } |

|                                                                                                    |
|----------------------------------------------------------------------------------------------------|
| Add random latency variance (±30ms) to mock responses to make them feel realistic during the demo. |

**Priority Queue Logic (B4.4)**

|                                                                           |
|---------------------------------------------------------------------------|
| urgency_score = case_risk_score × (1 + 1 / max(golden_window_minutes, 1)) 
 Sort cases descending by urgency_score.                                    
 Tie-break 1: higher risk_score wins.                                       
 Tie-break 2: earlier created_at wins.                                      
 Re-sort every 30 seconds OR on any case_updated WS event.                  |

**Transaction Simulator --- 3 Scripted Scenarios**

|        |                    |                                                                                                  |                                   |
|--------|--------------------|--------------------------------------------------------------------------------------------------|-----------------------------------|
| **ID** | **Name**           | **Sequence**                                                                                     | **Expected**                      |
| SC-01  | UPI Mule Chain     | ACC-1001 → ACC-2001 (₹2L, new receiver, off-hours) → ACC-3001 (4 min later) → simulated cash-out | Case HIGH_RISK within 3s          |
| SC-02  | SIM Swap           | ACC-1002 → ACC-2002, telecom call_flag=true. Parallel to SC-01 to test multi-case priority.      | Telecom alert fires, Case created |
| SC-03  | Low-Risk (FP Test) | ₹5,000 to known receiver, peak hours --- should NOT create a case                                | Score \<40, green row only        |

**config.py --- Parameters You Own**

Create config.py in the project root. All teams must import from here. Never hardcode values.

|                               |               |                                                |
|-------------------------------|---------------|------------------------------------------------|
| **Parameter**                 | **Default**   | **Description**                                |
| TX_INTERVAL_SECONDS           | 3--5 (random) | Interval between simulator transactions        |
| HIGH_RISK_THRESHOLD           | 70            | Score ≥ this → HIGH_RISK case                  |
| MEDIUM_THRESHOLD              | 40            | Score ≥ this → MEDIUM / NEW case               |
| GOLDEN_WINDOW_MINUTES         | 20            | Base golden window from case creation          |
| GOLDEN_WINDOW_DECAY_PER_HOP   | 1             | Minutes subtracted per detected hop            |
| WITHDRAWAL_DELAY_SECONDS      | 300           | Simulated delay before terminal node withdraws |
| PRIORITY_QUEUE_RESORT_SECONDS | 30            | How often priority queue re-sorts              |
| WS_FALLBACK_POLL_SECONDS      | 2             | HTTP poll interval if WS disconnects           |

**Deliverables Checklist**

- Git repo initialised with correct project structure

- config.py with all parameters above

- simulator.py --- 3 scripted scenarios + random tx generator

- POST /transaction --- calls Dev 1 scoring/case/graph/recovery, emits WS events

- All 8 REST endpoints implemented and responding correctly

- WebSocket /ws endpoint broadcasting all 3 event types

- mock_apis.py --- bank_freeze, telecom_flag, police_alert with realistic latency

- Priority queue sorted by urgency_score, re-sorts on schedule

- WS fallback HTTP polling working on disconnect

- EC-03 withdrawal event emitted by simulator

- GET /actions/log returns complete audit trail, JSON exportable

|                                                                                                                                                                                                        |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 🔑 Key handoff: By Hour 10, give Dev 3 and Dev 4 a running backend with at least POST /transaction, GET /cases, GET /graph/:id, and /ws working. Frontend cannot start live integration without these. |
