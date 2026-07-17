# SENTINEL - Real-Time Fraud Response System

**A hackathon-scale intelligent fraud detection and investigation platform with real-time transaction analysis, dynamic case management, and investigative action engine.**

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Core Features](#core-features)
4. [Tech Stack](#tech-stack)
5. [Monorepo Structure](#monorepo-structure)
6. [Getting Started](#getting-started)
7. [Running the System](#running-the-system)
8. [API Reference](#api-reference)
9. [WebSocket Events](#websocket-events)
10. [Fraud Detection Engine](#fraud-detection-engine)
11. [Simulation Scenarios](#simulation-scenarios)
12. [Key Components](#key-components)

---

## 🎯 Project Overview

**SENTINEL** is a real-time fraud investigation platform designed to detect, analyze, and respond to financial crimes in real-time. The system processes transaction streams, applies hybrid rule-based and ML scoring, creates connected case graphs, and enables investigators to take rapid investigative actions (account freezes, telecom flags, police alerts).

### Key Capabilities

- **Real-time Transaction Processing**: Ingest and score transactions within milliseconds
- **Intelligent Risk Scoring**: Hybrid rule-based + ML-guided scoring engine
- **Dynamic Case Management**: Automatically link related fraud transactions into investigation cases
- **Transaction Graph Visualization**: Visual representation of fraud chains and money flows
- **Investigative Actions**: Freeze accounts, flag phone numbers, alert police, monitor accounts
- **Recovery Calculation**: Track recoverable amounts across accounts in fraud chains
- **Action Logging & Audit Trail**: Complete compliance-ready audit logs
- **WebSocket Broadcasting**: Real-time event streaming to investigators' dashboards
- **Transaction Simulator**: Configurable fraud scenario generator for demos and testing

---

## 🏗️ System Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TRANSACTION STREAM                            │
│  (Simulator / Real API / External feeds)                             │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  POST /transaction  │
        │   (FastAPI Entry)   │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────────────────────────────────┐
        │           ORCHESTRATION PIPELINE                │
        ├───────────────────────────────────────────────┤
        │ 1. Account Initialization & Persistence        │
        │ 2. Risk Scoring (Hybrid Rule + ML)             │
        │ 3. Case Linking & Creation                     │
        │ 4. Transaction Graph Building                  │
        │ 5. Recovery Amount Calculation                 │
        └──────────┬─────────────────────────────────────┘
                   │
        ┌──────────▼──────────────────────┐
        │  In-Memory Data Store            │
        │  - Transactions                  │
        │  - Cases                         │
        │  - Accounts                      │
        │  - Graphs (Nodes/Edges)          │
        │  - Actions Log                   │
        └──────────┬─────────────────────┘
                   │
        ┌──────────▼──────────────────────┐
        │    WebSocket Broadcasting        │
        │  (Events: tx_scored,             │
        │   case_updated, action_taken)    │
        └──────────┬─────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      REACT FRONTEND                                  │
│  ├─ Dashboard (Cases, KPIs)                                          │
│  ├─ Graph Module (Interactive fraud chain visualization)             │
│  ├─ Action Panel (Freeze/Flag/Alert buttons)                         │
│  ├─ Action Log (Audit trail timeline)                                │
│  └─ WebSocket Hook (useWebSocket.js) for real-time sync              │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Transaction Ingestion**: Simulator or external API sends transaction to `/transaction`
2. **Scoring**: Rule-based scoring on amount deviation, time anomaly, new receivers, call flags
3. **Case Linking**: Transaction linked to existing case or new case created if score triggers threshold
4. **Graph Building**: Nodes (accounts) and edges (transaction flows) added to case graph
5. **Recovery Calc**: Recoverable amounts updated based on account status (frozen/withdrawn)
6. **Broadcasting**: Events pushed via WebSocket to connected frontend clients
7. **Actions**: Investigators take actions → mock agency APIs called → action logged → status updated

---

## 🚀 Core Features

### 1. Hybrid Fraud Scoring

**Rule-Based Engine** (Deterministic):
- **New Receiver Detection** (35% weight): First-time recipient of funds
- **Amount Deviation** (30% weight): Transaction amount vs. account's historical average
- **Time Anomaly** (20% weight): Off-hours transactions (10 PM - 6 AM)
- **Call Flag** (15% weight): Active call during transaction

**Dynamic Fraud Indicators**:
- Cross-border transactions
- Device/location changes
- Crypto-related transfers
- Scripted fraud patterns (velocity attacks, bulk transfers, SIM swaps)
- Remote access activity

**ML-Guided Scoring** (Adaptive):
- Feature importance tracking for transparency
- Per-feature contribution analysis
- Hybrid score = Rule Score + ML Score

**Thresholds**:
- **HIGH_RISK** (≥ 60): Immediate case creation
- **MEDIUM** (≥ 40): Case creation if no recent case linked
- **LOW** (< 40): Green row only, no case

### 2. Dynamic Case Management

**Case Lifecycle**:
- **NEW**: Case created on high-risk transaction
- **HIGH_RISK**: Multiple suspicious transactions confirmed
- **ACTIONED**: Investigator took action (freeze, flag, alert)
- **MONITORING**: Account under surveillance
- **CLOSED**: Investigation resolved
- **CLOSED_FP**: False positive

**Case Features**:
- Automatic transaction linking (same chain, same account)
- Dynamic node capping (3-6 nodes per case for variety)
- Golden Window tracking (time to act before money is withdrawn)
- Depth limiting (max 5 hops to prevent infinite chains)
- Total fraud amount accumulation
- Recovery percentage tracking

### 3. Transaction Graph Visualization

**Graph Model**:
- **Nodes**: Bank accounts (source, intermediaries, exits)
- **Edges**: Transactions with amounts and flow direction
- **Visualization**: Cytoscape.js with custom styling
- **Lead Node Detection**: Account with highest inflow = suspect

**Interactive Features**:
- Node selection highlights related transactions
- Node actions (freeze, flag account)
- Color coding by status (active, frozen, withdrawn)
- Recovery bar showing money recovery progress

### 4. Investigative Actions

**Freeze Action**:
- Locks specified account and all downstream accounts
- Updates account status in graph
- Recovers funds if account has balance
- Mock Bank API call with latency simulation

**Flag Action**:
- Alerts telecom provider for phone number
- Prevents SIM swaps
- Mock Telecom API integration

**Alert Action**:
- Escalates to police
- Case marked for law enforcement
- Mock Police API integration

**Monitor Action**:
- Continuous surveillance without freezing
- Case status = MONITORING

**Close/Close FP**:
- Resolves investigation
- Logs closure reason and timestamp

### 5. Recovery Engine

**Calculation**:
```
recoverable_amount = sum of balances in non-withdrawn accounts
recovery_percentage = (recovered + recoverable) / total_fraud * 100
```

**Status-Based Logic**:
- **Active**: Funds can be recovered (frozen or available)
- **Frozen**: Funds held pending enforcement
- **Withdrawn**: Funds lost (0% recovery)

---

## 🛠️ Tech Stack

### Frontend

| Technology | Purpose |
|-----------|---------|
| **React 18** | UI component framework |
| **Vite 5** | Lightning-fast build tool & dev server |
| **TailwindCSS** | Utility-first CSS styling |
| **Cytoscape.js** | Graph/network visualization engine |
| **Recharts** | Chart components (if used for analytics) |
| **React Router v6** | Client-side routing |
| **Lucide React** | Icon library |
| **clsx/tailwind-merge** | CSS utility helpers |

### Backend

| Technology | Purpose |
|-----------|---------|
| **FastAPI** | Modern async Python web framework |
| **Uvicorn** | ASGI server (high-performance) |
| **Pydantic** | Data validation & serialization |
| **Python 3.10+** | Core language |
| **asyncio** | Async/await concurrency |
| **WebSockets** | Real-time bidirectional communication |

### Data Storage

- **In-Memory Store**: Python dictionaries (demo-grade; production would use Redis/PostgreSQL)
- **Data Structures**: Nested dicts for transactions, cases, accounts, graphs, action logs

---

## 📁 Monorepo Structure

```
Criminal Investigation/
│
├── frontend/                          # React + Vite frontend
│   ├── src/
│   │   ├── components/               # Reusable UI components
│   │   │   ├── ActionButton.jsx
│   │   │   ├── AttackModeToggle.jsx
│   │   │   ├── CaseCard.jsx
│   │   │   ├── ErrorBoundary.jsx
│   │   │   ├── FactorBreakdown.jsx
│   │   │   ├── GoldenTimer.jsx
│   │   │   ├── InvestigationSidebar.jsx
│   │   │   ├── LiveAlertToast.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── RiskBadge.jsx
│   │   │   └── SystemStatusBar.jsx
│   │   ├── hooks/
│   │   │   └── useWebSocket.js       # Real-time event subscription
│   │   ├── modules/
│   │   │   └── GraphModule/          # Case graph visualization
│   │   │       ├── GraphCanvas.jsx   # Cytoscape rendering
│   │   │       ├── ActionPanel.jsx   # Action controls
│   │   │       ├── NodeActions.jsx   # Per-node actions
│   │   │       ├── ActionLog.jsx     # Audit trail
│   │   │       ├── RecoveryBar.jsx   # Recovery visualization
│   │   │       └── Legend.jsx        # Node status legend
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Cases.jsx
│   │   │   ├── Graph.jsx
│   │   │   └── Feed.jsx
│   │   ├── services/
│   │   │   └── exportAuditLog.js
│   │   ├── utils/
│   │   │   └── maskAccount.js
│   │   ├── types/
│   │   │   ├── events.js             # WebSocket event type definitions
│   │   │   └── index.js
│   │   ├── roleStore.js              # Role-based access control
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── postcss.config.cjs
│
├── backend/                            # FastAPI backend + engines
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app entry
│   │   ├── core/
│   │   │   ├── config.py             # Risk scoring parameters
│   │   │   ├── constants.py          # Enums & constants
│   │   │   ├── data_store.py         # In-memory store
│   │   │   └── models/
│   │   │       ├── account.py
│   │   │       ├── transaction.py
│   │   │       ├── case.py
│   │   │       └── action.py
│   │   ├── engines/                  # Core fraud detection logic
│   │   │   ├── scoring_engine.py     # Hybrid rule + ML scoring
│   │   │   ├── case_manager.py       # Case creation & linking
│   │   │   ├── graph_engine.py       # Graph building
│   │   │   └── recovery_engine.py    # Recovery calculation
│   │   ├── services/
│   │   │   ├── orchestrator.py       # Main pipeline
│   │   │   └── mock_apis.py          # Telecom, Bank, Police mocks
│   │   └── utils/
│   │       └── id_generator.py
│   ├── simulator/
│   │   └── simulator.py              # Transaction generator (11 scenarios)
│   ├── main.py                       # Entry point
│   ├── requirements.txt
│   ├── cases_debug.json              # Sample test cases
│   └── cases_complex_verify.json
│
├── docs/                              # Project documentation
│   ├── backend_integration_notes.md
│   ├── frontend_contracts.md
│   └── [dev notes from hackathon]
│
└── README.md                          # This file
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+** (for backend)
- **Node.js 16+** and npm (for frontend)
- **Git**
- Any modern browser

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install
```

---

## 🎯 Running the System

The system requires **3 separate terminal sessions**:

### Terminal 1: Backend Server

```bash
cd backend
python main.py
```

**Output**:
```
[ML Engine] Rule-Guided ML Emulator loaded
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

✓ Backend is ready at `http://localhost:8000`

### Terminal 2: Frontend Development Server

```bash
cd frontend
npm run dev
```

**Output**:
```
VITE v5.4.21 ready in 526 ms
➜  Local:   http://localhost:5173/
```

✓ Frontend is ready at `http://localhost:5173`

### Terminal 3: Transaction Simulator

```bash
cd backend
python simulator/simulator.py
```

**Output**:
```
SENTINEL Simulator Started — 6 tx/min | Equal Risk Distribution (Ctrl+C to stop)
Executing Scenario SC-01: Mule Chain (HIGH RISK)...
```

✓ Simulator generates transactions and pumps them into the backend at 6 tx/min

### Access the Application

Open your browser to: **http://localhost:5173**

You should see:
- **Dashboard**: Real-time case creation and updates
- **Cases**: All active investigation cases
- **Graph**: Interactive visualization of fraud chains
- **Feed**: Raw transaction stream

---

## 📡 API Reference

### REST Endpoints

#### Get All Cases

```http
GET /cases
```

**Response**:
```json
[
  {
    "case_id": "CASE-ABC12345",
    "status": "HIGH_RISK",
    "risk_level": 82,
    "nodes": [
      { "account_id": "ACC-VICTIM-001", "status": "active", "balance": 50000 },
      { "account_id": "ACC-MULE-001", "status": "frozen", "balance": 150000 }
    ],
    "edges": [
      { "tx_id": "TX-001", "source": "ACC-VICTIM-001", "target": "ACC-MULE-001", "amount": 200000 }
    ],
    "recoverable_amount": 150000,
    "recovery_pct": 75.0,
    "total_fraud_amount": 200000,
    "golden_window_minutes": 18,
    "actionLog": []
  }
]
```

#### Process Transaction

```http
POST /transaction
Content-Type: application/json

{
  "tx_id": "TX-001",
  "timestamp": "2024-04-30T14:30:00Z",
  "sender_account": "ACC-1001",
  "receiver_account": "ACC-2001",
  "amount": 200000,
  "currency": "INR",
  "channel": "NEFT",
  "hop_number": 0
}
```

**Response**:
```json
{
  "transaction": {
    "tx_id": "TX-001",
    "risk_score": 78,
    "risk_factors": [
      { "name": "amount_deviation", "contribution": 30 },
      { "name": "new_receiver", "contribution": 35 }
    ],
    "case_id": "CASE-ABC12345",
    "threshold": "HIGH_RISK",
    "ml_score": 42,
    "rule_score": 78,
    "ml_feature_importance": { "amount": 0.45, "is_new_receiver": 0.35 }
  },
  "case": { ... }
}
```

#### Freeze Account

```http
POST /action/freeze
Content-Type: application/json

{
  "case_id": "CASE-ABC12345",
  "account_id": "ACC-MULE-001",
  "reason": "High-risk mule account"
}
```

#### Flag Phone Number

```http
POST /action/flag
Content-Type: application/json

{
  "case_id": "CASE-ABC12345",
  "target_id": "+91-9876543210",
  "reason": "SIM swap attempt"
}
```

#### Alert Police

```http
POST /action/alert
Content-Type: application/json

{
  "case_id": "CASE-ABC12345",
  "reason": "Multi-account fraud chain detected"
}
```

#### Export Audit Log

```http
GET /export/sentinel_audit.csv
```

Returns CSV file with complete audit trail.

#### Health Check

```http
GET /health
```

**Response**:
```json
{ "status": "ok", "message": "Sentinel API is healthy" }
```

---

## 🔌 WebSocket Events

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  console.log('Connected to SENTINEL');
};
```

### Event: Transaction Scored

Fired when a transaction is processed and scored.

```json
{
  "event": "tx_scored",
  "tx_id": "TX-001",
  "case_id": "CASE-ABC12345",
  "risk_score": 78,
  "amount": 200000,
  "sender_account": "ACC-VICTIM-001",
  "receiver_account": "ACC-MULE-001",
  "channel": "NEFT",
  "risk_factors": [...],
  "threshold": "HIGH_RISK",
  "reason": "High amount deviation + new receiver",
  "ml_score": 42,
  "rule_score": 78,
  "ml_feature_importance": { ... }
}
```

### Event: Case Updated

Fired when a case changes (new transaction, action taken, etc.).

```json
{
  "event": "case_updated",
  "case_id": "CASE-ABC12345",
  "status": "HIGH_RISK",
  "nodes": [...],
  "edges": [...],
  "recoverable_amount": 150000,
  "recovery_pct": 75.0,
  "golden_window_minutes": 18,
  "actionLog": [...]
}
```

### Event: Action Taken

Fired when investigator performs an action.

```json
{
  "event": "action_taken",
  "action_id": "ACT-XYZ789",
  "case_id": "CASE-ABC12345",
  "action": "freeze",
  "target_id": "ACC-MULE-001",
  "status": "ACK",
  "timestamp": "2024-04-30T14:35:00Z"
}
```

---

## 🧠 Fraud Detection Engine

### Scoring Formula

```
RISK_SCORE = (new_receiver × 0.35) + (amount_deviation × 0.30) + 
             (time_anomaly × 0.20) + (call_flag × 0.15) + 
             [dynamic factors + ML contribution]
```

### Factor Definitions

| Factor | Description | Trigger | Score |
|--------|-------------|---------|-------|
| **New Receiver** | First-time recipient of funds | account.is_new_receiver = true | 100 |
| **Amount Deviation** | Abnormal transaction size | amount > 1.05× avg_monthly | 0-100 |
| **Time Anomaly** | Off-hours transaction | 10 PM - 6 AM | 100 |
| **Call Flag** | Transaction during active call | tx.on_active_call = true | 100 |
| **Velocity Attack** | Multiple rapid transactions | velocity_flag = true | Boosts to 100 |
| **Cross-Border** | International transfer | is_cross_border = true | Boosts amount_dev to 100 |
| **Device Change** | New device detected | device_changed = true | Boosts to 100 |
| **Crypto-Related** | Crypto exchange involved | is_crypto_related = true | Boosts amount_dev to 100 |

### ML Component

The ML engine provides **feature importance** scoring:
- Analyzes transaction characteristics
- Assigns importance weights to each feature
- Contributes to final hybrid score
- Transparent feature breakdown for investigators

---

## 🎬 Simulation Scenarios

The simulator generates realistic fraud patterns for testing:

### High-Risk Scenarios (equal probability)

**SC-01: Mule Chain** 🔴
- Victim account → Layer 1 mule → Exit account
- Branching structure (1-4 hops)
- Large amounts (₹200K-₹500K)
- Chain depth: 3-6 accounts
- Expected Score: 75-95

**SC-05: Cross-Border Fraud** 🔴
- International transfer with high risk
- Amount: ₹150K-₹400K
- All channels supported
- Flag: `is_cross_border = true`
- Expected Score: 70-90

**SC-06: Account Takeover** 🔴
- Victim account compromised
- Device/location change flags
- Amount: ₹100K-₹300K
- Triggers: `device_changed`, `location_changed`
- Expected Score: 75-92

**SC-08: Crypto Drain** 🔴
- Crypto exchange involvement
- Suspicious amount transfer
- Flag: `is_crypto_related = true`
- Expected Score: 80-95

### Medium-Risk Scenarios

**SC-02: SIM Swap** 🟠
- Phone compromise + transfer
- Triggered during active call
- Amount: ₹25K-₹95K
- Flag: `on_active_call = true`
- Expected Score: 50-80

**SC-11: Aggregation/Mule** 🟠
- Multiple victims → single mule account
- Bulk transfer pattern
- Amount: ₹50K-₹150K each
- Flag: `bulk_transfer_flag = true`
- Expected Score: 45-75

### Low-Risk Scenarios

**SC-03: Routine Transaction** 🟢
- Normal peer-to-peer transfer
- Amount: ₹100-₹9K
- Business hours
- Expected Score: 5-25

**SC-07: Small Payment** 🟢
- Retail/merchant payment
- Amount: ₹50-₹5K
- Low deviation from average
- Expected Score: 10-30

**SC-04: Velocity Attack** 🟢
- Rapid-fire micro transactions
- Same sender/receiver pair
- Amount: ₹10-₹50 each
- Flag: `velocity_flag = true`
- Expected Score: 30-60

### Simulator Configuration

```python
# In simulator/simulator.py
CHANNEL_CAPS = {
    "UPI":    100000,
    "IMPS":   500000,
    "NEFT":   500000,
    "CARD":   200000,
}

# 6 transactions per minute (every 10 seconds)
# Equal distribution: 1/3 HIGH, 1/3 MEDIUM, 1/3 LOW
```

---

## 🧩 Key Components

### Frontend Components

**useWebSocket Hook** (`src/hooks/useWebSocket.js`)
- Manages WebSocket connection to backend
- Maintains in-memory store of cases, transactions, actions
- Handles reconnection with exponential backoff
- HTTP polling fallback if WebSocket drops
- Normalizes incoming data from different API formats
- Notifies listeners on state changes

**GraphModule** (`src/modules/GraphModule/`)
- `GraphCanvas.jsx`: Cytoscape.js rendering engine
- `ActionPanel.jsx`: Freeze/Flag/Alert button controls
- `NodeActions.jsx`: Per-node context menu
- `ActionLog.jsx`: Audit trail timeline
- `RecoveryBar.jsx`: Visual progress of money recovery
- `Legend.jsx`: Account status color coding

**Dashboard & Cases Pages**
- Real-time case list with sorting/filtering
- Risk level indicators and color coding
- Action history timeline
- Golden window countdown timer
- Recovery percentage progress bar

### Backend Engines

**Scoring Engine** (`app/engines/scoring_engine.py`)
- Rule-based factor analysis
- ML feature importance calculation
- Hybrid score combination
- Configurable weights and thresholds
- Dynamic fraud indicator detection

**Case Manager** (`app/engines/case_manager.py`)
- Case creation on high-risk transactions
- Automatic transaction linking
- Chain depth tracking
- Golden window management
- Case status lifecycle

**Graph Engine** (`app/engines/graph_engine.py`)
- Node (account) creation and management
- Edge (transaction) addition
- Duplicate prevention
- Graph retrieval and serialization

**Recovery Engine** (`app/engines/recovery_engine.py`)
- Recoverable amount calculation
- Status-based logic (active, frozen, withdrawn)
- Recovery percentage tracking
- Multi-node aggregation

**Orchestrator** (`app/services/orchestrator.py`)
- Main pipeline orchestration
- Calls all engines in sequence
- Account persistence & initialization
- ML score integration
- Event generation

### Mock APIs

**Bank Freeze API**
```python
mock_bank_freeze(account_id, amount)
# Returns: {"status": "SUCCESS", "frozen_amount": amount}
```

**Telecom Flag API**
```python
mock_telecom_flag(phone_number)
# Returns: {"status": "SUCCESS", "flag_id": "FLAG-XXX"}
```

**Police Alert API**
```python
mock_police_alert(case_id, payload)
# Returns: {"status": "SUCCESS", "alert_id": "ALERT-XXX"}
```

---

## 📊 Data Models

### Transaction

```python
{
  "tx_id": "TX-001",
  "timestamp": "2024-04-30T14:30:00Z",
  "sender_account": "ACC-1001",
  "receiver_account": "ACC-2001",
  "amount": 200000.0,
  "currency": "INR",
  "channel": "NEFT",  # UPI | IMPS | NEFT | CARD
  "hop_number": 0,
  "case_id": "CASE-ABC12345",
  "risk_score": 78,
  "risk_factors": [...],
  "threshold": "HIGH_RISK"
}
```

### Case

```python
{
  "case_id": "CASE-ABC12345",
  "status": "HIGH_RISK",  # NEW | HIGH_RISK | ACTIONED | MONITORING | CLOSED | CLOSED_FP
  "created_at": "2024-04-30T14:30:00Z",
  "risk_level": 78,
  "total_fraud_amount": 200000.0,
  "recoverable_amount": 150000.0,
  "recovery_pct": 75.0,
  "golden_window_minutes": 18,
  "chain": ["ACC-VICTIM-001", "ACC-MULE-001"],
  "chain_depth": 1,
  "transactions": ["TX-001"],
  "actions_taken": [],
  "timeline": [...]
}
```

### Action

```python
{
  "action_id": "ACT-XYZ789",
  "case_id": "CASE-ABC12345",
  "action_type": "FREEZE",
  "target_id": "ACC-MULE-001",
  "status": "ACK",
  "timestamp": "2024-04-30T14:35:00Z",
  "reason": "High-risk mule account",
  "latency": 45
}
```

---

## ⚙️ Configuration

Edit `backend/app/core/config.py` to tune the system:

```python
# Risk Factor Weights
W_NEW_RECEIVER = 0.35      # 35% weight
W_AMOUNT_DEV = 0.30        # 30% weight
W_TIME_ANOMALY = 0.20      # 20% weight
W_CALL_FLAG = 0.15         # 15% weight

# Thresholds
HIGH_RISK_THRESHOLD = 60    # ≥60 → HIGH_RISK case
MEDIUM_THRESHOLD = 40       # ≥40 → case consideration

# System
DECAY_FACTOR = 0.85         # Recovery decay per hop
GOLDEN_WINDOW_MINUTES = 20  # Time to act before withdrawal
```

---

## 🧪 Testing

### Test with Curl

```bash
# Score a normal transaction
curl -X POST http://localhost:8000/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "tx_id": "TEST-001",
    "timestamp": "2024-04-30T14:30:00Z",
    "sender_account": "ACC-USER-001",
    "receiver_account": "ACC-MERCH-001",
    "amount": 1500,
    "currency": "INR",
    "channel": "UPI",
    "hop_number": 0
  }'

# Get all cases
curl http://localhost:8000/cases
```

### Test with Attack Mode

The frontend has an "Attack Mode" button that injects 5 high-risk transactions:

```bash
curl -X POST http://localhost:8000/attack-mode
```

---

## 📝 Project Timeline (Hackathon Context)

This project was built as a **19-hour hackathon submission** with 4 team members:

| Phase | Duration | Focus |
|-------|----------|-------|
| Setup & Foundation | 2 hrs | Git repo, project structure, dependencies, config |
| Simulator | 3 hrs | Transaction generation, 8+ scenarios, realistic patterns |
| WebSocket & Core APIs | 2 hrs | Real-time event broadcasting, /transaction endpoint |
| REST Endpoints & Actions | 3 hrs | All CRUD endpoints, freeze/flag/alert, mock APIs |
| Integration & Polish | 5 hrs | Priority queue, error handling, testing, edge cases |
| Demo Rehearsal | 4 hrs | E2E validation, bug fixes, performance optimization |

---

## 🔮 Future Enhancements

- **Persistence Layer**: Replace in-memory store with PostgreSQL/Redis
- **Advanced ML**: Integration with real ML models (XGBoost, LightGBM)
- **Role-Based Access Control**: Admin, Analyst, Supervisor roles with permissions
- **Historical Analytics**: Trends, patterns, predictive scoring
- **Alert Notifications**: Email, SMS, Slack integration
- **API Rate Limiting**: DDoS protection, quota management
- **Mobile App**: Native iOS/Android companion app
- **Blockchain Integration**: Immutable audit trail on ledger
- **Batch Processing**: Parallel transaction processing for scale
- **Geographic Heatmaps**: Money flow visualization by region

---

## 🤝 Contributing

This is a hackathon project. For modifications:

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and test thoroughly
3. Commit with clear messages: `git commit -am 'Add feature: ...'`
4. Push and create a PR

---

## 📄 License

MIT License - See LICENSE file for details

---

## 👥 Team Credits

**Backend Dev**: Transaction simulator, REST API, WebSocket broadcasting, action engine, priority queue  
**Frontend Dev**: React UI, real-time WebSocket integration, case management UI  
**Graph Dev**: Cytoscape visualization, interactive graph controls, node actions  
**ML/Scoring**: Hybrid scoring engine, feature importance, risk calculation  

---

## 📞 Support

For issues or questions:
1. Check the [docs/](docs/) directory for detailed notes
2. Review error logs in terminal output
3. Verify all 3 processes (backend, frontend, simulator) are running
4. Check WebSocket connectivity: `chrome://net-internals/#events` (DevTools)

**Quick Health Check**:
```bash
# Backend health
curl http://localhost:8000/health

# Frontend loads
curl http://localhost:5173

# Simulator running
ps aux | grep simulator.py
```

---

**SENTINEL - Intelligent Real-Time Fraud Investigation Platform**  
Built for speed, transparency, and investigative effectiveness.


