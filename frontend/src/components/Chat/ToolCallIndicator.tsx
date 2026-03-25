/**
 * ToolCallIndicator — inline row shown during agent tool dispatch.
 * Shows spinner while running, checkmark when completed.
 */

import './ChatPanel.css';

const TOOL_LABELS: Record<string, [string, string]> = {
  read_workflow_graph: ['Reading workflow graph...', 'Read workflow graph'],
  read_execution_errors: ['Reading execution errors...', 'Read execution errors'],
  read_execution_results: ['Reading execution results...', 'Read execution results'],
  get_cube_definition: ['Looking up cube definition...', 'Looked up cube definition'],
  list_cubes_summary: ['Browsing cube catalog...', 'Browsed cube catalog'],
  find_cubes_for_task: ['Searching for cubes...', 'Searched for cubes'],
  propose_graph_diff: ['Proposing changes...', 'Proposed changes'],
};

interface ToolCallIndicatorProps {
  toolName: string;
  done?: boolean;
}

export function ToolCallIndicator({ toolName, done }: ToolCallIndicatorProps) {
  const labels = TOOL_LABELS[toolName];
  const label = done
    ? (labels?.[1] ?? toolName)
    : (labels?.[0] ?? `Running ${toolName}...`);

  return (
    <div className={`tool-call-indicator${done ? ' tool-call-indicator--done' : ''}`}>
      {done ? (
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : (
        <svg
          className="tool-call-indicator__spinner"
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
        >
          <circle
            cx="6"
            cy="6"
            r="4.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeDasharray="14 8"
          />
        </svg>
      )}
      <span className="tool-call-indicator__label">{label}</span>
    </div>
  );
}
