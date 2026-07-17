import ActionLog from './ActionLog';

/**
 * ActionPanel Component (Final Polish)
 * 
 * High-fidelity command center for investigation.
 */
const ActionPanel = ({ 
  caseId, 
  caseState,
  lastActionStatus,
  leadNodeId,
  processingNodes,
  actionLog, 
  executeAction,
  onLogClick,
  role
}) => {
  const isGlobalProcessing = !!processingNodes['GLOBAL'] || role !== 'admin';

  const getStatusIndicator = () => {
    switch (lastActionStatus) {
      case 'BUSY': return { label: 'Processing', color: '#f59e0b', icon: '🟡' };
      case 'ERROR': return { label: 'System Error', color: '#ef4444', icon: '🔴' };
      default: return { label: 'System Ready', color: '#10b981', icon: '🟢' };
    }
  };

  const status = getStatusIndicator();

  return (
    <aside style={{
      width: '100%',
      background: '#fff',
      borderLeft: '1px solid #e2e8f0',
      display: 'flex',
      flexDirection: 'column',
      padding: '24px',
      gap: '24px'
    }}>
      {/* System Status Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '10px' }}>{status.icon}</span>
          <span style={{ fontSize: '11px', fontWeight: 700, color: status.color, textTransform: 'uppercase' }}>
            {status.label}
          </span>
        </div>
        <div style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8' }}>V1.4.2-PROD</div>
      </div>

      {/* Case Overview */}
      <div style={{ padding: '20px', background: '#f8fafc', borderRadius: '16px', border: '1px solid #f1f5f9' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h3 style={{ margin: '0 0 2px 0', fontSize: '0.65rem', color: '#94a3b8', textTransform: 'uppercase' }}>Case ID</h3>
            <div style={{ fontSize: '1.125rem', fontWeight: 800, color: '#1e293b' }}>{caseId}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <h3 style={{ margin: '0 0 2px 0', fontSize: '0.65rem', color: '#94a3b8', textTransform: 'uppercase' }}>Status</h3>
            <span style={{ 
              fontSize: '0.65rem', 
              padding: '4px 8px', 
              background: caseState === 'ACTIONED' || caseState === 'CLOSED' ? '#ecfdf5' : (caseState === 'MONITORING' ? '#eff6ff' : '#fef2f2'), 
              color: caseState === 'ACTIONED' || caseState === 'CLOSED' ? '#059669' : (caseState === 'MONITORING' ? '#3b82f6' : '#ef4444'), 
              borderRadius: '6px', 
              fontWeight: 800 
            }}>
              {caseState}
            </span>
          </div>
        </div>
      </div>

      {/* Global & Lead Actions */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <h4 style={{ margin: '0', fontSize: '0.75rem', color: '#64748b', fontWeight: 700 }}>Decision Support</h4>
        
        <button 
          onClick={() => executeAction('freeze', { accountId: 'SUSPECTS' })}
          disabled={isGlobalProcessing || processingNodes['SUSPECTS']}
          style={primaryButtonStyle('#3b82f6', isGlobalProcessing || processingNodes['SUSPECTS'])}
        >
          {processingNodes['SUSPECTS'] ? 'FREEZING NETWORK...' : `Freeze Suspect Network`}
        </button>

        <button 
          onClick={() => executeAction('flag', { accountId: leadNodeId })}
          disabled={isGlobalProcessing || processingNodes[leadNodeId]}
          style={secondaryButtonStyle('#f59e0b', isGlobalProcessing || processingNodes[leadNodeId])}
        >
          Flag Primary Suspect
        </button>

        <button 
          onClick={() => executeAction('alert', { accountId: 'GLOBAL' })}
          disabled={isGlobalProcessing || caseState === 'ACTIONED'}
          style={primaryButtonStyle('#8b5cf6', isGlobalProcessing || caseState === 'ACTIONED')}
        >
          {caseState === 'ACTIONED' ? 'CASE ESCALATED 🚨' : 'Escalate to Authorities'}
        </button>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <button 
            onClick={() => executeAction('monitor', { accountId: leadNodeId || 'GLOBAL' })}
            style={secondaryButtonStyle('#3b82f6', isGlobalProcessing)}
          >
            Monitor
          </button>
          <button 
            onClick={() => executeAction('close', { accountId: 'GLOBAL' })}
            style={secondaryButtonStyle('#10b981', isGlobalProcessing)}
          >
            Resolve
          </button>
        </div>

        <button 
          onClick={() => executeAction('close_fp', { accountId: 'GLOBAL' })}
          style={secondaryButtonStyle('#64748b', isGlobalProcessing)}
        >
          Mark False Positive
        </button>

        {lastActionStatus === 'ERROR' && (
          <div style={{ 
            fontSize: '11px', 
            color: '#ef4444', 
            textAlign: 'center', 
            padding: '8px', 
            background: '#fef2f2', 
            borderRadius: '8px',
            border: '1px solid #fee2e2'
          }}>
            Last action failed. <span style={{ textDecoration: 'underline', cursor: 'pointer', fontWeight: 800 }}>Retry connection?</span>
          </div>
        )}
      </div>

      {/* Audit Log (Linked) */}
      <div style={{ flex: 1, borderTop: '1px solid #f1f5f9', paddingTop: '20px' }}>
        <ActionLog logs={actionLog} onLogClick={onLogClick} />
      </div>
    </aside>
  );
};

const primaryButtonStyle = (color, isDisabled) => ({
  width: '100%',
  padding: '12px',
  background: isDisabled ? '#f1f5f9' : color,
  color: isDisabled ? '#94a3b8' : '#fff',
  border: 'none',
  borderRadius: '12px',
  fontWeight: 700,
  fontSize: '0.8125rem',
  cursor: isDisabled ? 'default' : 'pointer',
  transition: 'all 0.2s',
  opacity: isDisabled ? 0.7 : 1,
  boxShadow: isDisabled ? 'none' : `0 4px 12px ${color}30`
});

const secondaryButtonStyle = (color, isDisabled) => ({
  width: '100%',
  padding: '12px',
  background: '#fff',
  color: isDisabled ? '#94a3b8' : color,
  border: `1px solid ${isDisabled ? '#e2e8f0' : color + '40'}`,
  borderRadius: '12px',
  fontWeight: 700,
  fontSize: '0.8125rem',
  cursor: isDisabled ? 'default' : 'pointer',
  transition: 'all 0.2s'
});

export default ActionPanel;
