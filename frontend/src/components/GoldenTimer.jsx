import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

const GoldenTimer = ({ minutes }) => {
  const getTimerColor = (m) => {
    if (m > 15) return "text-green-500";
    if (m >= 5) return "text-amber-500";
    return "text-red-500";
  };

  const formatTime = (m) => {
    const totalSeconds = m * 60;
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  return (
    <div className={twMerge("font-mono font-bold flex items-center gap-1", getTimerColor(minutes))}>
      <span className="text-[10px] uppercase opacity-50">Window:</span>
      {formatTime(minutes)}
    </div>
  );
};

export default GoldenTimer;
