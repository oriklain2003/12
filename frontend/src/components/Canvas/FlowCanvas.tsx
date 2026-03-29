/**
 * React Flow canvas wrapper.
 * Handles:
 *  - Drop-from-sidebar to create cube nodes at drop position
 *  - Connection validation (Full Result rejection with toast, type-mismatch edge styling)
 *  - Dark theme, dot grid background, straight edges by default
 *
 * IMPORTANT: nodeTypes and edgeTypes are defined at MODULE LEVEL to prevent
 * React Flow from re-registering them on every render (React Flow v12 pattern).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  ConnectionLineType,
  MiniMap,
  Panel,
  useReactFlow,
  type Connection,
  type Edge,
  type IsValidConnection,
  type OnConnectStart,
} from '@xyflow/react';
import { useShallow } from 'zustand/react/shallow';
import { toast } from 'sonner';
import { CubeNode } from '../CubeNode/CubeNode';
import { MismatchEdge } from './MismatchEdge';
import { AnimatedEdge } from './AnimatedEdge';
import { LabeledStraightEdge } from './LabeledStraightEdge';
import { CommandPalette } from '../CommandPalette/CommandPalette';
import { MagneticConnectionLine } from './MagneticConnectionLine';
import { useFlowStore, type CubeFlowNode } from '../../store/flowStore';
import { ParamType } from '../../types/cube';
import type { AgentDiff } from '../../types/agent';
import './FlowCanvas.css';

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

// ─── Module-level type registrations (React Flow v12 requirement) ─────────────

const nodeTypes = { cube: CubeNode } as const;
const edgeTypes = { straight: LabeledStraightEdge, mismatch: MismatchEdge, animated: AnimatedEdge } as const;

// ─── Ghost preview builder ───────────────────────────────────────────────────

function buildGhostPreview(
  diff: AgentDiff,
  catalog: CubeFlowNode['data']['cubeDef'][],
) {
  const previewNodes: CubeFlowNode[] = [];
  const previewEdges: Edge[] = [];
  const removedNodeIds = new Set(diff.remove_node_ids ?? []);
  const removedEdgeIds = new Set(diff.remove_edge_ids ?? []);

  // Ghost nodes for additions — use deterministic IDs
  const addNodes = diff.add_nodes ?? [];
  for (let i = 0; i < addNodes.length; i++) {
    const n = addNodes[i];
    const cubeDef = catalog.find((c) => c.cube_id === n.cube_id);
    if (!cubeDef) continue;
    previewNodes.push({
      id: n.id ?? `ghost-${n.cube_id}-${i}`,
      type: 'cube',
      position: n.position,
      className: 'react-flow__node--ghost-add',
      data: {
        cube_id: n.cube_id,
        cubeDef,
        params: n.params ?? {},
        isPreview: true,
      },
      selectable: false,
      draggable: false,
      connectable: false,
    });
  }

  // Ghost edges for additions — use deterministic IDs
  const addEdges = diff.add_edges ?? [];
  for (let i = 0; i < addEdges.length; i++) {
    const e = addEdges[i];
    previewEdges.push({
      id: e.id ?? `ghost-edge-${i}`,
      source: e.source,
      target: e.target,
      sourceHandle: e.source_handle ?? null,
      targetHandle: e.target_handle ?? null,
      type: 'straight',
      className: 'react-flow__edge--ghost-add',
    });
  }

  return { previewNodes, previewEdges, removedNodeIds, removedEdgeIds };
}

// ─── Component ───────────────────────────────────────────────────────────────

export function FlowCanvas() {
  const { nodes, edges, onNodesChange, onEdgesChange } = useFlowStore(
    useShallow((s) => ({
      nodes: s.nodes,
      edges: s.edges,
      onNodesChange: s.onNodesChange,
      onEdgesChange: s.onEdgesChange,
    }))
  );
  const addCubeNode = useFlowStore((s) => s.addCubeNode);
  const pushSnapshot = useFlowStore((s) => s.pushSnapshot);
  const isRunning = useFlowStore((s) => s.isRunning);
  const isLoadingWorkflow = useFlowStore((s) => s.isLoadingWorkflow);
  const connectionDrag = useFlowStore((s) => s.connectionDrag);
  const startConnectionDrag = useFlowStore((s) => s.startConnectionDrag);

  const endConnectionDrag = useFlowStore((s) => s.endConnectionDrag);
  const reactFlowInstance = useReactFlow();
  const { screenToFlowPosition } = reactFlowInstance;

  // ── Command Palette state ───────────────────────────────────────────────────

  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (isRunning) return;
        setPaletteOpen((prev) => !prev);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isRunning]);

  // Tour can request the palette to open via custom event
  useEffect(() => {
    const handler = () => setPaletteOpen(true);
    document.addEventListener('tour:open-palette', handler);
    return () => document.removeEventListener('tour:open-palette', handler);
  }, []);

  // ── Connection drag handlers (magnetic handles) ────────────────────────────

  const onConnectStart = useCallback<OnConnectStart>((_event, params) => {
    if (params.nodeId && params.handleId) {
      startConnectionDrag(params.nodeId, params.handleId);
    }
  }, [startConnectionDrag]);

  const onConnectEnd = useCallback(() => {
    endConnectionDrag();
  }, [endConnectionDrag]);

  // Track mouse position during connection drag with RAF throttle
  const rafRef = useRef<number>(0);
  const isDragging = connectionDrag !== null;
  useEffect(() => {
    if (!isDragging) return;
    const onMouseMove = (e: MouseEvent) => {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        useFlowStore.getState().updateConnectionDragPosition(e.clientX, e.clientY);
      });
    };
    window.addEventListener('mousemove', onMouseMove);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      cancelAnimationFrame(rafRef.current);
    };
  }, [isDragging]);

  // ── Snapshot on node drag start (for undo) ──────────────────────────────────

  const onNodeDragStart = useCallback(() => {
    pushSnapshot();
  }, [pushSnapshot]);

  // ── Drop handler: receives cube-id from sidebar drag, creates node ──────────

  const onDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      const cubeId = event.dataTransfer.getData('application/cube-id');
      if (!cubeId) return;

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      addCubeNode(cubeId, position);
    },
    [screenToFlowPosition, addCubeNode]
  );

  // ── Connection validation: block Full Result → non-accepting inputs ─────────

  const isValidConnection = useCallback<IsValidConnection<Edge>>(
    (connection) => {
      const sourceHandle = connection.sourceHandle;
      const target = connection.target;
      const targetHandle = connection.targetHandle;
      const state = useFlowStore.getState();
      const targetNode = state.nodes.find((n) => n.id === target);
      if (!targetNode) return false;

      const targetParam = targetNode.data.cubeDef.inputs.find(
        (p) => p.name === targetHandle
      );
      if (!targetParam) return false;

      // Full Result rejection: show error toast and prevent the connection
      if (sourceHandle === '__full_result__' && !targetParam.accepts_full_result) {
        toast.error('This input does not accept Full Result');
        return false;
      }

      // Type mismatches are allowed — edge styling handles the visual warning
      return true;
    },
    []
  );

  // ── Custom onConnect: detect type mismatches and assign edge type ───────────

  const onConnect = useCallback((connection: Connection) => {
    const state = useFlowStore.getState();
    const sourceNode = state.nodes.find((n) => n.id === connection.source);
    const targetNode = state.nodes.find((n) => n.id === connection.target);
    if (!sourceNode || !targetNode) return;

    // Resolve source param type
    const sourceParam = sourceNode.data.cubeDef.outputs.find(
      (p) => p.name === connection.sourceHandle
    );
    // Full Result source uses JSON_OBJECT type
    const sourceType =
      connection.sourceHandle === '__full_result__'
        ? ParamType.JSON_OBJECT
        : sourceParam?.type;

    // Resolve target param type
    const targetParam = targetNode.data.cubeDef.inputs.find(
      (p) => p.name === connection.targetHandle
    );
    const targetType = targetParam?.type;

    const isMismatch =
      sourceType !== undefined &&
      targetType !== undefined &&
      sourceType !== targetType;

    const edge: Edge = {
      id: `${connection.source}-${connection.sourceHandle}-${connection.target}-${connection.targetHandle}`,
      source: connection.source!,
      target: connection.target!,
      sourceHandle: connection.sourceHandle,
      targetHandle: connection.targetHandle,
      type: isMismatch ? 'mismatch' : 'straight',
      style: isMismatch ? undefined : { stroke: 'rgba(255, 255, 255, 0.15)' },
    };

    // Add edge via store action (includes snapshot for undo)
    useFlowStore.getState().addTypedEdge(edge);
  }, []);

  // ── Ghost preview from pendingDiff ────────────────────────────────────────

  const pendingDiff = useFlowStore((s) => s.pendingDiff);
  const catalog = useFlowStore((s) => s.catalog);

  const { previewNodes, previewEdges, removedNodeIds, removedEdgeIds } = useMemo(() => {
    if (!pendingDiff) return { previewNodes: [] as CubeFlowNode[], previewEdges: [] as Edge[], removedNodeIds: new Set<string>(), removedEdgeIds: new Set<string>() };
    return buildGhostPreview(pendingDiff, catalog);
  }, [pendingDiff, catalog]);

  // ── Animated edges during execution ──────────────────────────────────────────

  const displayEdges = useMemo(() => {
    let result = edges;

    // Dim edges connected to removed nodes or explicitly removed edges
    if (removedNodeIds.size > 0 || removedEdgeIds.size > 0) {
      result = result.map((edge) => {
        if (removedEdgeIds.has(edge.id) || removedNodeIds.has(edge.source) || removedNodeIds.has(edge.target)) {
          return { ...edge, className: 'react-flow__edge--ghost-remove' };
        }
        return edge;
      });
    }

    if (isRunning) {
      result = result.map((edge) =>
        edge.type === 'mismatch'
          ? edge
          : { ...edge, type: 'animated' as const }
      );
    }

    return [...result, ...previewEdges];
  }, [edges, isRunning, previewEdges, removedNodeIds, removedEdgeIds]);

  // ── Display nodes with ghost previews ───────────────────────────────────────

  const displayNodes = useMemo(() => {
    let result = nodes;
    if (removedNodeIds.size > 0) {
      result = result.map((n) =>
        removedNodeIds.has(n.id)
          ? { ...n, className: 'react-flow__node--ghost-remove' }
          : n
      );
    }
    return [...result, ...previewNodes];
  }, [nodes, previewNodes, removedNodeIds]);

  // ── Render ──────────────────────────────────────────────────────────────────

  const handleFitView = useCallback(() => {
    reactFlowInstance.fitView({ padding: 0.2, duration: 300 });
  }, [reactFlowInstance]);

  return (
    <div className="flow-canvas" data-tour="canvas">
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      {isLoadingWorkflow && (
        <div className="flow-canvas__loading">
          <div className="flow-canvas__loading-spinner" />
          <span className="flow-canvas__loading-text">Loading workflow...</span>
        </div>
      )}
      {nodes.length === 0 && !isLoadingWorkflow && (
        <div className="flow-canvas__empty-guide">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="8" y="8" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
            <rect x="26" y="26" width="14" height="14" rx="3" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
            <path d="M22 15H30C31.1046 15 32 15.8954 32 17V26" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.3" />
          </svg>
          <p>Drag cubes from the sidebar to get started, or press <kbd>{isMac ? '⌘' : 'Ctrl'}+K</kbd> to open the command palette.</p>
        </div>
      )}
      <ReactFlow
        nodes={displayNodes}
        edges={displayEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onConnectStart={onConnectStart}
        onConnectEnd={onConnectEnd}
        onNodeDragStart={onNodeDragStart}
        isValidConnection={isValidConnection}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultEdgeOptions={{ type: 'straight' }}
        connectionLineType={ConnectionLineType.Straight}
        connectionLineComponent={MagneticConnectionLine}
        colorMode="dark"
        onDrop={onDrop}
        onDragOver={onDragOver}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={!isRunning}
        nodesConnectable={!isRunning}
        elementsSelectable={!isRunning}
        edgesReconnectable={!isRunning}
        deleteKeyCode={isRunning ? null : ['Delete', 'Backspace']}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={28}
          size={1}
          color="rgba(255,255,255,0.04)"
        />
        <MiniMap
          nodeColor="rgba(99, 102, 241, 0.5)"
          maskColor="rgba(0, 0, 0, 0.7)"
          style={{ backgroundColor: 'rgba(10, 12, 18, 0.8)' }}
          pannable
          zoomable
        />
        <Panel position="bottom-left">
          <button
            className="flow-canvas__fit-btn glass"
            onClick={handleFitView}
            title="Fit view"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M2 5V3C2 2.44772 2.44772 2 3 2H5M11 2H13C13.5523 2 14 2.44772 14 3V5M14 11V13C14 13.5523 13.5523 14 13 14H11M5 14H3C2.44772 14 2 13.5523 2 13V11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </Panel>
      </ReactFlow>
    </div>
  );
}
