import React, { useState } from 'react';
import RiskBadge from './RiskBadge';
import GoldenTimer from './GoldenTimer';
import FactorBreakdown from './FactorBreakdown';
import ActionButton from './ActionButton';
import { maskAccount } from '../utils/maskAccount';
import { twMerge } from 'tailwind-merge';
import { useRole } from '../RoleContext';
import { apiFetch } from '../services/api';

const InvestigationSidebar = ({ 
  isOpen, 
  selectedCase, 
  selectedTransaction, 
  actions = [], 
  onClose,
  role: roleProp
}) => {
  if (!isOpen) return null;

  // Prefer context role (set via RoleProvider); fall back to prop for compatibility
  const { isViewer: ctxIsViewer } = useRole();
  const isViewer = ctxIsViewer ?? (roleProp !== 'admin');

  const [actionFeedback, setActionFeedback] = useState(null);

  const totalFraud = selectedCase?.total_fraud_amount || 0;
  const recoverable = selectedCase?.recoverable_amount || 0;
  const recoveryPercent = totalFraud > 0 ? ((recoverable / totalFraud) * 100).toFixed(1) : "0.0";

  const handleAction = async (actionEndpoint) => {
    // ── AUTHORIZATION GUARD (defense in depth) ──────────────────────────
    // Even if a viewer bypasses the disabled button via devtools,
    // this guard ensures NO network request is ever made.
    if (isViewer) {
      setActionFeedback({ type: 'error', message: '🔒 Access denied — Viewer role cannot execute actions.' });
      setTimeout(() => setActionFeedback(null), 3000);
      return;
    }

    const caseId = selectedCase?.case_id || selectedTransaction?.case_id || selectedTransaction?.tx_id;
    if (!caseId) return;
    
    const targetAccount = selectedTransaction?.receiver_account || "GLOBAL";
    
    try {
      const response = await apiFetch(`/action/${actionEndpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: caseId,
          account_id: targetAccount,
          reason: `Action ${actionEndpoint} executed from terminal`
        })
      });
      
      if (!response.ok) {
        console.error(`Action ${actionEndpoint} failed with status: ${response.status}`);
        setActionFeedback({ type: 'error', message: `Action failed (HTTP ${response.status})` });
      } else {
        setActionFeedback({ type: 'success', message: `✅ ${actionEndpoint.toUpperCase()} executed successfully` });
      }
      setTimeout(() => setActionFeedback(null), 3000);
    } catch (error) {
      console.error('Network error during action:', error);
      setActionFeedback({ type: 'error', message: 'Network error — action could not be sent.' });
      setTimeout(() => setActionFeedback(null), 3000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity animate-in fade-in duration-300" 
        onClick={onClose}
      />

      <div className="absolute inset-y-0 right-0 max-w-full flex">
        <div className="w-screen max-w-md animate-in slide-in-from-right duration-500 ease-spring">
          <div className="h-full flex flex-col bg-card border-l border-border shadow-2xl overflow-y-scroll">
            
            {/* Header - Sticky */}
            <header className="sticky top-0 z-10 bg-card/90 backdrop-blur-md border-b border-border p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h2 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">
                    Investigation Unit
                  </h2>
                  <p className="text-xl font-black tracking-tighter">
                    {selectedCase?.case_id || 'STANDALONE TX'}
                  </p>
                </div>
                <button onClick={onClose} className="p-2 hover:bg-muted rounded-full transition-colors">
                   <span className="text-xl">✕</span>
                </button>
              </div>

              {selectedCase && (
                <div className="flex items-center gap-4">
                  <RiskBadge score={selectedCase.risk_level} />
                  <GoldenTimer minutes={selectedCase.golden_window_minutes} />
                  <span className="text-[10px] px-2 py-1 bg-primary/10 text-primary rounded font-bold uppercase">
                    {selectedCase.status}
                  </span>
                </div>
              )}
            </header>

            {/* Content Body */}
            <div className="flex-1 p-6 space-y-8">
              
              {/* Transaction Context */}
              {selectedTransaction && (
                <section>
                  <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-primary mb-4">Transaction Context</h3>
                  <div className="bg-muted/30 rounded-2xl p-4 border border-border">
                    <div className="flex justify-between items-center mb-4">
                      <span className="font-mono text-xs font-bold">
                        {isViewer ? '••••••' : selectedTransaction.tx_id}
                      </span>
                      <span className="text-[10px] bg-background px-2 py-1 rounded border border-border font-bold">
                        {selectedTransaction.channel}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mb-4">
                      <div className="flex-1">
                         <span className="text-[8px] uppercase text-muted-foreground font-bold">Sender</span>
                          <p className="font-mono text-sm text-primary">
                            {isViewer ? maskAccount(selectedTransaction.sender_account) : selectedTransaction.sender_account}
                          </p>
                      </div>
                      <span className="text-lg opacity-20">→</span>
                      <div className="flex-1 text-right">
                         <span className="text-[8px] uppercase text-muted-foreground font-bold">Receiver</span>
                          <p className="font-mono text-sm text-primary">
                            {isViewer ? maskAccount(selectedTransaction.receiver_account) : selectedTransaction.receiver_account}
                          </p>
                      </div>
                    </div>
                    <div className="flex justify-between items-end border-t border-border pt-3">
                       <div>
                          <span className="text-[8px] uppercase text-muted-foreground font-bold">Timestamp</span>
                          <p className="text-xs font-mono">{new Date(selectedTransaction.timestamp).toLocaleString()}</p>
                       </div>
                       <p className="text-lg font-black italic">₹{selectedTransaction.amount.toLocaleString()}</p>
                    </div>
                  </div>
                </section>
              )}

              {/* Reasoning Engine (Phase 1) */}
              {(selectedTransaction?.full_reason || selectedTransaction?.confidence) && (
                <section className="bg-primary/5 rounded-2xl p-5 border border-primary/20 space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">Reasoning Engine</h3>
                    {selectedTransaction.confidence && (
                      <span className={twMerge(
                        "text-[8px] px-2 py-0.5 rounded font-black border",
                        selectedTransaction.confidence === 'HIGH' ? "bg-green-500/10 text-green-500 border-green-500/20" :
                        selectedTransaction.confidence === 'MEDIUM' ? "bg-amber-500/10 text-amber-500 border-amber-500/20" :
                        "bg-red-500/10 text-red-500 border-red-500/20"
                      )}>
                        CONFIDENCE: {selectedTransaction.confidence}
                      </span>
                    )}
                  </div>
                  
                  <p className="text-sm font-medium leading-relaxed text-foreground italic">
                    "{selectedTransaction.full_reason}"
                  </p>

                  {/* ML Intelligence Breakdown */}
                  {selectedTransaction.ml_score !== undefined && (
                    <div className="grid grid-cols-2 gap-4 pt-2 border-t border-primary/10">
                      <div>
                        <span className="text-[8px] uppercase text-muted-foreground font-bold">Rule Engine</span>
                        <p className="text-sm font-mono font-bold text-foreground">{selectedTransaction.rule_score}</p>
                      </div>
                      <div>
                        <span className="text-[8px] uppercase text-muted-foreground font-bold">ML Predictive</span>
                        <p className="text-sm font-mono font-bold text-primary">{selectedTransaction.ml_score}</p>
                      </div>
                    </div>
                  )}

                  {/* Feature Importance */}
                  {selectedTransaction.ml_feature_importance && (
                    <div className="pt-2 space-y-2">
                       <span className="text-[8px] uppercase text-muted-foreground font-bold">Model Influence Factors</span>
                       <div className="space-y-1.5">
                          {Object.entries(selectedTransaction.ml_feature_importance).slice(0, 6).map(([feature, importance]) => (
                            <div key={feature} className="space-y-1">
                               <div className="flex justify-between text-[9px] uppercase font-bold tracking-tight">
                                  <span>{feature.replace(/_/g, ' ')}</span>
                                  <span className="opacity-60">{(importance * 100).toFixed(0)}%</span>
                               </div>
                               <div className="h-1 w-full bg-primary/10 rounded-full overflow-hidden">
                                  <div 
                                    className="h-full bg-primary" 
                                    style={{ width: `${importance * 100}%` }}
                                  />
                               </div>
                            </div>
                          ))}
                       </div>
                    </div>
                  )}
                </section>
              )}

              {/* Factor Analysis */}
              {selectedTransaction?.risk_factors && (
                <section>
                  <FactorBreakdown factors={selectedTransaction.risk_factors} />
                </section>
              )}

              {/* Action Panel */}
              <section>
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-primary mb-4">Decision Terminal</h3>

                {/* Action Feedback Toast */}
                {actionFeedback && (
                  <div className={twMerge(
                    "mb-3 px-4 py-2.5 rounded-xl text-[11px] font-bold animate-in slide-in-from-top-2",
                    actionFeedback.type === 'success'
                      ? "bg-green-500/10 border border-green-500/20 text-green-400"
                      : "bg-red-500/10 border border-red-500/20 text-red-400"
                  )}>
                    {actionFeedback.message}
                  </div>
                )}

                {/* Viewer Lock Banner */}
                {isViewer && (
                  <div className="mb-4 flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
                    <span className="text-lg">🔒</span>
                    <div>
                      <p className="text-[10px] font-black uppercase tracking-widest text-amber-400">Viewer Access — Actions Locked</p>
                      <p className="text-[9px] text-amber-300/60 mt-0.5">Login as <span className="font-mono font-bold">admin</span> to execute investigative actions.</p>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                  <ActionButton label="Freeze Account" onClick={() => handleAction('freeze')} disabled={isViewer} className="bg-red-600 hover:bg-red-700 text-[10px]" />
                  <ActionButton label="Monitor Account" onClick={() => handleAction('monitor')} disabled={isViewer} className="bg-cyan-600 hover:bg-cyan-700 text-[10px]" />
                  <ActionButton label="Escalate Case" onClick={() => handleAction('flag')} disabled={isViewer} className="bg-amber-600 hover:bg-amber-700 text-[10px]" />
                  <ActionButton label="Alert Police" onClick={() => handleAction('alert')} disabled={isViewer} className="bg-blue-600 hover:bg-blue-700 text-[10px]" />
                  <ActionButton label="Close (Resolved)" onClick={() => handleAction('close')} disabled={isViewer} className="bg-green-600 hover:bg-green-700 text-[10px]" />
                  <ActionButton label="Close (False Pos)" onClick={() => handleAction('close_fp')} disabled={isViewer} className="bg-gray-600 hover:bg-gray-700 text-[10px]" />
                </div>
              </section>

              {/* Graph Summary */}
              {selectedCase && (
                <section>
                  <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-primary mb-4">Graph Topology</h3>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-muted/20 p-3 rounded-xl border border-border">
                       <span className="text-[8px] uppercase text-muted-foreground font-bold">Chain Depth</span>
                       <p className="text-sm font-bold">{selectedCase.chain.length} Hops</p>
                    </div>
                    <div className="bg-muted/20 p-3 rounded-xl border border-border">
                       <span className="text-[8px] uppercase text-muted-foreground font-bold">Recovery</span>
                       <p className="text-sm font-bold text-green-500">{recoveryPercent}%</p>
                    </div>
                  </div>
                </section>
              )}

              {/* Action Timeline */}
              <section className="pb-10">
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-primary mb-4">Action Timeline</h3>
                <div className="space-y-4 border-l border-border ml-2 pl-6">
                   {actions.length > 0 ? actions.map((action, idx) => (
                     <div key={action.action_id} className="relative">
                       <span className="absolute -left-8 top-1 w-4 h-4 rounded-full bg-primary border-4 border-card" />
                       <div>
                          <div className="flex justify-between items-center mb-1">
                             <span className="text-[10px] font-bold uppercase tracking-tighter text-primary">
                               {action.action_type.replace(/_/g, ' ')}
                             </span>
                             <span className="text-[8px] font-mono opacity-50">
                               {new Date(action.timestamp).toLocaleTimeString()}
                             </span>
                          </div>
                          <p className="text-[10px] text-muted-foreground">
                            Target: <span className="font-mono text-foreground font-bold">
                              {isViewer ? maskAccount(action.target) : action.target}
                            </span>
                          </p>
                          <p className="text-[8px] text-muted-foreground mt-0.5">
                            Role: {action.actor_role}
                          </p>
                       </div>
                     </div>
                   )) : (
                     <p className="text-xs text-muted-foreground italic ml-2">No investigative actions recorded.</p>
                   )}
                </div>
              </section>

            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InvestigationSidebar;
