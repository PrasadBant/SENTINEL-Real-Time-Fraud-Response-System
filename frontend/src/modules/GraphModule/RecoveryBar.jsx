/**
 * RecoveryBar Component
 * 
 * Prop-driven visualization of fraudulent funds.
 * Receives derived recovery state from the parent.
 */
const RecoveryBar = ({ recovery }) => {
  const total = Math.max(recovery.totalFraud || 0, recovery.recovered || 0, recovery.inflight || 0, recovery.lost || 0, 1);
  const recoveredWidth = `${Math.max((recovery.recovered || 0) / total * 100, 0)}%`;
  const inflightWidth = `${Math.max((recovery.inflight || 0) / total * 100, 0)}%`;
  const lostWidth = `${Math.max((recovery.lost || 0) / total * 100, 0)}%`;

  return (
    <div className="recovery-card">
      <div className="recovery-header">
        <div>
          <h3 style={{ margin: 0, fontSize: '0.75rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Investigation Recovery Rate
          </h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 900, color: '#059669', lineHeight: 1 }}>
            {recovery.percentage}% <span style={{ fontSize: '1rem', fontWeight: 500, color: '#94a3b8' }}>Saved</span>
          </div>
        </div>
      </div>

      <div
        className="recovery-stack"
        role="img"
        aria-label={`Recovered ${recovery.recovered || 0}, in-flight ${recovery.inflight || 0}, lost ${recovery.lost || 0}`}
      >
        <div style={{ width: recoveredWidth, background: '#10b981' }} />
        <div style={{ width: inflightWidth, background: '#f59e0b' }} />
        <div style={{ width: lostWidth, background: '#ef4444' }} />
      </div>

      <div className="recovery-stat-grid">
        <StatItem label="Recovered" amount={recovery.recovered} color="#10b981" />
        <StatItem label="In-flight" amount={recovery.inflight} color="#f59e0b" />
        <StatItem label="Lost" amount={recovery.lost} color="#ef4444" />
      </div>
    </div>
  );
};

const StatItem = ({ label, amount, color }) => (
  <div style={{ padding: '12px', background: '#f8fafc', borderRadius: '12px', border: `1px solid #f1f5f9` }}>
    <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '4px' }}>{label}</div>
    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: color }}>₹{(amount || 0).toLocaleString()}</div>
  </div>
);

export default RecoveryBar;
