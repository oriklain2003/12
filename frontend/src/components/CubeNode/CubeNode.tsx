/**
 * Custom React Flow node component for a Cube.
 * Renders the cube header, input params (with handles + editors),
 * output params (with handles), Full Result handle, and results preview.
 */

import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { CubeCategory, ParamType } from '../../types/cube';
import type { CubeFlowNode } from '../../store/flowStore';
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

export function CubeNode({ id, data, isConnectable }: NodeProps<CubeFlowNode>) {
  const { cubeDef } = data;
  const categoryColor = CATEGORY_COLORS[cubeDef.category] ?? '#6b7280';

  return (
    <div className="cube-node glass">
      {/* Header */}
      <div
        className="cube-node__header"
        style={{ borderLeftColor: categoryColor }}
      >
        <span className="cube-node__header-name">{cubeDef.name}</span>
      </div>

      <div className="cube-node__body">
        {/* Input params */}
        {cubeDef.inputs.length > 0 && (
          <>
            <div className="cube-node__section-label">Inputs</div>
            {cubeDef.inputs.map((param) => (
              <div key={param.name} className="cube-node__param-row cube-node__param-row--input">
                <ParamHandle param={param} type="target" isConnectable={isConnectable} />
                <ParamField nodeId={id} param={param} />
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
            className="nodrag"
            style={{
              background: PARAM_COLORS[ParamType.JSON_OBJECT],
              width: 10,
              height: 10,
              border: '2px solid rgba(0,0,0,0.4)',
            }}
          />
        </div>

        {/* Results preview */}
        <ResultsPanel nodeId={id} />
      </div>
    </div>
  );
}
