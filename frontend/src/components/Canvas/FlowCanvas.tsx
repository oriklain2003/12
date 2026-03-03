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

import { useCallback } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  useReactFlow,
  type Connection,
  type Edge,
  type IsValidConnection,
} from '@xyflow/react';
import { toast } from 'sonner';
import { CubeNode } from '../CubeNode/CubeNode';
import { MismatchEdge } from './MismatchEdge';
import { useFlowStore } from '../../store/flowStore';
import { ParamType } from '../../types/cube';
import './FlowCanvas.css';

// ─── Module-level type registrations (React Flow v12 requirement) ─────────────

const nodeTypes = { cube: CubeNode } as const;
const edgeTypes = { mismatch: MismatchEdge } as const;

// ─── Component ───────────────────────────────────────────────────────────────

export function FlowCanvas() {
  const { nodes, edges, onNodesChange, onEdgesChange } = useFlowStore();
  const addCubeNode = useFlowStore((s) => s.addCubeNode);
  const { screenToFlowPosition } = useReactFlow();

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
      style: isMismatch ? undefined : { stroke: '#4b5563' },
    };

    // Directly update edges in the store
    useFlowStore.setState((s) => ({ edges: [...s.edges, edge] }));
  }, []);

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="flow-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        isValidConnection={isValidConnection}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultEdgeOptions={{ type: 'straight' }}
        colorMode="dark"
        onDrop={onDrop}
        onDragOver={onDragOver}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1}
          color="rgba(255,255,255,0.07)"
        />
      </ReactFlow>
    </div>
  );
}
