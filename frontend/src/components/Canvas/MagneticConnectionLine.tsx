/**
 * Custom connection line rendered while dragging a new connection.
 * Shows a dashed line from source to cursor, plus curved guide lines
 * reaching from the cursor toward any compatible magnetic handles.
 */

import type { ConnectionLineComponentProps } from '@xyflow/react';
import { getStraightPath, useReactFlow } from '@xyflow/react';
import { useFlowStore } from '../../store/flowStore';

export function MagneticConnectionLine({
  fromX,
  fromY,
  toX,
  toY,
}: ConnectionLineComponentProps) {
  const [path] = getStraightPath({
    sourceX: fromX,
    sourceY: fromY,
    targetX: toX,
    targetY: toY,
  });

  const magneticTargets = useFlowStore((s) => s.magneticTargets);
  const { screenToFlowPosition } = useReactFlow();

  // Convert each magnetic target's screen coords to flow-space
  const guides = Object.entries(magneticTargets).map(([id, t]) => {
    const pos = screenToFlowPosition({ x: t.screenX, y: t.screenY });
    return { id, x: pos.x, y: pos.y, color: t.color };
  });

  return (
    <g>
      {/* Main drag line — dashed from source handle to cursor */}
      <path
        d={path}
        fill="none"
        stroke="rgba(255,255,255,0.25)"
        strokeWidth={2}
        strokeDasharray="6 4"
      />

      {/* Pulsing dot at cursor */}
      <circle cx={toX} cy={toY} r="4" fill="var(--color-accent)" opacity="0.7">
        <animate
          attributeName="opacity"
          values="0.5;1;0.5"
          dur="1s"
          repeatCount="indefinite"
        />
        <animate
          attributeName="r"
          values="3;5;3"
          dur="1s"
          repeatCount="indefinite"
        />
      </circle>

      {/* Guide curves from cursor to each compatible magnetic target */}
      {guides.map((g) => {
        const dx = g.x - toX;
        const dy = g.y - toY;
        const dist = Math.sqrt(dx * dx + dy * dy);

        // Opacity fades in as cursor gets closer (50px = full, farther = fainter)
        const opacity = Math.max(0, Math.min(0.6, 1 - dist / 80));

        // Quadratic bezier with a slight curve perpendicular to the line
        const midX = (toX + g.x) / 2;
        const midY = (toY + g.y) / 2;
        // Offset the control point perpendicular to the line for a nice arc
        const len = dist || 1;
        const nx = -dy / len; // normal x
        const ny = dx / len;  // normal y
        const curveOffset = Math.min(dist * 0.3, 25);
        const cx = midX + nx * curveOffset;
        const cy = midY + ny * curveOffset;

        const guidePath = `M ${toX} ${toY} Q ${cx} ${cy} ${g.x} ${g.y}`;

        return (
          <g key={g.id}>
            {/* Glow underneath */}
            <path
              d={guidePath}
              fill="none"
              stroke={g.color}
              strokeWidth={4}
              strokeLinecap="round"
              opacity={opacity * 0.3}
              style={{ filter: 'blur(3px)' }}
            />
            {/* Main guide line */}
            <path
              d={guidePath}
              fill="none"
              stroke={g.color}
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeDasharray="4 3"
              opacity={opacity}
            />
            {/* Small dot at the target handle */}
            <circle
              cx={g.x}
              cy={g.y}
              r="3"
              fill={g.color}
              opacity={opacity}
            >
              <animate
                attributeName="r"
                values="2;4;2"
                dur="0.8s"
                repeatCount="indefinite"
              />
            </circle>
          </g>
        );
      })}
    </g>
  );
}
