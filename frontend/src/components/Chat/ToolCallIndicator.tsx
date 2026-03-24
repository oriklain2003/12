/**
 * ToolCallIndicator — inline row shown during agent tool dispatch.
 * Renders a spinning SVG loader with a tool-specific human-readable label.
 */

import './ChatPanel.css';

const TOOL_LABELS: Record<string, string> = {
  read_workflow_graph: 'Reading workflow graph...',
  read_execution_errors: 'Reading execution errors...',
  read_execution_results: 'Reading execution results (capped at store limit)...',
  get_cube_definition: 'Looking up cube definition...',
  list_cubes_summary: 'Browsing cube catalog...',
  find_cubes_for_task: 'Browsing cube catalog...',
};

interface ToolCallIndicatorProps {
  toolName: string;
}

export function ToolCallIndicator({ toolName }: ToolCallIndicatorProps) {
  const label = TOOL_LABELS[toolName] ?? `Running ${toolName}...`;

  return (
    <div className="tool-call-indicator">
      <svg
        className="tool-call-indicator__spinner"
        width="12"
        height="12"
        viewBox="0 0 12 12"
        fill="none"
      >
        {/* stroke-dasharray creates the broken-arc spinner look */}
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
      <span className="tool-call-indicator__label">{label}</span>
    </div>
  );
}
