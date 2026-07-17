import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../hooks/useWebSocket';
import RiskBadge from '../components/RiskBadge';
import ActionButton from '../components/ActionButton';
import InvestigationSidebar from '../components/InvestigationSidebar';
import { exportAuditLog } from '../services/exportAuditLog';
import { getRole } from '../roleStore';

const CaseRow = React.memo(({ c, role, onRowClick, onGraphClick }) => (
  <tr 
    onClick={() => onRowClick(c)}
    className="hover:bg-muted/20 transition-colors group cursor-pointer"
  >
    <td className="p-4">
      <span className="font-mono text-xs font-bold">{c.case_id}</span>
    </td>
    <td className="p-4">
      <span className="font-mono text-[10px] font-bold">
        {role === "admin" ? (c.primary_tx_id || 'N/A') : '••••••'}
      </span>
    </td>
    <td className="p-4">
      <span className={`text-[10px] px-2 py-0.5 rounded font-bold border ${c.status === 'HIGH_RISK' ? 'bg-red-500/10 text-red-500 border-red-500/20' : 'bg-muted text-muted-foreground border-transparent'}`}>
        {c.status}
      </span>
    </td>
    <td className="p-4 text-center">
      <RiskBadge score={c.risk_level} />
    </td>
    <td className="p-4 text-right font-mono text-sm font-bold">
      ₹{c.total_fraud_amount.toLocaleString()}
    </td>
    <td className="p-4 text-right font-mono text-sm text-green-500 font-bold">
      ₹{c.recoverable_amount.toLocaleString()}
    </td>
    <td className="p-4 text-center">
      <div className="flex justify-center gap-2">
        <ActionButton 
          label="Graph" 
          onClick={(e) => { e.stopPropagation(); onGraphClick(c.case_id); }} 
          className="text-[10px] py-1 bg-secondary text-secondary-foreground" 
        />
        <ActionButton 
          label="Analyze" 
          onClick={(e) => { e.stopPropagation(); onRowClick(c); }} 
          className="text-[10px] py-1" 
        />
      </div>
    </td>
  </tr>
), (prev, next) => 
  prev.c.case_id === next.c.case_id && 
  prev.c.status === next.c.status && 
  prev.c.risk_level === next.c.risk_level &&
  prev.c.total_fraud_amount === next.c.total_fraud_amount &&
  prev.c.recoverable_amount === next.c.recoverable_amount &&
  prev.role === next.role
);

const Cases = () => {
  const navigate = useNavigate();
  const cases = useStore((state) => state.cases);
  const actions = useStore((state) => state.actions);
  const transactions = useStore((state) => state.transactions);
  const [filter, setFilter] = useState('ALL');
  const [sidebarState, setSidebarState] = useState({ isOpen: false, caseId: null });
  const role = getRole();

  const ALL_STATUSES = ['ALL', 'NEW', 'HIGH_RISK', 'ACTIONED', 'MONITORING', 'CLOSED', 'CLOSED_FP'];

  const filteredCases = React.useMemo(() => {
    return filter === 'ALL' ? cases : cases.filter(c => c.status === filter);
  }, [cases, filter]);

  const handleRowClick = React.useCallback((c) => {
    setSidebarState({ isOpen: true, caseId: c.case_id });
  }, []);

  const handleGraphClick = React.useCallback((caseId) => {
    navigate(`/graph/${caseId}`);
  }, [navigate]);

  const activeCase = React.useMemo(() => {
    return sidebarState.caseId ? cases.find(c => c.case_id === sidebarState.caseId) : null;
  }, [cases, sidebarState.caseId]);

  const activeTx = React.useMemo(() => {
    return sidebarState.caseId ? transactions.find(t => t.case_id === sidebarState.caseId) : null;
  }, [transactions, sidebarState.caseId]);

  const activeActions = React.useMemo(() => {
    return sidebarState.caseId ? actions.filter(a => a.case_id === sidebarState.caseId) : [];
  }, [actions, sidebarState.caseId]);

  return (
    <div className="p-8 bg-background min-h-screen animate-in slide-in-from-right-4 duration-500">
      <header className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Case Management</h1>
          <p className="text-sm text-muted-foreground mt-1 text-primary font-bold uppercase tracking-tighter">Investigation Workflow & Status Tracking</p>
        </div>
        
        <div className="flex flex-col items-end gap-4">
          <ActionButton 
            label="Export Audit Log" 
          onClick={() => { window.location.href = 'http://127.0.0.1:8000/export/sentinel_audit.csv'; }} 
            disabled={role !== "admin"}
            className="text-[10px] bg-secondary hover:bg-secondary/80 text-secondary-foreground"
          />
          <div className="flex bg-muted rounded-lg p-1 gap-1 flex-wrap">
            {ALL_STATUSES.map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase transition-all ${filter === f ? 'bg-background shadow-sm text-primary' : 'text-muted-foreground hover:text-foreground'}`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="rounded-2xl border border-border bg-card overflow-hidden shadow-sm">
        <table className="w-full text-left">
          <thead className="bg-muted/30 border-b border-border">
            <tr className="text-[10px] uppercase font-black tracking-widest text-muted-foreground">
              <th className="p-4">Case ID</th>
              <th className="p-4">Transaction ID</th>
              <th className="p-4">Status</th>
              <th className="p-4 text-center">Risk Level</th>
              <th className="p-4 text-right">Fraud Value</th>
              <th className="p-4 text-right">Recoverable</th>
              <th className="p-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filteredCases.map((c) => (
              <CaseRow key={c.case_id} c={c} role={role} onRowClick={handleRowClick} onGraphClick={handleGraphClick} />
            ))}
          </tbody>
        </table>
      </div>

      <InvestigationSidebar 
        isOpen={sidebarState.isOpen}
        selectedCase={activeCase}
        selectedTransaction={activeTx}
        actions={activeActions}
        onClose={() => setSidebarState({ ...sidebarState, isOpen: false })}
        role={role}
      />
    </div>
  );
};

export default Cases;
