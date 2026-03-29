/**
 * MiniGraph — mini workflow preview from show_intent_preview tool.
 * Renders cube nodes styled like the real canvas with category colors,
 * key params, and directed connection lines between them.
 */

import { useMemo } from 'react';
import type { IntentPreviewData, IntentPreviewNode, IntentPreviewConnection } from '../../types/wizard';
import './MiniGraph.css';

interface MiniGraphProps {
  data: IntentPreviewData;
  onBuild: () => void;
  onAdjust: () => void;
  disabled?: boolean;
  building?: boolean;
}

const CATEGORY_COLORS: Record<string, string> = {
  data_source: '#6366f1',
  filter: '#f59e0b',
  analysis: '#8b5cf6',
  aggregation: '#06b6d4',
  output: '#10b981',
};

const CATEGORY_LABELS: Record<string, string> = {
  data_source: 'Source',
  filter: 'Filter',
  analysis: 'Analysis',
  aggregation: 'Aggregation',
  output: 'Output',
};

const NODE_WIDTH = 200;
const NODE_GAP_X = 60;
const NODE_GAP_Y = 16;

interface LayoutNode {
  id: string;
  label: string;
  category: string;
  keyParams: Record<string, unknown>;
  x: number;
  y: number;
  height: number;
}

function computeLayout(
  nodes: IntentPreviewNode[],
  connections: IntentPreviewConnection[]
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

  // BFS from roots
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

  // Estimate node height based on key_params count
  function nodeHeight(node: IntentPreviewNode): number {
    const paramCount = Object.keys(node.key_params ?? {}).length;
    return 36 + Math.max(paramCount, 0) * 22; // header + params
  }

  // Group by depth and assign positions
  const byDepth = new Map<number, IntentPreviewNode[]>();
  for (const node of nodes) {
    const depth = depthMap.get(node.cube_id) ?? 0;
    if (!byDepth.has(depth)) byDepth.set(depth, []);
    byDepth.get(depth)!.push(node);
  }

  const result: LayoutNode[] = [];
  for (const [depth, depthNodes] of byDepth) {
    let y = 0;
    for (const node of depthNodes) {
      const h = nodeHeight(node);
      result.push({
        id: node.cube_id,
        label: node.label,
        category: node.category ?? 'filter',
        keyParams: node.key_params ?? {},
        x: depth * (NODE_WIDTH + NODE_GAP_X),
        y,
        height: h,
      });
      y += h + NODE_GAP_Y;
    }
  }

  // Center columns vertically relative to the tallest column
  const maxColHeight = Math.max(
    ...Array.from(byDepth.values()).map((depthNodes) => {
      let total = 0;
      for (const n of depthNodes) total += nodeHeight(n) + NODE_GAP_Y;
      return total - NODE_GAP_Y;
    })
  );

  for (const [depth, depthNodes] of byDepth) {
    let colHeight = 0;
    for (const n of depthNodes) colHeight += nodeHeight(n) + NODE_GAP_Y;
    colHeight -= NODE_GAP_Y;
    const offset = (maxColHeight - colHeight) / 2;
    for (const layoutNode of result) {
      if (depthMap.get(layoutNode.id) === depth) {
        layoutNode.y += offset;
      }
    }
  }

  return result;
}

function formatParamValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'object' && value !== null) return JSON.stringify(value);
  return String(value);
}

export function MiniGraph({ data, onBuild, onAdjust, disabled, building }: MiniGraphProps) {
  const layoutNodes = useMemo(
    () => computeLayout(data.nodes, data.connections),
    [data.nodes, data.connections]
  );

  const posMap = useMemo(() => {
    const m = new Map<string, LayoutNode>();
    for (const n of layoutNodes) m.set(n.id, n);
    return m;
  }, [layoutNodes]);

  const canvasSize = useMemo(() => {
    if (layoutNodes.length === 0) return { width: 200, height: 80 };
    const maxX = Math.max(...layoutNodes.map((n) => n.x + NODE_WIDTH));
    const maxY = Math.max(...layoutNodes.map((n) => n.y + n.height));
    return { width: maxX, height: maxY };
  }, [layoutNodes]);

  function handleBuild() {
    if (building || disabled) return;
    onBuild();
  }

  return (
    <div className="mini-graph glass">
      <div
        className="mini-graph__canvas"
        style={{ width: canvasSize.width, height: canvasSize.height }}
      >
        {/* Connection lines (SVG overlay) */}
        <svg className="mini-graph__connections" aria-hidden="true">
          <defs>
            <marker
              id="mini-arrow"
              markerWidth={6}
              markerHeight={6}
              refX={5}
              refY={3}
              orient="auto"
            >
              <path d="M0,0 L0,6 L6,3 z" fill="rgba(255,255,255,0.3)" />
            </marker>
          </defs>
          {data.connections.map((conn, i) => {
            const from = posMap.get(conn.from_cube);
            const to = posMap.get(conn.to_cube);
            if (!from || !to) return null;

            const x1 = from.x + NODE_WIDTH;
            const y1 = from.y + from.height / 2;
            const x2 = to.x;
            const y2 = to.y + to.height / 2;
            const midX = (x1 + x2) / 2;

            return (
              <path
                key={`conn-${i}`}
                d={`M${x1},${y1} C${midX},${y1} ${midX},${y2} ${x2},${y2}`}
                fill="none"
                stroke="rgba(255,255,255,0.2)"
                strokeWidth={1.5}
                markerEnd="url(#mini-arrow)"
              />
            );
          })}
        </svg>

        {/* Node cards */}
        {layoutNodes.map((node) => {
          const color = CATEGORY_COLORS[node.category] ?? '#6366f1';
          const categoryLabel = CATEGORY_LABELS[node.category] ?? node.category;
          const params = Object.entries(node.keyParams);

          return (
            <div
              key={node.id}
              className="mini-graph__node"
              style={{
                left: node.x,
                top: node.y,
                width: NODE_WIDTH,
                borderColor: `${color}33`,
              }}
            >
              <div className="mini-graph__node-header">
                <span
                  className="mini-graph__node-dot"
                  style={{ background: color }}
                />
                <span className="mini-graph__node-name">{node.label}</span>
              </div>
              {params.length > 0 && (
                <div className="mini-graph__node-params">
                  {params.map(([key, value]) => (
                    <div key={key} className="mini-graph__node-param">
                      <span className="mini-graph__param-key">{key}</span>
                      <span className="mini-graph__param-value">
                        {formatParamValue(value)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <div
                className="mini-graph__node-category"
                style={{ color }}
              >
                {categoryLabel}
              </div>
            </div>
          );
        })}
      </div>

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
        >
          Adjust Plan
        </button>
        <button
          className="glass-btn glass-btn--accent"
          onClick={handleBuild}
          disabled={building || disabled}
          type="button"
        >
          {building ? (
            <>
              <span className="mini-graph__pulse-dot" />
              Building…
            </>
          ) : (
            'Build This'
          )}
        </button>
      </div>
    </div>
  );
}
