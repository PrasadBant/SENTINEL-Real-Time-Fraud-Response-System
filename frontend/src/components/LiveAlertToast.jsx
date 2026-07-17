import React, { useState, useEffect } from 'react';
import { getRole } from '../roleStore';
import { maskAccount } from '../utils/maskAccount';

const LiveAlertToast = () => {
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    const handleAlert = (event) => {
      const data = event.detail;
      const role = getRole();
      const isViewer = role !== 'admin';
      
      // Trigger condition: risk_score >= 85
      if (data.risk_score >= 85) {
        const id = Math.random().toString(36).substr(2, 9);
        const displaySender = isViewer ? maskAccount(data.sender_account) : data.sender_account;
        
        const newAlert = {
          id,
          title: "🚨 HIGH RISK TRANSACTION",
          message: `₹${data.amount.toLocaleString()} flagged from ${displaySender}`,
          type: 'danger'
        };

        setAlerts(prev => [newAlert, ...prev].slice(0, 5));

        // Auto-dismiss
        setTimeout(() => {
          setAlerts(prev => prev.filter(a => a.id !== id));
        }, 5000);
      }
    };

    window.addEventListener('sentinel_alert', handleAlert);
    return () => window.removeEventListener('sentinel_alert', handleAlert);
  }, []);

  // EC-03: Golden window expired — mule drained funds
  useEffect(() => {
    const handleWithdrawal = (event) => {
      const data = event.detail;
      const id = Math.random().toString(36).substr(2, 9);
      const newAlert = {
        id,
        title: "⚠ Mule Withdrawal — Golden Window Expired",
        message: data.message || `Funds drained from ${data.suspect_node_id} — recovery window closed.`,
        type: 'withdrawal'
      };
      setAlerts(prev => [newAlert, ...prev].slice(0, 5));
      setTimeout(() => {
        setAlerts(prev => prev.filter(a => a.id !== id));
      }, 7000);
    };

    window.addEventListener('sentinel_withdrawal', handleWithdrawal);
    return () => window.removeEventListener('sentinel_withdrawal', handleWithdrawal);
  }, []);

  // EC-03: Investigator froze node in time — recovery secured
  useEffect(() => {
    const handleSaved = (event) => {
      const data = event.detail;
      const id = Math.random().toString(36).substr(2, 9);
      const newAlert = {
        id,
        title: "✅ Mule Frozen — Recovery Secured",
        message: data.message || `Node ${data.suspect_node_id} frozen in time. Funds recoverable.`,
        type: 'saved'
      };
      setAlerts(prev => [newAlert, ...prev].slice(0, 5));
      setTimeout(() => {
        setAlerts(prev => prev.filter(a => a.id !== id));
      }, 7000);
    };

    window.addEventListener('sentinel_saved', handleSaved);
    return () => window.removeEventListener('sentinel_saved', handleSaved);
  }, []);

  const getBorderColor = (type) => {
    if (type === 'withdrawal') return 'border-amber-500';
    if (type === 'saved') return 'border-green-500';
    return 'border-red-600';
  };

  const getTitleColor = (type) => {
    if (type === 'withdrawal') return 'text-amber-400';
    if (type === 'saved') return 'text-green-400';
    return 'text-red-500';
  };

  const getProgressColor = (type) => {
    if (type === 'withdrawal') return 'bg-amber-500';
    if (type === 'saved') return 'bg-green-500';
    return 'bg-red-600';
  };

  return (
    <div className="fixed top-6 right-6 z-[100] flex flex-col gap-3 pointer-events-none">
      {alerts.map(alert => (
        <div 
          key={alert.id}
          className={`w-80 bg-background/80 backdrop-blur-xl border-l-4 ${getBorderColor(alert.type)} border border-border p-4 rounded-xl shadow-2xl pointer-events-auto animate-in slide-in-from-right fade-in duration-300`}
        >
          <div className="flex justify-between items-start">
             <h4 className={`text-[10px] font-black tracking-widest ${getTitleColor(alert.type)} uppercase`}>{alert.title}</h4>
             <button 
               onClick={() => setAlerts(prev => prev.filter(a => a.id !== alert.id))}
               className="text-muted-foreground hover:text-foreground"
             >
               ✕
             </button>
          </div>
          <p className="text-xs font-bold mt-1">{alert.message}</p>
          <div className="mt-2 w-full bg-muted h-0.5 rounded-full overflow-hidden">
             <div className={`${getProgressColor(alert.type)} h-full animate-[shrink_5s_linear]`} />
          </div>
        </div>
      ))}
      <style>{`
        @keyframes shrink {
          from { width: 100%; }
          to { width: 0%; }
        }
      `}</style>
    </div>
  );
};

export default LiveAlertToast;
