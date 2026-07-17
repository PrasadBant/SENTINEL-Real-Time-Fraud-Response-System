import { useMemo, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useStore } from '../hooks/useWebSocket';
import { getRole } from '../roleStore';
import ErrorBoundary from '../components/ErrorBoundary';
import GraphModule from '../modules/GraphModule';

const Graph = () => {
  const { caseId } = useParams();
  const cases = useStore((state) => state.cases);
  const transactions = useStore((state) => state.transactions);
  const actions = useStore((state) => state.actions);
  const connectionStatus = useStore((state) => state.connectionStatus);

  const selectedCase = useMemo(
    () => cases.find((c) => c.case_id === caseId) || null,
    [caseId, cases]
  );

  const handleAction = useCallback(async (type, payload) => {
    const endpointByType = {
      freeze: '/action/freeze',
      flag: '/action/flag',
      alert: '/action/alert',
      monitor: '/action/monitor',
      close: '/action/close',
      close_fp: '/action/close_fp'
    };
    const endpoint = endpointByType[type];
    if (!endpoint) return;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);
    
    const actionPayload = {
      case_id: caseId,
      account_id: payload?.accountId || payload?.target || 'GLOBAL',
      ...payload
    };
    
    let res;
    try {
      const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
      res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(actionPayload),
        signal: controller.signal
      });
    } finally {
      clearTimeout(timeoutId);
    }
    if (!res.ok) {
      throw new Error(`Action failed with status ${res.status}`);
    }
  }, [caseId]);

  if (cases.length === 0 && connectionStatus === 'LIVE') {
    return <div className="p-6 text-sm text-muted-foreground">Loading case graph...</div>;
  }

  if (connectionStatus === 'OFFLINE' && !selectedCase) {
    return <div className="p-6 text-sm text-red-500">Graph unavailable while offline.</div>;
  }

  if (!selectedCase) return null;

  return (
    <ErrorBoundary>
      <GraphModule
        caseData={selectedCase}
        actions={actions}
        onAction={handleAction}
        connectionStatus={connectionStatus}
      />
    </ErrorBoundary>
  );
};

export default Graph;
