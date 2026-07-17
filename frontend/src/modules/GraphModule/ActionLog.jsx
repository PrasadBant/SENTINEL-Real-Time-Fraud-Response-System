import { getRole } from '../../roleStore';
import { maskAccount } from '../../utils/maskAccount';

/**
 * ActionLog Component
 * 
 * Displays rich audit trail with reasoning and graph cross-linking.
 */
const ActionLog = ({ logs, onLogClick }) => {
  const role = getRole();
  const isViewer = role !== 'admin';

  const getActionColor = (type) => {
    switch (type) {
      case 'FREEZE': return '#3b82f6';
      case 'FLAG': return '#f59e0b';
      case 'ALERT': return '#8b5cf6';
      default: return '#94a3b8';
    }
  };

  const formatTarget = (target) => {
    if (!target || target === 'GLOBAL' || target === 'SUSPECTS') return target;
    return isViewer ? maskAccount(target) : target;
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      overflowY: 'auto',
      maxHeight: '300px',
      padding: '4px'
    }}>
      <h4 style={{ 
        margin: '0 0 4px 0', 
        fontSize: '0.65rem', 
        color: '#94a3b8', 
        textTransform: 'uppercase', 
        letterSpacing: '0.1em' 
      }}>
        Audit Trail (Rich History)
      </h4>
      
      {logs.length === 0 && (
        <div style={{ fontSize: '0.8125rem', color: '#cbd5e1', fontStyle: 'italic' }}>
          Initializing investigation ledger...
        </div>
      )}

      {logs.map((log) => (
        <div 
          key={log.action_id} 
          onClick={() => log.target !== 'GLOBAL' && onLogClick(log.target)}
          style={{
            fontSize: '0.75rem',
            fontFamily: 'monospace',
            padding: '10px',
            background: log.status === 'NACK' ? '#fff1f2' : '#f8fafc',
            border: `1px solid ${log.status === 'NACK' ? '#fecaca' : '#f1f5f9'}`,
            borderRadius: '10px',
            cursor: log.target !== 'GLOBAL' ? 'pointer' : 'default',
            transition: 'transform 0.1s, box-shadow 0.1s',
            boxShadow: log.status === 'NACK' ? '0 2px 4px rgba(239, 68, 68, 0.1)' : 'none'
          }}
          onMouseEnter={(e) => {
            if (log.target !== 'GLOBAL') {
              e.currentTarget.style.transform = 'translateY(-1px)';
              e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0,0,0,0.05)';
            }
          }}
          onMouseLeave={(e) => {
            if (log.target !== 'GLOBAL') {
              e.currentTarget.style.transform = 'none';
              e.currentTarget.style.boxShadow = log.status === 'NACK' ? '0 2px 4px rgba(239, 68, 68, 0.1)' : 'none';
            }
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <div style={{ color: '#64748b' }}>
              <span style={{ color: '#94a3b8' }}>[{log.timestamp}]</span>{' '}
              <span style={{ fontWeight: 800, color: getActionColor(log.action_type) }}>{log.action_type}</span>{' '}
              <span style={{ color: '#334155' }}>{formatTarget(log.target)}</span>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span style={{ 
                color: log.status === 'ACK' ? '#10b981' : '#ef4444', 
                fontWeight: 800 
              }}>
                {log.status}
              </span>
            </div>
          </div>
          
          <div style={{ fontSize: '0.65rem', color: '#94a3b8', display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontStyle: 'italic', maxWidth: '70%', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              Reason: {log.reason || 'System Action'}
            </span>
            <span>{log.latency}ms</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default ActionLog;
