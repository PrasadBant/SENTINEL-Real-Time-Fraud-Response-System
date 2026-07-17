const Legend = () => {
  const items = [
    { label: 'Active', color: '#3B82F6', icon: '' },
    { label: 'Flagged', color: '#F97316', icon: '⚠' },
    { label: 'Frozen', color: '#9CA3AF', icon: '🔒' },
    { label: 'Withdrawn', color: '#EF4444', icon: '✗', dashed: true }
  ];

  return (
    <div className="absolute top-[70px] right-4 bg-card/90 backdrop-blur-md px-4 py-3 rounded-xl border border-border shadow-lg z-50 flex flex-col gap-2">
      <h4 className="m-0 text-[11px] text-muted-foreground uppercase tracking-[0.05em] font-bold">Legend</h4>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2.5">
          <div style={{
            width: '14px',
            height: '14px',
            borderRadius: '4px',
            background: item.color,
            border: `1.5px ${item.dashed ? 'dashed' : 'solid'} rgba(255,255,255,0.15)`
          }} />
          <span className="text-[13px] text-foreground font-medium">
            {item.label} {item.icon}
          </span>
        </div>
      ))}
    </div>
  );
};

export default Legend;
