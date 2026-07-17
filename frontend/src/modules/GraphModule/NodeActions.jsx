import { maskAccount } from '../../utils/maskAccount';

/**
 * NodeActions Component (Final Polish)
 * 
 * Contextual actions for a specific account node.
 * Uses per-node processing state from useActionController.
 */
const NodeActions = ({ 
  node, 
  onClose, 
  executeAction,
  processingNodes,
  role
}) => {
  if (!node) return null;

  const isViewer = role !== 'admin';
  const displayId = isViewer ? maskAccount(node.id) : node.id;
  const isFrozen = node.status === 'frozen';
  const isWithdrawn = node.status === 'withdrawn';
  const isProcessing = !!processingNodes[node.id] || isViewer;

  return (
    <div style={{
      position: 'absolute',
      bottom: '24px',
      left: '24px',
      background: 'rgba(255, 255, 255, 0.95)',
      padding: '20px',
      borderRadius: '20px',
      border: '1px solid #e2e8f0',
      boxShadow: '0 12px 32px -4px rgba(0, 0, 0, 0.15)',
      backdropFilter: 'blur(12px)',
      width: '260px',
      zIndex: 200,
      display: 'flex',
      flexDirection: 'column',
      gap: '16px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: '0.875rem', fontWeight: 900, color: '#1e293b', letterSpacing: '-0.02em' }}>{displayId}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
             <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: isFrozen ? '#94a3b8' : '#10b981' }} />
             <div style={{ fontSize: '0.75rem', color: '#64748b', textTransform: 'capitalize', fontWeight: 500 }}>
               {node.status}
             </div>
          </div>
        </div>
        <button 
          onClick={onClose}
          style={{ border: 'none', background: '#f1f5f9', borderRadius: '50%', width: '24px', height: '24px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', cursor: 'pointer' }}
        >
          ×
        </button>
      </div>

      <div style={{ display: 'flex', gap: '8px' }}>
        <button 
          onClick={() => executeAction('freeze', { accountId: node.id })}
          disabled={isProcessing || isFrozen || isWithdrawn}
          style={nodeActionButtonStyle('#3b82f6', isProcessing || isFrozen || isWithdrawn)}
        >
          {isProcessing ? 'PROCESSING...' : (isFrozen ? 'FROZEN 🔒' : 'FREEZE')}
        </button>

        <button 
          onClick={() => executeAction('flag', { accountId: node.id })}
          disabled={isProcessing || isFrozen || isWithdrawn}
          style={nodeActionButtonStyle('#f59e0b', isProcessing || isFrozen || isWithdrawn)}
        >
          FLAG
        </button>
      </div>

      {isProcessing && (
        <div style={{ fontSize: '11px', color: '#3b82f6', fontWeight: 700, textAlign: 'center', animation: 'pulse 1s infinite' }}>
          Establishing secure link...
        </div>
      )}

      {(isFrozen || isWithdrawn) && !isProcessing && (
        <div style={{ 
          fontSize: '11px', 
          color: '#94a3b8', 
          fontStyle: 'italic', 
          background: '#f8fafc', 
          padding: '8px', 
          borderRadius: '8px',
          border: '1px solid #f1f5f9'
        }}>
          Account restricted by jurisdiction.
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0% { opacity: 1; }
          50% { opacity: 0.6; }
          100% { opacity: 1; }
        }
      `}</style>
    </div>
  );
};

const nodeActionButtonStyle = (color, isDisabled) => ({
  flex: 1,
  padding: '12px 8px',
  background: isDisabled ? '#f8fafc' : color,
  color: isDisabled ? '#cbd5e1' : '#fff',
  border: `1px solid ${isDisabled ? '#e2e8f0' : 'transparent'}`,
  borderRadius: '12px',
  fontWeight: 800,
  fontSize: '0.7rem',
  cursor: isDisabled ? 'default' : 'pointer',
  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
  boxShadow: isDisabled ? 'none' : `0 4px 6px ${color}20`
});

export default NodeActions;
