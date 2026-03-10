/**
 * Specialized editor for relative time values stored as seconds.
 * Shows a number input + unit dropdown (seconds/minutes/hours/days).
 */

import { useState } from 'react';

interface RelativeTimeInputProps {
  value: number | undefined;
  onChange: (seconds: number) => void;
  placeholder?: string;
}

const UNITS = [
  { label: 'sec', factor: 1 },
  { label: 'min', factor: 60 },
  { label: 'hr', factor: 3600 },
  { label: 'day', factor: 86400 },
] as const;

function decompose(seconds: number): { amount: number; unitIndex: number } {
  // Find largest unit that divides evenly, or largest that gives >= 1
  for (let i = UNITS.length - 1; i > 0; i--) {
    if (seconds >= UNITS[i].factor && seconds % UNITS[i].factor === 0) {
      return { amount: seconds / UNITS[i].factor, unitIndex: i };
    }
  }
  return { amount: seconds, unitIndex: 0 };
}

export function RelativeTimeInput({ value, onChange, placeholder }: RelativeTimeInputProps) {
  const initial = decompose(value ?? 0);
  const [unitIndex, setUnitIndex] = useState(initial.unitIndex);

  const displayAmount = value != null ? value / UNITS[unitIndex].factor : '';

  const handleAmountChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.valueAsNumber;
    if (Number.isNaN(raw)) return;
    onChange(Math.round(raw * UNITS[unitIndex].factor));
  };

  const handleUnitChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newIdx = Number(e.target.value);
    setUnitIndex(newIdx);
    if (value != null) {
      // Re-store same total seconds — display will update via displayAmount
    }
  };

  return (
    <div className="relative-time-input nodrag nowheel">
      <input
        type="number"
        min={0}
        value={displayAmount}
        placeholder={placeholder}
        onChange={handleAmountChange}
      />
      <select value={unitIndex} onChange={handleUnitChange}>
        {UNITS.map((u, i) => (
          <option key={u.label} value={i}>{u.label}</option>
        ))}
      </select>
    </div>
  );
}
