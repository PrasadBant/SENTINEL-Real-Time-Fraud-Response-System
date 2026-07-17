export const STATUS_STYLES = {
  active: { bg: '#3B82F6', border: '#1D4ED8', icon: '' },
  flagged: { bg: '#F97316', border: '#EA580C', icon: '\u26A0' },
  frozen: { bg: '#9CA3AF', border: '#6B7280', icon: '\uD83D\uDD12' },
  withdrawn: { bg: '#EF4444', border: '#B91C1C', icon: '\u2715' }
};

export const graphStyles = [
  {
    selector: 'node',
    style: {
      'label': (node) => {
        const label = node.data('displayLabel') || node.data('id');
        const status = node.data('status');
        const icon = STATUS_STYLES[status]?.icon || '';
        return icon ? `${label} ${icon}` : label;
      },
      'background-color': (node) => STATUS_STYLES[node.data('status')]?.bg || STATUS_STYLES.active.bg,
      'border-width': 2,
      'border-color': (node) => STATUS_STYLES[node.data('status')]?.border || STATUS_STYLES.active.border,
      'border-style': (node) => node.data('status') === 'withdrawn' ? 'dashed' : 'solid',
      'color': '#fff',
      'text-valign': 'center',
      'text-halign': 'center',
      'font-size': 12,
      'width': (node) => {
        const bal = parseFloat(node.data('current_balance_sim') || node.data('balance') || 0);
        return Math.min(120, Math.max(45, 45 + (bal / 50000) * 40));
      },
      'height': (node) => {
        const bal = parseFloat(node.data('current_balance_sim') || node.data('balance') || 0);
        return Math.min(120, Math.max(45, 45 + (bal / 50000) * 40));
      },
      'text-outline-width': 2,
      'text-outline-color': '#000000'
    }
  },
  {
    selector: 'edge',
    style: {
      'label': '',
      'width': (edge) => {
        const amt = parseFloat(edge.data('amount') || 0);
        return Math.min(8, Math.max(1.5, 1.5 + (amt / 20000) * 3));
      },
      'line-color': '#475569',
      'target-arrow-color': '#475569',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'line-style': 'dashed',
      'line-dash-pattern': [6, 3],
      'font-size': 9,
      'text-rotation': 'autorotate',
      'text-margin-y': -14,
      'text-background-color': '#0f172a',
      'color': '#f8fafc',
      'text-background-opacity': 0.9,
      'text-background-padding': 3,
      'text-border-color': '#334155',
      'text-border-width': 1,
      'text-border-opacity': 1,
      'opacity': 0.8,
      'arrow-scale': 1.2,
      'transition-property': 'line-color, target-arrow-color, opacity, width',
      'transition-duration': '0.2s'
    }
  },
  {
    selector: 'edge.show-label',
    style: {
      'label': 'data(label)',
      'line-color': '#e2e8f0',
      'target-arrow-color': '#e2e8f0',
      'opacity': 1,
      'z-index': 20
    }
  }
];
