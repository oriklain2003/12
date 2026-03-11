/**
 * Straight edge with param label overlay.
 * Replaces the built-in 'straight' edge type to add EdgeLabel support.
 */

import { getStraightPath, BaseEdge, type EdgeProps } from '@xyflow/react';
import { EdgeLabel } from './EdgeLabel';

export function LabeledStraightEdge({
  id,
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

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{ stroke: 'rgba(255, 255, 255, 0.15)' }}
        {...rest}
      />
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
