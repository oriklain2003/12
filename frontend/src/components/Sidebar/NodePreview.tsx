import { createPortal } from 'react-dom';
import type { CubeDefinition } from '../../types/cube';
import { CubeCategory } from '../../types/cube';
import './NodePreview.css';

const CATEGORY_COLORS: Record<CubeCategory, string> = {
  [CubeCategory.DATA_SOURCE]: '#6366f1',
  [CubeCategory.FILTER]: '#f59e0b',
  [CubeCategory.ANALYSIS]: '#8b5cf6',
  [CubeCategory.AGGREGATION]: '#06b6d4',
  [CubeCategory.OUTPUT]: '#10b981',
};

interface NodePreviewProps {
  cube: CubeDefinition;
  rect: DOMRect;
}

export function NodePreview({ cube, rect }: NodePreviewProps) {
  const inputCount = cube.inputs.length;
  const outputCount = cube.outputs.filter((p) => p.name !== '__full_result__').length;
  const color = CATEGORY_COLORS[cube.category] ?? '#6b7280';

  return createPortal(
    <div
      className="node-preview"
      style={{ left: rect.right + 12, top: rect.top }}
    >
      <div className="node-preview__header">
        <span className="node-preview__dot" style={{ background: color }} />
        <span className="node-preview__name">{cube.name}</span>
      </div>
      <div className="node-preview__summary">
        {inputCount} input{inputCount !== 1 ? 's' : ''}, {outputCount} output{outputCount !== 1 ? 's' : ''}
      </div>
    </div>,
    document.body
  );
}
