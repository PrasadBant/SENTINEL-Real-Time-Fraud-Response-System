import React, { useState, useMemo, useCallback } from 'react';
import { useStore } from '../hooks/useWebSocket';
import RiskBadge from '../components/RiskBadge';
import InvestigationSidebar from '../components/InvestigationSidebar';
import { getRole } from '../roleStore';
import { maskAccount } from '../utils/maskAccount';

const formatTime = (isoString) => {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
};

const getRowColor = (score, tx) => {
  if (!tx) return 'hover:bg-muted/50';
  if (tx.regulatory_flagged && !tx.requires_pan) return "bg-amber-400/10 hover:bg-amber-400/20";
  if (score >= 70) return "bg-red-500/10 hover:bg-red-500/20";
  if (score >= 40) return "bg-amber-500/10 hover:bg-amber-500/20";
  return "hover:bg-muted/50";
};

const FeedRow = React.memo(({ tx, role, onClick }) => (
  <tr 
    onClick={() => onClick(tx)}
    className={`transition-colors duration-200 cursor-pointer ${getRowColor(tx.risk_score, tx)}`}
  >
    <td className="p-4 font-mono text-xs font-bold tracking-tighter">
      {role === "admin" ? tx.tx_id : "••••••"}
    </td>
    <td className="p-4 text-center font-mono text-xs opacity-70 tracking-tighter">{formatTime(tx.timestamp)}</td>
    <td className="p-4 text-center">
      <span className="text-[10px] bg-muted px-2 py-0.5 rounded font-bold border border-border/50 uppercase tracking-tighter">{tx.channel}</span>
    </td>
     <td className="p-4">
      <div className="flex items-center gap-2 text-xs">
        <span className="font-mono text-primary font-bold">
          {role === "admin" ? tx.sender_account : maskAccount(tx.sender_account)}
        </span>
        <span className="opacity-30">→</span>
        <span className="font-mono text-primary font-bold">
          {role === "admin" ? tx.receiver_account : maskAccount(tx.receiver_account)}
        </span>
      </div>
    </td>
    <td className="p-4 text-right font-mono font-bold tracking-tighter">
      ₹{tx.amount.toLocaleString()}
    </td>
    <td className="p-4 text-center">
      <RiskBadge score={tx.risk_score} />
    </td>
    <td className="p-4">
      {tx.reason && (
        <span className="text-xs font-bold text-white italic whitespace-nowrap overflow-hidden text-ellipsis max-w-[250px] block">
          {tx.reason}
        </span>
      )}
    </td>
  </tr>
), (prev, next) => prev.tx.tx_id === next.tx.tx_id && prev.role === next.role);


const Feed = () => {
  const transactions = useStore((state) => state.transactions);
  const cases = useStore((state) => state.cases);
  const actions = useStore((state) => state.actions);
  const [sidebarState, setSidebarState] = useState({ isOpen: false, tx: null });
  const role = getRole();
  
  // Data calculations for Header
  const totalTransactions = transactions.length;
  const totalAtRiskAmount = useMemo(
    () => cases.reduce((sum, c) => sum + c.total_fraud_amount, 0),
    [cases]
  );

  // Calculate Tx/min (transactions in the last 60 seconds)
  const txPerMin = useMemo(
    () => transactions.filter(tx => Date.now() - new Date(tx.timestamp).getTime() < 60000).length,
    [transactions]
  );

  // Sort transactions by timestamp (latest first) and limit to 100
  const sortedTransactions = useMemo(
    () => [...transactions].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)).slice(0, 100),
    [transactions]
  );



  const handleTxClick = useCallback((tx) => {
    setSidebarState({ isOpen: true, tx });
  }, []);

  const activeCaseId = sidebarState.tx?.case_id;

  const activeCase = useMemo(() => {
    return activeCaseId ? cases.find(c => c.case_id === activeCaseId) : null;
  }, [cases, activeCaseId]);

  const activeActions = useMemo(() => {
    return activeCaseId ? actions.filter(a => a.case_id === activeCaseId) : [];
  }, [actions, activeCaseId]);

  return (
    <div className="flex flex-col h-screen bg-background overflow-hidden animate-in fade-in duration-500">
      {/* Header Bar */}
      <header className="p-6 border-b border-border bg-card/30 backdrop-blur-md">
        <div className="flex justify-between items-center max-w-7xl mx-auto">
          <div className="flex items-center gap-6">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-primary">SENTINEL</h1>
              <p className="text-xs text-muted-foreground uppercase tracking-widest mt-1">Live Transaction Stream</p>
            </div>
          </div>
          
          <div className="flex gap-8">
            <div className="text-right">
              <span className="text-[10px] text-muted-foreground uppercase font-bold block tracking-tighter">Throughput</span>
              <span className="text-xl font-mono font-bold">{totalTransactions}</span>
            </div>
            <div className="text-right border-l border-border pl-8">
              <span className="text-[10px] text-muted-foreground uppercase font-bold block tracking-tighter flex items-center gap-1">
                <span className="w-1 h-1 bg-primary rounded-full animate-pulse" />
                Velocity
              </span>
              <span className="text-xl font-mono font-bold text-primary">⚡ {txPerMin} <span className="text-[10px]">tx/min</span></span>
            </div>
            <div className="text-right border-l border-border pl-8">
              <span className="text-[10px] text-muted-foreground uppercase font-bold block tracking-tighter">At Risk</span>
              <span className="text-xl font-mono font-bold text-red-500">₹{totalAtRiskAmount.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Table Container */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-7xl mx-auto">
          <div className="rounded-xl border border-border bg-card overflow-hidden shadow-2xl">
            <table className="w-full text-left border-collapse">
              <thead className="bg-muted/50 sticky top-0 backdrop-blur-sm">
                <tr className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground border-b border-border">
                  <th className="p-4">Tx ID</th>
                  <th className="p-4 text-center">Time</th>
                  <th className="p-4 text-center">Channel</th>
                  <th className="p-4">Sender → Receiver</th>
                  <th className="p-4 text-right">Amount</th>
                  <th className="p-4 text-center">Risk Score</th>
                  <th className="p-4 text-left">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortedTransactions.map((tx) => (
                  <FeedRow key={tx.tx_id} tx={tx} role={role} onClick={handleTxClick} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <InvestigationSidebar 
        isOpen={sidebarState.isOpen}
        selectedTransaction={sidebarState.tx}
        selectedCase={activeCase}
        actions={activeActions}
        onClose={() => setSidebarState({ ...sidebarState, isOpen: false })}
        role={role}
      />
    </div>
  );
};

export default Feed;
