import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

const RiskBadge = ({ score }) => {
  const getColors = (s) => {
    if (s >= 70) return "bg-red-500/10 text-red-500 border-red-500/20";
    if (s >= 40) return "bg-amber-500/10 text-amber-500 border-amber-500/20";
    return "bg-green-500/10 text-green-500 border-green-500/20";
  };

  return (
    <div className={twMerge(
      "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold border",
      getColors(score)
    )}>
      {score}
    </div>
  );
};

export default React.memo(RiskBadge);
