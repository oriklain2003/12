/**
 * Custom React Flow node component for a Cube.
 * Renders the cube header, input params (with handles + editors),
 * output params (with handles), Full Result handle, and results preview.
 *
 * Execution status indicators:
 *  - Header badge: gray (pending), blue spinner (running), green check (done), red X (error), dash (skipped)
 *  - Error banner: floats ABOVE the node content (absolute positioned, bottom: calc(100% + 6px))
 *  - Running glow: subtle box-shadow when the node is actively running
 */

import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { CubeCategory, ParamType } from '../../types/cube';
import type { CubeFlowNode } from '../../store/flowStore';
import { useFlowStore } from '../../store/flowStore';
import { PARAM_COLORS } from './ParamHandle';
import { ParamHandle } from './ParamHandle';
import { ParamField } from './ParamField';
import { ResultsPanel } from './ResultsPanel';
import './CubeNode.css';

// ─── Category color accent map ────────────────────────────────────────────────

const CATEGORY_COLORS: Record<CubeCategory, string> = {
  [CubeCategory.DATA_SOURCE]: '#6366f1', // indigo
  [CubeCategory.FILTER]: '#f59e0b',      // amber
  [CubeCategory.ANALYSIS]: '#8b5cf6',    // violet
  [CubeCategory.AGGREGATION]: '#06b6d4', // cyan
  [CubeCategory.OUTPUT]: '#10b981',      // emerald
};

// ─── Component ───────────────────────────────────────────────────────────────

export function CubeNode({ id, data, selected, isConnectable }: NodeProps<CubeFlowNode>) {
  const { cubeDef } = data;
  const categoryColor = CATEGORY_COLORS[cubeDef.category] ?? '#6b7280';
  const removeNode = useFlowStore((s) => s.removeNode);

  // Execution state from store — per-node status
  const executionStatus = useFlowStore((s) => s.executionStatus[id]);
  const isRunning = useFlowStore((s) => s.isRunning);

  // Build class list for the root node div
  const nodeClasses = [
    'cube-node',
    'glass--node',
    selected ? 'cube-node--selected' : '',
    executionStatus?.status === 'running' ? 'cube-node--running' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={nodeClasses}>
      {/* Error banner — absolute positioned ABOVE the node (bottom: calc(100% + 6px)) */}
      {executionStatus?.status === 'error' && executionStatus.error && (
        <div className="cube-node__error-banner">
          {executionStatus.error}
        </div>
      )}

      {/* Close button — hidden during execution to prevent accidental removal */}
      {!isRunning && (
        <button
          className="cube-node__close nodrag"
          onClick={() => removeNode(id)}
          aria-label="Remove node"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M1 1l8 8M9 1l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      )}

      {/* Header */}
      <div className="cube-node__header">
        <span className="cube-node__category-dot" style={{ background: categoryColor }} />
        <span className="cube-node__header-name">{cubeDef.name}</span>

        {/* Execution status indicator */}
        {executionStatus && (
          <span className={`cube-node__status cube-node__status--${executionStatus.status}`}>
            {executionStatus.status === 'running' && (
              <span className="cube-node__spinner" />
            )}
            {executionStatus.status === 'done' && (
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
            {executionStatus.status === 'error' && (
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            )}
            {executionStatus.status === 'skipped' && (
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2 6h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            )}
            {/* pending status: no icon — just the styled background circle via CSS */}
          </span>
        )}
      </div>

      <div className="cube-node__body">
        {/* Input params */}
        {cubeDef.inputs.length > 0 && (
          <>
            <div className="cube-node__section-label">Inputs</div>
            {cubeDef.inputs.map((param) => (
              <div key={param.name} className="cube-node__param-row cube-node__param-row--input">
                <ParamHandle param={param} type="target" isConnectable={isConnectable} />
                <div className="cube-node__param-content">
                  <span className="cube-node__param-label">{param.name}</span>
                  <ParamField nodeId={id} param={param} />
                </div>
              </div>
            ))}
          </>
        )}

        {/* Output params */}
        {cubeDef.outputs.length > 0 && (
          <>
            <div className="cube-node__section-label">Outputs</div>
            {cubeDef.outputs.map((param) => {
              // Skip the __full_result__ param — rendered separately below
              if (param.name === '__full_result__') return null;
              return (
                <div key={param.name} className="cube-node__param-row cube-node__param-row--output">
                  <ParamHandle param={param} type="source" isConnectable={isConnectable} />
                  <span className="cube-node__param-label">{param.name}</span>
                </div>
              );
            })}
          </>
        )}

        {/* Full Result handle — always present */}
        <div className="cube-node__full-result-row">
          <span className="cube-node__full-result-label">Full Result</span>
          <Handle
            type="source"
            position={Position.Right}
            id="__full_result__"
            isConnectable={isConnectable}
            className="nodrag cube-node__handle"
            style={{
              background: PARAM_COLORS[ParamType.JSON_OBJECT],
              width: 12,
              height: 12,
              borderRadius: 4,
              border: '2px solid rgba(0,0,0,0.3)',
            }}
          />
        </div>

        {/* Results preview */}
        <ResultsPanel nodeId={id} />
      </div>
    </div>
  );
}
