/**
 * SENTINEL Audit Log Export Service
 * Exports the full audit trail (transactions + investigative actions) as CSV.
 */
export const exportAuditLog = (actions = [], transactions = []) => {
  if (transactions.length === 0 && actions.length === 0) {
    alert('SENTINEL: No data to export yet. Wait for the live feed to receive transactions.');
    return;
  }

  const esc = (val) => {
    const str = String(val ?? '');
    return str.includes(',') || str.includes('"') || str.includes('\n')
      ? `"${str.replace(/"/g, '""')}"`
      : str;
  };

  const lines = [];

  // Section 1: Transaction Feed (always present)
  lines.push('SENTINEL AUDIT LOG - TRANSACTION FEED');
  lines.push([
    'Tx ID', 'Timestamp', 'Channel',
    'Sender Account', 'Receiver Account',
    'Amount (INR)', 'Risk Score', 'Risk Level', 'Case ID'
  ].join(','));

  transactions.forEach(tx => {
    const level = tx.risk_score >= 70 ? 'HIGH_RISK' : tx.risk_score >= 40 ? 'MEDIUM' : 'LOW';
    lines.push([
      esc(tx.tx_id),
      esc(tx.timestamp),
      esc(tx.channel || ''),
      esc(tx.sender_account || ''),
      esc(tx.receiver_account || ''),
      esc(tx.amount),
      esc(tx.risk_score),
      esc(level),
      esc(tx.case_id || '')
    ].join(','));
  });

  // Section 2: Investigative Actions (if any)
  if (actions.length > 0) {
    lines.push('');
    lines.push('INVESTIGATIVE ACTIONS');
    lines.push([
      'Action ID', 'Case ID', 'Action Type',
      'Target Account', 'Status', 'Reason', 'Latency (ms)', 'Timestamp'
    ].join(','));

    actions.forEach(a => {
      lines.push([
        esc(a.action_id),
        esc(a.case_id),
        esc(a.action_type),
        esc(a.target || a.target_id || 'GLOBAL'),
        esc(a.status || 'ACK'),
        esc(a.reason || 'System Action'),
        esc(a.latency ?? ''),
        esc(a.timestamp)
      ].join(','));
    });
  }

  // UTF-8 BOM so Excel opens correctly + join with Windows-style line endings
  const csvContent = '\uFEFF' + lines.join('\r\n');

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const filename = `sentinel_audit_${timestamp}.csv`;

  // Use data URI — most reliable cross-browser download method
  const encodedUri = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', filename);
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  console.log(`[SENTINEL] Exported ${transactions.length} transactions + ${actions.length} actions as: ${filename}`);
};
