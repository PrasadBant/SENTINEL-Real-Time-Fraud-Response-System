import React, { useState, useEffect } from 'react';

const SystemStatusBar = ({ status }) => {
  const [lastEventTime, setLastEventTime] = useState(0);

  useEffect(() => {
    // Reset timer on status change or simulation heartbeat
    setLastEventTime(0);
    const interval = setInterval(() => {
      setLastEventTime(prev => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [status]);

  const getStatusConfig = (s) => {
    switch (s) {
      case 'LIVE':
        return { color: 'bg-green-500', text: 'LIVE', pulse: true };
      case 'POLLING':
        return { color: 'bg-amber-500', text: 'POLLING', pulse: false };
      case 'RECONNECTING':
        return { color: 'bg-orange-500', text: 'RECONNECTING', pulse: true };
      case 'OFFLINE':
        return { color: 'bg-red-500', text: 'OFFLINE', pulse: false };
      default:
        return { color: 'bg-muted', text: 'UNKNOWN', pulse: false };
    }
  };

  const config = getStatusConfig(status);

  return (
    <div className="flex items-center gap-3 px-3 py-1.5 bg-muted/20 border border-border rounded-full backdrop-blur-md">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${config.color} ${config.pulse ? 'animate-pulse' : ''}`} />
        <span className="text-[10px] font-bold uppercase tracking-tighter">{config.text}</span>
      </div>
      <div className="h-3 w-[1px] bg-border" />
      <span className="text-[10px] font-mono text-muted-foreground tabular-nums">
        Last event: {lastEventTime}s ago
      </span>
    </div>
  );
};

export default SystemStatusBar;
