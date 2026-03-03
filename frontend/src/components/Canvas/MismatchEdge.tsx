/**
 * Custom React Flow edge for type-mismatched connections.
 * Renders as a dashed orange straight line to visually indicate
 * that the source and target param types do not match.
 */

import { getStraightPath, BaseEdge, type EdgeProps } from '@xyflow/react';

export function MismatchEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  ...rest
}: EdgeProps) {
  const [edgePath] = getStraightPath({ sourceX, sourceY, targetX, targetY });

  return (
    <BaseEdge
      id={id}
      path={edgePath}
      style={{
        stroke: 'var(--color-warning)',
        strokeDasharray: '6 3',
        strokeWidth: 2,
      }}
      {...rest}
    />
  );
}
