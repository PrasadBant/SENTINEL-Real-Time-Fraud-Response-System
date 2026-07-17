# SENTINEL Frontend API Contracts

This document defines the data structures and WebSocket event schemas expected by the SENTINEL frontend.

## 1. Transaction Object
The base unit of monitoring.

| Field | Type | Description |
| :--- | :--- | :--- |
| `tx_id` | `string` | Unique transaction identifier |
| `timestamp` | `string (ISO)` | Event occurrence time |
| `sender_account` | `string` | Originating account ID |
| `receiver_account` | `string` | Target account ID |
| `amount` | `number` | Transaction value |
| `currency` | `string` | Currency code (e.g., "INR") |
| `channel` | `string` | Transaction method (UPI, IMPS, NEFT, CARD) |
| `risk_score` | `number` | Fraud probability (0-100) |
| `risk_factors` | `array<object>` | List of fraud indicators |
| `case_id` | `string` | Associated investigation ID (nullable) |

**Example:**
```json
{
  "tx_id": "tx_8821",
  "timestamp": "2026-04-28T15:30:00Z",
  "sender_account": "ACC-1234",
  "receiver_account": "ACC-5678",
  "amount": 45000,
  "currency": "INR",
  "channel": "UPI",
  "risk_score": 92,
  "risk_factors": [{"name": "rapid_hops", "weight": 40}],
  "case_id": "case_alpha"
}
```

## 2. Case Object
Represents an investigative unit.

| Field | Type | Description |
| :--- | :--- | :--- |
| `case_id` | `string` | Unique case identifier |
| `status` | `string` | NEW, HIGH_RISK, ACTIONED, MONITORING, CLOSED, CLOSED_FP |
| `risk_level` | `number` | Aggregate risk score |
| `total_fraud_amount`| `number` | Total value at risk |
| `recoverable_amount`| `number` | Amount still in system |
| `golden_window_minutes`| `number` | Minutes left for recovery |
| `chain` | `array<string>` | List of account IDs in the fraud path |
| `transactions` | `array<string>` | List of associated `tx_id` values |

## 3. Action Log Object
History of investigative steps.

| Field | Type | Description |
| :--- | :--- | :--- |
| `action_id` | `string` | Unique log entry ID |
| `case_id` | `string` | Associated case ID |
| `action_type` | `string` | FREEZE, ESCALATE, ALERT_POLICE, MARK_REVIEWED |
| `target` | `string` | ID of the account or case affected |
| `actor_role` | `string` | Role of the initiator (SYSTEM, ANALYST, ADMIN) |
| `timestamp` | `string (ISO)` | When the action occurred |

## 4. WebSocket Event Schemas

### `tx_scored`
Emitted when a new transaction is processed.
**Payload:** Full Transaction Object.

### `case_updated`
Emitted when case metadata (status, risk, window) changes.
**Payload:** Partial Case Object (must include `case_id`).

### `action_taken`
Emitted when a new action is recorded.
**Payload:** Full Action Log Object.
