/**
 * @typedef {Object} RiskFactor
 * @property {string} name
 * @property {number} weight
 * @property {number} contribution
 * @property {string | number} value
 */

/**
 * @typedef {Object} Transaction
 * @property {string} tx_id
 * @property {string} timestamp
 * @property {string} sender_account
 * @property {string} receiver_account
 * @property {number} amount
 * @property {string} currency
 * @property {'UPI' | 'NEFT' | 'IMPS' | 'RTGS'} channel
 * @property {number | null} risk_score
 * @property {RiskFactor[]} risk_factors
 * @property {string | null} case_id
 */

/**
 * @typedef {Object} Case
 * @property {string} case_id
 * @property {'NEW' | 'HIGH_RISK' | 'ACTIONED' | 'MONITORING' | 'CLOSED' | 'CLOSED_FP'} status
 * @property {number} risk_level
 * @property {number} total_fraud_amount
 * @property {number} recoverable_amount
 * @property {number} golden_window_minutes
 * @property {string[]} chain - Array of account IDs
 * @property {string[]} transactions - Array of tx IDs
 */

/**
 * @typedef {Object} ActionLog
 * @property {string} action_id
 * @property {string} case_id
 * @property {'FREEZE_ACCOUNT' | 'FLAG_NUMBER' | 'ALERT_POLICE'} action_type
 * @property {string} target
 * @property {string} actor_role
 * @property {string} timestamp
 * @property {Object} api_response
 */

export const CHANNELS = {
  UPI: 'UPI',
  NEFT: 'NEFT',
  IMPS: 'IMPS',
  RTGS: 'RTGS'
};

export const CASE_STATUS = {
  NEW: 'NEW',
  HIGH_RISK: 'HIGH_RISK',
  ACTIONED: 'ACTIONED',
  MONITORING: 'MONITORING',
  CLOSED: 'CLOSED',
  CLOSED_FP: 'CLOSED_FP'
};

export const ACTION_TYPES = {
  FREEZE_ACCOUNT: 'FREEZE_ACCOUNT',
  FLAG_NUMBER: 'FLAG_NUMBER',
  ALERT_POLICE: 'ALERT_POLICE'
};
