import { create } from 'zustand';
import { EVENT_TYPES } from '../types/events';
import { clearAuthGlobal, getToken } from '../roleStore';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

let ws = null;
let reconnectTimer = null;
let pollingTimer = null;
let reconnectDelay = 1500;
let started = false;
let pollingFailures = 0;

export const useStore = create((set, get) => ({
  transactions: [],
  cases: [],
  actions: [],
  connectionStatus: 'OFFLINE',
  setConnectionStatus: (status) => set({ connectionStatus: status }),
  setCases: (cases) => set({ cases }),
  addTransaction: (tx) => set((state) => {
    const exists = state.transactions.some((t) => t.tx_id === tx.tx_id);
    if (exists) return state;
    return { transactions: [tx, ...state.transactions].slice(0, 100) };
  }),
  updateCase: (payload) => set((state) => ({
    cases: mergeCase(state.cases, payload).slice(0, 500)
  })),
  addAction: (action) => set((state) => ({
    actions: [action, ...state.actions].slice(0, 2000),
    cases: state.cases.map((c) =>
      c.case_id === action.case_id
        ? { ...c, actionLog: [action, ...(c.actionLog || [])] }
        : c
    )
  }))
}));

const normalizeCase = (raw = {}) => ({
  case_id: raw.case_id || raw.caseId || '',
  status: raw.status || 'NEW',
  nodes: Array.isArray(raw.nodes)
    ? raw.nodes.map((n) => ({
      ...n,
      accountId: n.accountId || n.account_id || n.id || '',
      account_id: n.account_id || n.accountId || n.id || '',
      id: n.id || n.accountId || n.account_id || ''
    }))
    : [],
  edges: Array.isArray(raw.edges)
    ? raw.edges.map((e) => ({
      ...e,
      source: e.source || e.from || '',
      target: e.target || e.to || '',
      tx_id: e.tx_id || e.id || `${e.source || e.from}-${e.target || e.to}`
    }))
    : [],
  recoverable_amount: Number(raw.recoverable_amount || raw.recoverableAmount || 0),
  actionLog: Array.isArray(raw.actionLog)
    ? raw.actionLog.map(normalizeAction)
    : (Array.isArray(raw.actions_taken) ? raw.actions_taken.map(normalizeAction) : []),
  risk_level: Number(raw.risk_level || 0),
  golden_window_minutes: Number(raw.golden_window_minutes || 0),
  total_fraud_amount: Number(raw.total_fraud_amount || 0),
  primary_tx_id: raw.primary_tx_id || raw.primaryTxId || '',
  chain: Array.isArray(raw.chain) ? raw.chain : []
});

const normalizeTransaction = (raw = {}) => ({
  ...raw,
  tx_id: raw.tx_id || raw.txId || '',
  case_id: raw.case_id || raw.caseId || '',
  risk_score: Number(raw.risk_score || 0),
  timestamp: raw.timestamp || new Date().toISOString()
});

const normalizeAction = (raw = {}) => ({
  ...raw,
  action_id: raw.action_id || raw.actionId || `action_${Date.now()}`,
  case_id: raw.case_id || raw.caseId || '',
  action_type: (raw.action_type || raw.actionType || raw.action || '').toUpperCase(),
  target_id: raw.target_id || raw.target || raw.account_id || raw.accountId || 'GLOBAL',
  target: raw.target || raw.target_id || raw.account_id || raw.accountId || 'GLOBAL',
  timestamp: raw.timestamp || new Date().toISOString()
});

const mergeCase = (cases, incomingRaw) => {
  const incoming = normalizeCase(incomingRaw);
  const idx = cases.findIndex((c) => c.case_id === incoming.case_id);
  if (idx === -1) return [incoming, ...cases];
  const next = [...cases];
  next[idx] = { ...next[idx], ...incoming };
  return next;
};

const validateCasePayload = (raw) => {
  if (!raw || typeof raw !== 'object') {
    console.warn('[WS] Malformed case payload: expected object');
    return false;
  }
  if (!raw.case_id && !raw.caseId) {
    console.warn('[WS] Malformed case payload: missing case_id');
    return false;
  }
  if (raw.nodes !== undefined && !Array.isArray(raw.nodes)) {
    console.warn(`[WS] Malformed case payload for ${raw.case_id || raw.caseId}: nodes must be an array`);
    return false;
  }
  if (raw.edges !== undefined && !Array.isArray(raw.edges)) {
    console.warn(`[WS] Malformed case payload for ${raw.case_id || raw.caseId}: edges must be an array`);
    return false;
  }
  return true;
};

