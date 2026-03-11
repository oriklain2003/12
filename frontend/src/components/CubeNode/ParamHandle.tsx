/**
 * Color-coded React Flow handle component for a single param.
 * Renders a Handle with a label positioned to the left (target) or right (source).
 * Target handles detect proximity during connection drags for magnetic effects.
 */

import { useRef, useEffect, useState, useCallback } from 'react';
import { Handle, Position } from '@xyflow/react';
import { ParamType } from '../../types/cube';
import type { ParamDefinition } from '../../types/cube';
import { useFlowStore } from '../../store/flowStore';

// ─── Handle color map (FRONT-05) ─────────────────────────────────────────────

export const PARAM_COLORS: Record<ParamType, string> = {
  [ParamType.STRING]: 'var(--color-param-string)',       // blue
  [ParamType.NUMBER]: 'var(--color-param-number)',       // green
  [ParamType.BOOLEAN]: 'var(--color-param-boolean)',     // orange
  [ParamType.LIST_OF_STRINGS]: 'var(--color-param-list)', // teal
  [ParamType.LIST_OF_NUMBERS]: 'var(--color-param-list)', // teal
  [ParamType.JSON_OBJECT]: 'var(--color-param-json)',    // gray
};

// ─── Proximity threshold (px) ────────────────────────────────────────────────

const MAGNETIC_DISTANCE = 50;

// ─── Component ───────────────────────────────────────────────────────────────

interface ParamHandleProps {
  param: ParamDefinition;
  type: 'source' | 'target';
  isConnectable: boolean;
}

export function ParamHandle({ param, type, isConnectable }: ParamHandleProps) {
  const position = type === 'target' ? Position.Left : Position.Right;
  const color = PARAM_COLORS[param.type];
  const handleElRef = useRef<HTMLDivElement | null>(null);
  const [magneticState, setMagneticState] = useState<'compatible' | 'incompatible' | null>(null);

  const connectionDrag = useFlowStore((s) => s.connectionDrag);
  const registerMagneticTarget = useFlowStore((s) => s.registerMagneticTarget);
  const unregisterMagneticTarget = useFlowStore((s) => s.unregisterMagneticTarget);

  // Capture the Handle's actual DOM element via callback ref
  const handleRef = useCallback((el: HTMLDivElement | null) => {
    handleElRef.current = el;
  }, []);

  // Proximity detection for target handles only
  useEffect(() => {
    if (type !== 'target' || !connectionDrag) {
      setMagneticState(null);
      return;
    }

    const el = handleElRef.current;
    if (!el) return;

    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = connectionDrag.mouseX - cx;
    const dy = connectionDrag.mouseY - cy;
    const dist = Math.sqrt(dx * dx + dy * dy);

    if (dist < MAGNETIC_DISTANCE) {
      const typesMatch =
        connectionDrag.sourceParamType === null ||
        connectionDrag.sourceParamType === param.type ||
        // Full result (json_object) can connect to accepts_full_result inputs
        (connectionDrag.sourceHandleId === '__full_result__' && param.accepts_full_result);
      const newState = typesMatch ? 'compatible' : 'incompatible';
      setMagneticState(newState);

      // Register compatible targets so MagneticConnectionLine can draw guide lines
      if (newState === 'compatible') {
        registerMagneticTarget(param.name, cx, cy, color);
      } else {
        unregisterMagneticTarget(param.name);
      }
    } else {
      setMagneticState(null);
      unregisterMagneticTarget(param.name);
    }
  }, [connectionDrag, type, param.type, param.name, param.accepts_full_result, color, registerMagneticTarget, unregisterMagneticTarget]);

  const magneticClass =
    magneticState === 'compatible'
      ? 'cube-handle--magnetic'
      : magneticState === 'incompatible'
        ? 'cube-handle--repel'
        : '';

  return (
    <Handle
      ref={handleRef}
      type={type}
      position={position}
      id={param.name}
      isConnectable={isConnectable}
      className={`nodrag cube-node__handle ${magneticClass}`}
      style={{
        background: color,
        width: 12,
        height: 12,
        borderRadius: 4,
        border: '2px solid rgba(0,0,0,0.3)',
        '--glow-color': color,
        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
      } as React.CSSProperties}
    />
  );
}
