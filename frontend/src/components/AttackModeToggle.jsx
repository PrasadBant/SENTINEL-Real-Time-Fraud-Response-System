import React, { useState, useEffect, useRef } from 'react';
import { getRole } from '../roleStore';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const AttackModeToggle = () => {
  const [isAttack, setIsAttack] = useState(window.__SENTINEL_ATTACK_MODE__ || false);
  const role = getRole();
  const isViewer = role !== 'admin';
  const intervalRef = useRef(null);

  const fireBurst = async () => {
    try {
      await fetch(`${API_BASE}/attack-mode`, { method: 'POST' });
    } catch (e) {
      console.error('[SENTINEL] Attack mode burst failed:', e);
    }
  };

  const toggleMode = async () => {
    if (isViewer) return;
    const newState = !isAttack;
    setIsAttack(newState);
    window.__SENTINEL_ATTACK_MODE__ = newState;
    window.dispatchEvent(new CustomEvent('sentinel_mode_change', { detail: newState }));

    if (newState) {
      // Fire immediately, then repeat every 30s
      await fireBurst();
      intervalRef.current = setInterval(fireBurst, 30000);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return (
    <div className={`space-y-2 ${isViewer ? 'opacity-50 grayscale pointer-events-none' : ''}`}>
      {isAttack && (
        <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-xl animate-pulse">
          <span className="w-2 h-2 bg-red-500 rounded-full animate-ping" />
          <span className="text-[9px] font-black uppercase tracking-widest text-red-500">
            Attack Detected — Burst Active
          </span>
        </div>
      )}
      <div className={`flex items-center gap-2 bg-muted/30 p-1 rounded-lg border transition-colors duration-300 shadow-inner ${isAttack ? 'border-red-500/40 bg-red-500/5' : 'border-border'}`}>
        <button
          onClick={toggleMode}
          disabled={isViewer}
          className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all duration-300 ${!isAttack ? 'bg-background shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
        >
          NORMAL
        </button>
        <button
          onClick={toggleMode}
          disabled={isViewer}
          className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all duration-300 ${isAttack ? 'bg-red-600 text-white shadow-[0_0_20px_rgba(220,38,38,0.6)] animate-pulse' : 'text-muted-foreground hover:text-foreground'}`}
        >
          ⚡ ATTACK
        </button>
      </div>
    </div>
  );
};

export default AttackModeToggle;
