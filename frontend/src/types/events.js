/**
 * SENTINEL WebSocket Event Schema
 */

export const EVENT_TYPES = {
  TX_SCORED: 'tx_scored',
  CASE_UPDATED: 'case_updated',
  ACTION_TAKEN: 'action_taken',
  WITHDRAWAL_EVENT: 'withdrawal_event',
  WITHDRAWAL_PREVENTED: 'withdrawal_prevented'
};

/**
 * @typedef {Object} TxScoredEvent
 * @property {"tx_scored"} event
 * @property {string} tx_id
 * @property {number} risk_score
 * @property {string} case_id
 * @property {import('./index').RiskFactor[]} risk_factors
 */

/**
 * @typedef {Object} CaseUpdatedEvent
 * @property {"case_updated"} event
 * @property {string} case_id
 * @property {string} status
 * @property {number} recoverable_amount
 * @property {number} golden_window_minutes
 */

/**
 * @typedef {Object} ActionTakenEvent
 * @property {"action_taken"} event
 * @property {string} action_id
 * @property {string} case_id
 * @property {string} action_type
 * @property {string} target
 * @property {Object} api_response
 */
