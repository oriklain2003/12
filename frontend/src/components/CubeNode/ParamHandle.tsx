/**
 * Color-coded React Flow handle component for a single param.
 * Renders a Handle with a label positioned to the left (target) or right (source).
 */

import { Handle, Position } from '@xyflow/react';
import { ParamType } from '../../types/cube';
import type { ParamDefinition } from '../../types/cube';

// ─── Handle color map (FRONT-05) ─────────────────────────────────────────────

export const PARAM_COLORS: Record<ParamType, string> = {
  [ParamType.STRING]: 'var(--color-param-string)',       // blue
  [ParamType.NUMBER]: 'var(--color-param-number)',       // green
  [ParamType.BOOLEAN]: 'var(--color-param-boolean)',     // orange
  [ParamType.LIST_OF_STRINGS]: 'var(--color-param-list)', // teal
  [ParamType.LIST_OF_NUMBERS]: 'var(--color-param-list)', // teal
  [ParamType.JSON_OBJECT]: 'var(--color-param-json)',    // gray
};

// ─── Component ───────────────────────────────────────────────────────────────

interface ParamHandleProps {
  param: ParamDefinition;
  type: 'source' | 'target';
  isConnectable: boolean;
}

export function ParamHandle({ param, type, isConnectable }: ParamHandleProps) {
  const position = type === 'target' ? Position.Left : Position.Right;
  const color = PARAM_COLORS[param.type];

  return (
    <Handle
      type={type}
      position={position}
      id={param.name}
      isConnectable={isConnectable}
      className="nodrag cube-node__handle"
      style={{
        background: color,
        width: 12,
        height: 12,
        borderRadius: 4,
        border: '2px solid rgba(0,0,0,0.3)',
      }}
    />
  );
}
