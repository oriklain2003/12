/**
 * Compact results preview panel shown at the bottom of a CubeNode.
 * Displays row count and a short preview of the first few values.
 */

import { useFlowStore } from '../../store/flowStore';
import './ResultsPanel.css';

interface ResultsPanelProps {
  nodeId: string;
}

export function ResultsPanel({ nodeId }: ResultsPanelProps) {
  const result = useFlowStore((s) => s.results[nodeId]);

  if (!result) return null;

  const { rows, truncated } = result;

  // Build a short preview string from the first 2–3 rows
  const previewValues = rows.slice(0, 3).map((row) => {
    if (row === null || row === undefined) return 'null';
    if (typeof row === 'object') {
      // Show first value of the row object
      const values = Object.values(row as Record<string, unknown>);
      return values.length > 0 ? String(values[0]) : '{}';
    }
    return String(row);
  });

  const preview = previewValues.join(', ') + (rows.length > 3 ? '…' : '');

  return (
    <div className="results-panel">
      <div className={`results-panel__count${truncated ? ' results-panel__count--truncated' : ''}`}>
        {rows.length} row{rows.length !== 1 ? 's' : ''}{truncated ? ' (truncated)' : ''}
      </div>
      {preview && <div className="results-panel__preview">{preview}</div>}
    </div>
  );
}
