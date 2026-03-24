/**
 * IssuesPanel — collapsible panel below the canvas showing validation issues.
 *
 * Reads validationIssues, showIssuesPanel, highlightedNodeId from Zustand.
 * Clicking an issue row highlights the relevant canvas node and fits it into view.
 *
 * Must be rendered inside a ReactFlowProvider context (EditorPage provides this).
 */

import { useState, useEffect } from 'react';
import { useReactFlow } from '@xyflow/react';
import { useFlowStore } from '../../store/flowStore';
import type { ValidationIssue } from '../../api/agent';
import './IssuesPanel.css';

function IssueRow({ issue, onClick }: { issue: ValidationIssue; onClick: () => void }) {
  const severityClass = issue.severity === 'error' ? 'issues-panel__row--error' : 'issues-panel__row--warning';
  const iconColor = issue.severity === 'error' ? 'var(--color-error)' : 'var(--color-warning)';

  return (
    <div
      className={`issues-panel__row ${severityClass}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClick(); }}
    >
      <span className="issues-panel__icon" style={{ color: iconColor }}>●</span>
      {issue.cube_name && (
        <span className="issues-panel__cube-name">{issue.cube_name}</span>
      )}
      {issue.cube_name && issue.param_name && (
        <span className="issues-panel__separator">›</span>
      )}
      {issue.param_name && (
        <span className="issues-panel__param-name">{issue.param_name}</span>
      )}
      <span className="issues-panel__message">{issue.message}</span>
    </div>
  );
}

export function IssuesPanel() {
  const validationIssues = useFlowStore((s) => s.validationIssues);
  const showIssuesPanel = useFlowStore((s) => s.showIssuesPanel);
  const setHighlightedNodeId = useFlowStore((s) => s.setHighlightedNodeId);
  const { fitView } = useReactFlow();

  const errorCount = validationIssues.filter((i) => i.severity === 'error').length;
  const warningCount = validationIssues.filter((i) => i.severity === 'warning').length;
  const hasErrors = errorCount > 0;

  // Start expanded when errors block execution; collapsed otherwise
  const [isExpanded, setIsExpanded] = useState(hasErrors);

  // Sync expansion when issues panel is opened/updated
  useEffect(() => {
    if (showIssuesPanel) {
      setIsExpanded(hasErrors);
    }
  }, [showIssuesPanel, hasErrors]);

  if (!showIssuesPanel) return null;

  const handleIssueClick = (issue: ValidationIssue) => {
    if (issue.node_id) {
      setHighlightedNodeId(issue.node_id);
      fitView({ nodes: [{ id: issue.node_id }], padding: 0.3, duration: 300 });
    }
  };

  const errorLabel = errorCount === 1 ? '1 error' : `${errorCount} errors`;
  const warningLabel = warningCount === 1 ? '1 warning' : `${warningCount} warnings`;

  return (
    <div className="issues-panel">
      <div className="issues-panel__header">
        <span className="issues-panel__heading">ISSUES</span>
        {errorCount > 0 && (
          <span className="issues-panel__count issues-panel__count--error">{errorLabel}</span>
        )}
        {errorCount > 0 && warningCount > 0 && (
          <span className="issues-panel__count-sep">·</span>
        )}
        {warningCount > 0 && (
          <span className="issues-panel__count issues-panel__count--warning">{warningLabel}</span>
        )}
        <button
          className="issues-panel__toggle"
          onClick={() => setIsExpanded((v) => !v)}
          aria-label={isExpanded ? 'Collapse issues panel' : 'Expand issues panel'}
        >
          {isExpanded ? '▲' : '▼'}
        </button>
      </div>

      {isExpanded && (
        <div className="issues-panel__body">
          {validationIssues.map((issue, idx) => (
            <IssueRow
              key={`${issue.rule}-${issue.node_id}-${idx}`}
              issue={issue}
              onClick={() => handleIssueClick(issue)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
