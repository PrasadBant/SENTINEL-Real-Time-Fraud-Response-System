import React from 'react';

/**
 * ActionButton — Contextual action trigger with role-aware styling.
 *
 * When disabled (viewer role), shows:
 *   - A 🔒 lock prefix on the label
 *   - Greyed out + no-pointer-events
 *   - Native tooltip via `title` attribute
 */
const ActionButton = ({ label, onClick, disabled, className = "", title }) => {
  const disabledTitle = disabled
    ? (title || 'Insufficient permissions — Viewer access cannot execute actions')
    : title;

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={disabledTitle}
      aria-label={disabled ? `${label} (locked — viewer role)` : label}
      className={`px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-semibold 
      hover:bg-primary/90 hover:shadow-primary/30 hover:-translate-y-0.5 active:scale-95 active:translate-y-0 transition-all duration-200 ease-spring shadow-lg shadow-primary/20 
      flex items-center justify-center gap-1.5
      ${disabled ? 'opacity-30 grayscale cursor-not-allowed pointer-events-none hover:translate-y-0 active:scale-100' : ''} ${className}`}
    >
      {disabled && <span className="text-xs" aria-hidden="true">🔒</span>}
      {label}
    </button>
  );
};

export default ActionButton;