const startPolling = () => {
  if (pollingTimer) return;
  useStore.getState().setConnectionStatus('POLLING');
  pollingTimer = setInterval(async () => {
    try {
      const token = getToken();
      const res = await fetch(`${API_BASE}/cases`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.status === 401) {
        // Session expired/invalid — stop polling and bounce to login rather
        // than retrying forever against an endpoint that will never succeed.
        stopPolling();
        clearAuthGlobal();
        return;
      }
      if (!res.ok) {
        pollingFailures += 1;
        if (pollingFailures >= 3) {
          useStore.getState().setConnectionStatus('OFFLINE');
        }
        return;
      }
      const payload = await res.json();
      const cases = Array.isArray(payload)
        ? payload.filter(validateCasePayload).map(normalizeCase)
        : [];
      pollingFailures = 0;
      useStore.getState().setCases(cases);
    } catch {
      pollingFailures += 1;
      if (pollingFailures >= 3) {
        useStore.getState().setConnectionStatus('OFFLINE');
      }
    }
  }, 2000);
};

const stopPolling = () => {
  if (!pollingTimer) return;
  clearInterval(pollingTimer);
  pollingTimer = null;
};

const scheduleReconnect = () => {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    useStore.getState().setConnectionStatus('RECONNECTING');
    connectWS();
  }, reconnectDelay);
  reconnectDelay = Math.min(reconnectDelay * 2, 10000);
};

const handleEvent = (payload = {}) => {
  const type = payload.event;
  if (type === EVENT_TYPES.TX_SCORED) {
    const incoming = normalizeTransaction(payload);
    useStore.getState().addTransaction(incoming);
    window.dispatchEvent(new CustomEvent('sentinel_alert', { detail: incoming }));
    return;
  }

  if (type === EVENT_TYPES.CASE_UPDATED) {
    if (!validateCasePayload(payload)) return;
    useStore.getState().updateCase(payload);
    return;
  }

  if (type === EVENT_TYPES.ACTION_TAKEN) {
    const incoming = normalizeAction(payload);
    useStore.getState().addAction(incoming);
  }

  if (type === EVENT_TYPES.WITHDRAWAL_EVENT) {
    window.dispatchEvent(new CustomEvent('sentinel_withdrawal', { detail: payload }));
    return;
  }

  if (type === EVENT_TYPES.WITHDRAWAL_PREVENTED) {
    window.dispatchEvent(new CustomEvent('sentinel_saved', { detail: payload }));
    return;
  }
};

const connectWS = () => {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

  // Browsers can't set custom headers on a WebSocket handshake, so the JWT
  // travels as a query param instead — the backend's get_ws_user dependency
  // reads it from there (see backend/app/core/deps.py).
  const token = getToken();
  if (!token) {
    // No session yet (shouldn't normally happen — App.jsx gates the whole
    // app behind login — but stay defensive rather than opening an
    // unauthenticated connection the server will just reject anyway).
    return;
  }
  const separator = WS_URL.includes('?') ? '&' : '?';
  ws = new WebSocket(`${WS_URL}${separator}token=${encodeURIComponent(token)}`);

  ws.onopen = () => {
    reconnectDelay = 1500;
    stopPolling();
    useStore.getState().setConnectionStatus('LIVE');
  };

  ws.onmessage = (event) => {
    try {
      handleEvent(JSON.parse(event.data));
    } catch {
      // ignore malformed payloads
    }
  };

  ws.onclose = () => {
    ws = null;
    startPolling();
    scheduleReconnect();
  };

  ws.onerror = () => {
    ws?.close();
  };
};

export const startRealtime = async () => {
  if (started) return;
  started = true;
  startPolling();
  connectWS();
};

export const stopRealtime = () => {
  if (ws) {
    ws.onclose = null;
    ws.onerror = null;
    ws.onmessage = null;
    ws.close();
    ws = null;
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  stopPolling();
  started = false;
  reconnectDelay = 1500;
  pollingFailures = 0;
};
