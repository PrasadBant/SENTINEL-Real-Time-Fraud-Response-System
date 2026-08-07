import React, { useState } from 'react';
import RiskBadge from './RiskBadge';
import GoldenTimer from './GoldenTimer';
import ActionButton from './ActionButton';
import FactorBreakdown from './FactorBreakdown';
import { maskAccount } from '../utils/maskAccount';
import { apiFetch } from '../services/api';

const CaseCard = ({ caseData, onAnalyze, transactions = [], role }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const isViewer = role !== 'admin';
  
  if (!caseData) return null;

  const totalFraud = caseData.total_fraud_amount || 0;
  const recoverable = caseData.recoverable_amount || 0;
  const recoveryPercent = totalFraud > 0 ? ((recoverable / totalFraud) * 100).toFixed(1) : "0.0";

  // Get factors from the first transaction associated with this case
  const relatedTx = transactions.find(tx => tx.case_id === caseData.case_id);
  const factors = relatedTx?.risk_factors || [];

  const handleAction = async (e, actionEndpoint) => {
    e.stopPropagation();
    if (isViewer) return;
    try {
      await apiFetch(`/action/${actionEndpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: caseData.case_id,
          account_id: 'GLOBAL',
          reason: `Action ${actionEndpoint} executed from Case Card`
        })
      });
    } catch (error) {
      console.error('Network error during action:', error);
    }
  };

  return (
    <div 
      onClick={() => onAnalyze && onAnalyze(caseData, relatedTx)}
      className={`bg-card border border-border rounded-xl p-6 shadow-sm transition-all duration-300 ease-smooth cursor-pointer hover:-translate-y-1 hover:shadow-xl ${isExpanded ? 'ring-2 ring-primary/50' : 'hover:border-primary/50'}`}
    >
      <div className="flex justify-between items-start mb-4" onClick={(e) => { e.stopPropagation(); setIsExpanded(!isExpanded); }}>
        <div>
          <h3 className="text-sm font-mono text-muted-foreground uppercase tracking-wider mb-1">Case ID</h3>
          <p className="text-lg font-bold">{caseData.case_id}</p>
        </div>
        <RiskBadge score={caseData.risk_level} />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <div>
          <span className="text-xs text-muted-foreground block">Chain Depth</span>
          <span className="font-semibold text-sm">{caseData.chain?.length || 0} Accounts</span>
        </div>
        <div>
          <span className="text-xs text-muted-foreground block">Recovery Status</span>
          <span className="font-semibold text-sm">{recoveryPercent}%</span>
        </div>
      </div>

      <div className="space-y-3 mb-6">
        <div className="flex justify-between items-center text-sm">
          <span className="text-muted-foreground">Total Fraud</span>
          <span className="font-mono font-bold">₹{caseData.total_fraud_amount.toLocaleString()}</span>
        </div>
        <div className="flex justify-between items-center text-sm">
          <span className="text-muted-foreground">Recoverable</span>
          <span className="font-mono text-green-500 font-bold">₹{caseData.recoverable_amount.toLocaleString()}</span>
        </div>
      </div>

      <div className="pt-4 border-t border-border flex justify-between items-center mb-6">
        <GoldenTimer minutes={caseData.golden_window_minutes} />
        <span className="text-[10px] px-2 py-1 bg-muted rounded uppercase font-bold text-muted-foreground">
          {caseData.status}
        </span>
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <ActionButton label="Freeze" onClick={(e) => handleAction(e, 'freeze')} disabled={isViewer} className="bg-red-600 hover:bg-red-700 text-[10px] py-1" />
        <ActionButton label="Police" onClick={(e) => handleAction(e, 'alert')} disabled={isViewer} className="bg-blue-600 hover:bg-blue-700 text-[10px] py-1" />
        <ActionButton label="Escalate" onClick={(e) => handleAction(e, 'flag')} disabled={isViewer} className="bg-amber-600 hover:bg-amber-700 text-[10px] py-1" />
      </div>

      {/* Expandable Section */}
      {isExpanded && (
        <div className="mt-6 pt-6 border-t border-border animate-in slide-in-from-top-2 duration-300">
          <div className="mb-6">
            <h4 className="text-[10px] font-bold uppercase text-muted-foreground mb-3 tracking-widest">Transaction Chain</h4>
            <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono bg-background/50 p-3 rounded-lg">
              {caseData.chain.map((account, idx) => (
                <React.Fragment key={account}>
                  <span className="bg-primary/10 text-primary px-2 py-1 rounded border border-primary/20">
                    {isViewer ? maskAccount(account) : account}
                  </span>
                  {idx < caseData.chain.length - 1 && <span className="opacity-30">→</span>}
                </React.Fragment>
              ))}
            </div>
          </div>
          <FactorBreakdown factors={factors} />
        </div>
      )}

      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full text-[10px] uppercase font-bold text-muted-foreground hover:text-primary transition-colors pt-2"
      >
        {isExpanded ? 'Show Less' : 'Analyze Case'}
      </button>
    </div>
  );
};

export default React.memo(CaseCard, (prev, next) =>
  prev.caseData?.case_id === next.caseData?.case_id &&
  prev.caseData?.status === next.caseData?.status &&
  prev.caseData?.recoverable_amount === next.caseData?.recoverable_amount &&
  prev.caseData?.risk_level === next.caseData?.risk_level &&
  prev.role === next.role
);
