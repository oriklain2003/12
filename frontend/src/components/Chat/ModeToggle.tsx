/**
 * ModeToggle — three-segment toggle for the agent chat panel.
 * Switches between Optimize, Fix, and General modes.
 * Does NOT clear chat messages on mode switch (per D-07).
 */

import { useFlowStore } from '../../store/flowStore';
import type { AgentMode } from '../../types/agent';

const MODES: { value: AgentMode; label: string }[] = [
  { value: 'optimize', label: 'Optimize' },
  { value: 'fix', label: 'Fix' },
  { value: 'general', label: 'General' },
];

export function ModeToggle() {
  const chatPanelMode = useFlowStore((s) => s.chatPanelMode);
  const setChatPanelMode = useFlowStore((s) => s.setChatPanelMode);
  const executionStatus = useFlowStore((s) => s.executionStatus);

  const hasErrors = Object.values(executionStatus).some((s) => s.status === 'error');

  return (
    <div className="mode-toggle" role="tablist" aria-label="Agent mode">
      {MODES.map(({ value, label }) => {
        const isActive = chatPanelMode === value;
        const showErrorDot = value === 'fix' && isActive && hasErrors;

        return (
          <button
            key={value}
            role="tab"
            aria-selected={isActive}
            className={`mode-toggle__segment${isActive ? ' mode-toggle__segment--active' : ''}`}
            onClick={() => setChatPanelMode(value)}
          >
            {showErrorDot && (
              <span className="mode-toggle__error-dot" aria-hidden="true" />
            )}
            {label}
          </button>
        );
      })}
    </div>
  );
}
