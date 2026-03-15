/**
 * Multi-select chips for LIST_OF_STRINGS params with predefined options.
 * Users click chips to toggle selection — no free-text input.
 */

import { useCallback } from 'react';
import './MultiSelectChips.css';

interface MultiSelectChipsProps {
  options: string[];
  value: string[];
  onChange: (selected: string[]) => void;
}

export function MultiSelectChips({ options, value, onChange }: MultiSelectChipsProps) {
  const toggle = useCallback(
    (opt: string) => {
      // "all" is exclusive — selecting it clears others, selecting others clears "all"
      if (opt === 'all') {
        onChange(value.includes('all') ? [] : ['all']);
        return;
      }

      const next = value.includes(opt)
        ? value.filter((v) => v !== opt)
        : [...value.filter((v) => v !== 'all'), opt];

      onChange(next.length === 0 ? ['all'] : next);
    },
    [value, onChange],
  );

  return (
    <div className="multi-chips nodrag nowheel">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          className={`multi-chips__chip${value.includes(opt) ? ' multi-chips__chip--active' : ''}`}
          onClick={() => toggle(opt)}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
