/**
 * MiniGraph — SVG mini-graph preview from show_intent_preview tool.
 * Renders cube nodes as rounded rectangles connected by directed lines.
 * Layout: topological depth ordering (x = depth × 160px, y = index × 64px).
 */

import { useState, useMemo } from 'react';
import type { IntentPreviewData } from '../../types/wizard';
import './MiniGraph.css';

interface MiniGraphProps {
  data: IntentPreviewData;
  onBuild: () => void;
  onAdjust: () => void;
  disabled?: boolean;
}

const NODE_WIDTH = 120;
const NODE_HEIGHT = 44;
const COL_GAP = 160;
const ROW_GAP = 64;
const PADDING = 20;
const ARROW_SIZE = 6;

interface LayoutNode {
  id: string;
  label: string;
  x: number;
  y: number;
}

function computeLayout(
  nodes: IntentPreviewData['nodes'],
  connections: IntentPreviewData['connections']
): LayoutNode[] {
  if (nodes.length === 0) return [];

  // Build adjacency and compute depths via BFS
  const depthMap = new Map<string, number>();
  const children = new Map<string, string[]>();

  for (const node of nodes) {
    depthMap.set(node.cube_id, 0);
    children.set(node.cube_id, []);
  }

  for (const conn of connections) {
    children.get(conn.from_cube)?.push(conn.to_cube);
  }

  // BFS from roots (nodes with no incoming edges)
  const hasIncoming = new Set(connections.map((c) => c.to_cube));
  const roots = nodes.filter((n) => !hasIncoming.has(n.cube_id));
  const queue = roots.map((n) => n.cube_id);

  while (queue.length > 0) {
    const current = queue.shift()!;
    const currentDepth = depthMap.get(current) ?? 0;
    for (const child of children.get(current) ?? []) {
      const existingDepth = depthMap.get(child) ?? 0;
      if (existingDepth <= currentDepth) {
        depthMap.set(child, currentDepth + 1);
        queue.push(child);
      }
    }
  }

  // Group by depth
  const byDepth = new Map<number, string[]>();
  for (const [id, depth] of depthMap) {
    if (!byDepth.has(depth)) byDepth.set(depth, []);
    byDepth.get(depth)!.push(id);
  }

  // Assign positions
  const positions = new Map<string, { x: number; y: number }>();
  for (const [depth, ids] of byDepth) {
    ids.forEach((id, index) => {
      positions.set(id, {
        x: PADDING + depth * COL_GAP,
        y: PADDING + index * ROW_GAP,
      });
    });
  }

  return nodes.map((node) => {
    const pos = positions.get(node.cube_id) ?? { x: PADDING, y: PADDING };
    return { id: node.cube_id, label: node.label, x: pos.x, y: pos.y };
  });
}

export function MiniGraph({ data, onBuild, onAdjust, disabled }: MiniGraphProps) {
  const [building, setBuilding] = useState(false);

  const layoutNodes = useMemo(
    () => computeLayout(data.nodes, data.connections),
    [data.nodes, data.connections]
  );

  const posMap = useMemo(() => {
    const m = new Map<string, LayoutNode>();
    for (const n of layoutNodes) m.set(n.id, n);
    return m;
  }, [layoutNodes]);

  // Compute SVG viewBox from node positions
  const svgWidth = useMemo(() => {
    if (layoutNodes.length === 0) return 200;
    const maxX = Math.max(...layoutNodes.map((n) => n.x + NODE_WIDTH));
    return maxX + PADDING;
  }, [layoutNodes]);

  const svgHeight = useMemo(() => {
    if (layoutNodes.length === 0) return 100;
    const maxY = Math.max(...layoutNodes.map((n) => n.y + NODE_HEIGHT));
    return maxY + PADDING;
  }, [layoutNodes]);

  function handleBuild() {
    if (building || disabled) return;
    setBuilding(true);
    onBuild();
  }

  return (
    <div className="mini-graph glass">
      <svg
        className="mini-graph__svg"
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Workflow graph preview"
      >
        <defs>
          <marker
            id="mini-graph-arrow"
            markerWidth={ARROW_SIZE}
            markerHeight={ARROW_SIZE}
            refX={ARROW_SIZE - 1}
            refY={ARROW_SIZE / 2}
            orient="auto"
          >
            <path
              d={`M0,0 L0,${ARROW_SIZE} L${ARROW_SIZE},${ARROW_SIZE / 2} z`}
              fill="rgba(255, 255, 255, 0.25)"
            />
          </marker>
        </defs>

        {/* Connection lines */}
        {data.connections.map((conn, i) => {
          const from = posMap.get(conn.from_cube);
          const to = posMap.get(conn.to_cube);
          if (!from || !to) return null;

          const x1 = from.x + NODE_WIDTH;
          const y1 = from.y + NODE_HEIGHT / 2;
          const x2 = to.x;
          const y2 = to.y + NODE_HEIGHT / 2;

          return (
            <line
              key={`conn-${i}`}
              x1={x1}
              y1={y1}
              x2={x2 - ARROW_SIZE + 1}
              y2={y2}
              stroke="rgba(255, 255, 255, 0.25)"
              strokeWidth={1.5}
              markerEnd="url(#mini-graph-arrow)"
            />
          );
        })}

        {/* Node rectangles */}
        {layoutNodes.map((node) => (
          <g key={node.id}>
            <rect
              x={node.x}
              y={node.y}
              width={NODE_WIDTH}
              height={NODE_HEIGHT}
              rx={8}
              fill="var(--color-surface-raised)"
              stroke="rgba(255, 255, 255, 0.12)"
              strokeWidth={1}
            />
            <text
              x={node.x + NODE_WIDTH / 2}
              y={node.y + NODE_HEIGHT / 2}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="rgba(255, 255, 255, 0.92)"
              fontSize={12}
              fontWeight={400}
              fontFamily="'DM Sans', system-ui, sans-serif"
            >
              <tspan>{node.label.length > 14 ? node.label.slice(0, 13) + '…' : node.label}</tspan>
            </text>
          </g>
        ))}
      </svg>

      <div className="mini-graph__info">
        <div className="mini-graph__mission-name">{data.mission_name}</div>
        {data.mission_description && (
          <div className="mini-graph__mission-description">{data.mission_description}</div>
        )}
      </div>

      <div className="mini-graph__actions">
        <button
          className="glass-btn"
          onClick={onAdjust}
          disabled={building || disabled}
          type="button"
          style={{ fontSize: 13, fontWeight: 600, padding: '8px 16px' }}
        >
          Adjust Plan
        </button>
        <button
          className="glass-btn glass-btn--accent"
          onClick={handleBuild}
          disabled={building || disabled}
          type="button"
          style={{ fontSize: 13, fontWeight: 600, padding: '8px 16px' }}
        >
          {building ? (
            <>
              <span className="mini-graph__pulse-dot" />
              Building...
            </>
          ) : (
            'Build This'
          )}
        </button>
      </div>
    </div>
  );
}
