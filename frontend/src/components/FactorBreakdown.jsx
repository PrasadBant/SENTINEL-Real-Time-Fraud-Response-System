import React from 'react';

const FactorBreakdown = ({ factors = [] }) => {
  // Sort factors by contribution (descending)
  const sortedFactors = [...factors].sort((a, b) => b.contribution - a.contribution);

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground opacity-50">Risk Analysis</h3>
      <div className="space-y-2">
        {sortedFactors.length > 0 ? (
          sortedFactors.map((factor, index) => (
            <div 
              key={`${factor.name}-${index}`}
              className="group bg-muted/30 hover:bg-muted/50 p-3 rounded-lg border border-transparent hover:border-border transition-all"
            >
              <div className="flex justify-between items-center mb-1">
                <span className="text-xs font-bold uppercase text-primary tracking-tight">
                  {factor.name.replace(/_/g, ' ')}
                </span>
                <span className="text-xs font-mono font-bold text-red-400">
                  +{factor.contribution}%
                </span>
              </div>
              <div className="flex justify-between items-end">
                <div className="text-[10px] text-muted-foreground">
                  Weight: <span className="text-foreground">{factor.weight}</span>
                </div>
                <div className="text-xs font-mono">
                  {typeof factor.value === 'number' ? `₹${factor.value.toLocaleString()}` : factor.value}
                </div>
              </div>
              {/* Simple progress bar representation */}
              <div className="mt-2 h-1 w-full bg-background rounded-full overflow-hidden">
                <div 
                  className="h-full bg-red-500/50 group-hover:bg-red-500 transition-all"
                  style={{ width: `${factor.contribution}%` }}
                />
              </div>
            </div>
          ))
        ) : (
          <p className="text-xs text-muted-foreground italic">No risk factors identified.</p>
        )}
      </div>
    </div>
  );
};

export default FactorBreakdown;
