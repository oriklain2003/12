/**
 * Custom React Flow edge with multi-particle data flow animation.
 * Shows colored particles streaming along the edge path when the
 * source node is running, with a burst effect on completion.
 */

import { useRef, useMemo } from 'react';
import { getStraightPath, BaseEdge, type EdgeProps } from '@xyflow/react';
import { useFlowStore } from '../../store/flowStore';
import { PARAM_COLORS } from '../CubeNode/ParamHandle';
import { EdgeLabel } from './EdgeLabel';

// ─── Particle config ─────────────────────────────────────────────────────────

interface Particle {
  radius: number;
  opacity: number;
  duration: number;
  begin: number;
}

function buildParticles(count: number, baseDuration: number): Particle[] {
  return Array.from({ length: count }, (_, i) => ({
    radius: 2 + (i % 3),                          // 2-4px
    opacity: 0.5 + (i % 5) * 0.1,                 // 0.5-0.9
    duration: baseDuration + i * 0.08,             // stagger durations
    begin: (i / count) * baseDuration,             // spread starts evenly
  }));
}

// ─── Component ───────────────────────────────────────────────────────────────

export function AnimatedEdge({
  id,
  source,
  sourceX,
  sourceY,
  sourceHandleId: sourceHandle,
  targetX,
  targetY,
  targetHandleId: targetHandle,
  selected,
  selectable: _selectable,
  deletable: _deletable,
  sourcePosition: _sourcePosition,
  targetPosition: _targetPosition,
  pathOptions: _pathOptions,
  ...rest
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getStraightPath({ sourceX, sourceY, targetX, targetY });

  const sourceStatus = useFlowStore((s) => s.executionStatus[source]?.status);
  const sourceNode = useFlowStore((s) => s.nodes.find((n) => n.id === source));
  const prevStatusRef = useRef(sourceStatus);

  const isActive = sourceStatus === 'running' || sourceStatus === 'done';
  const justFinished =
    prevStatusRef.current === 'running' && sourceStatus === 'done';

  // Update ref after reading it
  if (sourceStatus !== prevStatusRef.current) {
    prevStatusRef.current = sourceStatus;
  }

  // Resolve the param color from the source handle's ParamType
  const paramColor = useMemo(() => {
    if (!sourceNode || !sourceHandle) return 'var(--color-accent)';
    if (sourceHandle === '__full_result__') return 'var(--color-accent)';
    const paramDef = sourceNode.data.cubeDef.outputs.find(
      (p) => p.name === sourceHandle,
    );
    if (!paramDef) return 'var(--color-accent)';
    return PARAM_COLORS[paramDef.type] ?? 'var(--color-accent)';
  }, [sourceNode, sourceHandle]);

  // Build particle array: 7 when running, 3 when done
  const particles = useMemo(() => {
    if (!isActive) return [];
    const count = sourceStatus === 'running' ? 7 : 3;
    const baseDuration = sourceStatus === 'running' ? 1.2 : 2.0;
    return buildParticles(count, baseDuration);
  }, [isActive, sourceStatus]);

  const filterId = `particle-glow-${id}`;

  return (
    <>
      {/* Edge path — glows when active */}
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: isActive ? paramColor : 'rgba(255,255,255,0.15)',
          strokeWidth: 2,
          opacity: isActive ? 0.3 : 1,
          filter: isActive ? `drop-shadow(0 0 4px ${paramColor})` : undefined,
        }}
        {...rest}
      />

      {isActive && (
        <>
          {/* Glow filter definition */}
          <defs>
            <filter id={filterId}>
              <feGaussianBlur stdDeviation="2" in="SourceGraphic" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Particles */}
          {particles.map((p, i) => (
            <circle
              key={i}
              r={p.radius}
              fill={paramColor}
              filter={`url(#${filterId})`}
              className={justFinished ? 'particle-burst' : undefined}
            >
              <animateMotion
                dur={`${p.duration}s`}
                repeatCount="indefinite"
                begin={`${p.begin}s`}
                path={edgePath}
              />
              <animate
                attributeName="opacity"
                values={`0;${p.opacity};${p.opacity};0`}
                keyTimes="0;0.1;0.9;1"
                dur={`${p.duration}s`}
                repeatCount="indefinite"
                begin={`${p.begin}s`}
              />
            </circle>
          ))}
        </>
      )}

      <EdgeLabel
        labelX={labelX}
        labelY={labelY}
        sourceHandle={sourceHandle}
        targetHandle={targetHandle}
        selected={selected}
      />
    </>
  );
}
