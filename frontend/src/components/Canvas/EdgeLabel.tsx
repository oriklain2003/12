/**
 * Edge label overlay showing source → target param names.
 * Appears on hover or when the edge is selected.
 */

import { EdgeLabelRenderer } from '@xyflow/react';
import './EdgeLabel.css';

interface EdgeLabelProps {
  labelX: number;
  labelY: number;
  sourceHandle: string | null | undefined;
  targetHandle: string | null | undefined;
  selected?: boolean;
}

function formatHandle(handle: string | null | undefined): string {
  if (!handle) return '?';
  if (handle === '__full_result__') return 'Full Result';
  return handle;
}

export function EdgeLabel({ labelX, labelY, sourceHandle, targetHandle, selected }: EdgeLabelProps) {
  return (
    <EdgeLabelRenderer>
      <div
        className={`edge-label${selected ? ' edge-label--visible' : ''}`}
        style={{
          transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
        }}
      >
        <span className="edge-label__pill">
          {formatHandle(sourceHandle)}
          <span className="edge-label__arrow">→</span>
          {formatHandle(targetHandle)}
        </span>
      </div>
    </EdgeLabelRenderer>
  );
}
