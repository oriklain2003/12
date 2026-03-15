/**
 * Central Zustand store for the visual workflow canvas.
 * Single source of truth for nodes, edges, catalog, results,
 * workflow metadata, and execution state.
 */

import { create } from 'zustand';
import type { Node, Edge, NodeChange, EdgeChange, Connection } from '@xyflow/react';
import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react';
import type { CubeDefinition } from '../types/cube';
import { ParamType } from '../types/cube';
import type { CubeStatus, CubeStatusEvent } from '../types/execution';
import type { WorkflowGraph, WorkflowNode, WorkflowEdge } from '../types/workflow';
import { getWorkflow, createWorkflow, updateWorkflow } from '../api/workflows';
import { getCatalog } from '../api/cubes';

// ─── Type definitions (collocated here, not in a separate file) ──────────────

export type CubeNodeData = {
  cube_id: string;
  cubeDef: CubeDefinition;
  params: Record<string, unknown>;
  isNew?: boolean;
};

export type CubeFlowNode = Node<CubeNodeData, 'cube'>;

// ─── Serialization helpers ────────────────────────────────────────────────────

/**
 * Serialize canvas nodes/edges to the WorkflowGraph format for API persistence.
 */
export function serializeGraph(nodes: CubeFlowNode[], edges: Edge[]): WorkflowGraph {
  const wfNodes: WorkflowNode[] = nodes.map((n) => ({
    id: n.id,
    type: 'cube',
    position: n.position,
    data: {
      cube_id: n.data.cube_id,
      params: n.data.params,
    },
  }));

  const wfEdges: WorkflowEdge[] = edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle ?? null,
    targetHandle: e.targetHandle ?? null,
  }));

  return { nodes: wfNodes, edges: wfEdges };
}

/**
 * Deserialize a WorkflowGraph from the API back into canvas nodes/edges.
 * Re-hydrates cubeDef by looking up cube_id in the catalog.
 */
export function deserializeGraph(
  graph: WorkflowGraph,
  catalog: CubeDefinition[]
): { nodes: CubeFlowNode[]; edges: Edge[] } {
  const nodes: CubeFlowNode[] = graph.nodes
    .map((wn) => {
      const cubeDef = catalog.find((c) => c.cube_id === wn.data.cube_id);
      if (!cubeDef) {
        console.warn(`deserializeGraph: cube "${wn.data.cube_id}" not found in catalog — skipping node`);
        return null;
      }
      return {
        id: wn.id,
        type: 'cube' as const,
        position: wn.position,
        data: {
          cube_id: wn.data.cube_id,
          cubeDef,
          params: wn.data.params,
        },
      } satisfies CubeFlowNode;
    })
    .filter((n): n is CubeFlowNode => n !== null);

  const edges: Edge[] = graph.edges.map((we) => ({
    id: we.id,
    source: we.source,
    target: we.target,
    sourceHandle: we.sourceHandle,
    targetHandle: we.targetHandle,
    type: 'straight',
  }));

  return { nodes, edges };
}

// ─── Store interface ─────────────────────────────────────────────────────────

interface FlowState {
  // Canvas state
  nodes: CubeFlowNode[];
  edges: Edge[];
  catalog: CubeDefinition[];
  results: Record<string, { rows: unknown[]; truncated: boolean }>;
  catalogLoading: boolean;
  isLoadingWorkflow: boolean;

  // Workflow metadata
  workflowId: string | null;
  workflowName: string;
  isDirty: boolean;

  // Undo/Redo history
  history: { nodes: CubeFlowNode[]; edges: Edge[] }[];
  historyIndex: number;
  savedHistoryIndex: number;
  _isUndoRedo: boolean;

  // Execution state
  isRunning: boolean;
  executionStatus: Record<string, { status: CubeStatus; error?: string; outputs?: Record<string, unknown>; execution_ms?: number }>;
  completedCount: number;
  totalCount: number;

  // Catalog actions
  setCatalog: (catalog: CubeDefinition[]) => void;
  setCatalogLoading: (loading: boolean) => void;

  // React Flow change handlers
  onNodesChange: (changes: NodeChange<CubeFlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;

  // Node actions
  addCubeNode: (cubeId: string, position: { x: number; y: number }) => void;
  removeNode: (nodeId: string) => void;
  updateNodeParam: (nodeId: string, paramName: string, value: unknown) => void;
  clearNodeNew: (nodeId: string) => void;

  // Edge actions
  addTypedEdge: (edge: Edge) => void;

  // Undo/Redo actions
  pushSnapshot: () => void;
  undo: () => void;
  redo: () => void;

  // Results actions
  setResults: (nodeId: string, rows: unknown[], truncated: boolean) => void;
  clearResults: () => void;

  // Workflow metadata actions
  setWorkflowName: (name: string) => void;
  setWorkflowMeta: (id: string | null, name: string) => void;

  // Workflow persistence actions
  saveWorkflow: () => Promise<string>;
  loadWorkflow: (id: string) => Promise<void>;
  resetWorkflow: () => void;

  // Results drawer selection state
  selectedResultNodeId: string | null;
  setSelectedResultNodeId: (nodeId: string | null) => void;

  // Execution actions
  startExecution: () => void;
  stopExecution: () => void;
  setNodeExecutionStatus: (nodeId: string, event: CubeStatusEvent) => void;

  // Connection drag state (for magnetic handles)
  connectionDrag: {
    sourceNodeId: string;
    sourceHandleId: string;
    sourceParamType: ParamType | null;
    mouseX: number;
    mouseY: number;
  } | null;
  startConnectionDrag: (nodeId: string, handleId: string) => void;
  updateConnectionDragPosition: (x: number, y: number) => void;
  endConnectionDrag: () => void;

  // Magnetic guide lines — compatible handles register their screen position
  magneticTargets: Record<string, { screenX: number; screenY: number; color: string }>;
  registerMagneticTarget: (handleId: string, screenX: number, screenY: number, color: string) => void;
  unregisterMagneticTarget: (handleId: string) => void;
  clearMagneticTargets: () => void;
}

// ─── Default param value helper ──────────────────────────────────────────────

function defaultParamValue(param: { type: ParamType; default: unknown }): unknown {
  if (param.default !== null && param.default !== undefined) {
    return param.default;
  }
  if (param.type === ParamType.BOOLEAN) return false;
  if (param.type === ParamType.LIST_OF_STRINGS) return [];
  if (param.type === ParamType.LIST_OF_NUMBERS) return [];
  return undefined;
}

// ─── Store ───────────────────────────────────────────────────────────────────

export const useFlowStore = create<FlowState>()((set, get) => ({
  // Initial canvas state
  nodes: [],
  edges: [],
  catalog: [],
  results: {},
  catalogLoading: false,
  isLoadingWorkflow: false,

  // Initial workflow metadata
  workflowId: null,
  workflowName: 'Untitled Workflow',
  isDirty: false,

  // Undo/Redo history
  history: [{ nodes: [], edges: [] }],
  historyIndex: 0,
  savedHistoryIndex: 0,
  _isUndoRedo: false,

  // Initial execution state
  isRunning: false,
  executionStatus: {},
  completedCount: 0,
  totalCount: 0,

  // Connection drag state
  connectionDrag: null,
  magneticTargets: {},

  // Results drawer selection state
  selectedResultNodeId: null,

  // Results drawer selection
  setSelectedResultNodeId: (nodeId) => set({ selectedResultNodeId: nodeId }),

  // Catalog
  setCatalog: (catalog) => set({ catalog }),
  setCatalogLoading: (loading) => set({ catalogLoading: loading }),

  // ── Undo/Redo ─────────────────────────────────────────────────────────────

  pushSnapshot: () => {
    const { nodes, edges, history, historyIndex } = get();
    const snapshot = { nodes: structuredClone(nodes), edges: structuredClone(edges) };
    const truncated = history.slice(0, historyIndex + 1);
    truncated.push(snapshot);
    // Cap at 50 entries
    if (truncated.length > 50) truncated.shift();
    set({
      history: truncated,
      historyIndex: truncated.length - 1,
    });
  },

  undo: () => {
    const { historyIndex, history, savedHistoryIndex } = get();
    if (historyIndex <= 0) return;
    const newIndex = historyIndex - 1;
    const snapshot = history[newIndex];
    set({
      _isUndoRedo: true,
      nodes: structuredClone(snapshot.nodes),
      edges: structuredClone(snapshot.edges),
      historyIndex: newIndex,
      isDirty: newIndex !== savedHistoryIndex,
    });
    // Reset flag after React Flow processes the changes
    queueMicrotask(() => set({ _isUndoRedo: false }));
  },

  redo: () => {
    const { historyIndex, history, savedHistoryIndex } = get();
    if (historyIndex >= history.length - 1) return;
    const newIndex = historyIndex + 1;
    const snapshot = history[newIndex];
    set({
      _isUndoRedo: true,
      nodes: structuredClone(snapshot.nodes),
      edges: structuredClone(snapshot.edges),
      historyIndex: newIndex,
      isDirty: newIndex !== savedHistoryIndex,
    });
    // Reset flag after React Flow processes the changes
    queueMicrotask(() => set({ _isUndoRedo: false }));
  },

  addTypedEdge: (edge) => {
    get().pushSnapshot();
    set((state) => ({ edges: [...state.edges, edge], isDirty: true }));
  },

  // React Flow change handlers — delegate to xyflow utilities, mark dirty
  // Only substantive changes (position, add, remove, replace) set isDirty.
  // Selection and dimension changes are internal React Flow bookkeeping.
  onNodesChange: (changes) => {
    if (!get()._isUndoRedo) {
      const hasStructural = changes.some(
        (c) => c.type === 'add' || c.type === 'remove' || c.type === 'replace'
      );
      if (hasStructural) get().pushSnapshot();
    }
    set((state) => {
      const substantive = changes.some(
        (c) => c.type !== 'select' && c.type !== 'dimensions'
      );
      return {
        nodes: applyNodeChanges(changes, state.nodes),
        ...(substantive && !get()._isUndoRedo ? { isDirty: true } : {}),
      };
    });
  },

  onEdgesChange: (changes) => {
    if (!get()._isUndoRedo) {
      get().pushSnapshot();
    }
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
      ...(get()._isUndoRedo ? {} : { isDirty: true }),
    }));
  },

  onConnect: (connection) => {
    get().pushSnapshot();
    set((state) => ({
      edges: addEdge(connection, state.edges),
      isDirty: true,
    }));
  },

  // Add a new cube node from the catalog
  addCubeNode: (cubeId, position) => {
    get().pushSnapshot();
    const { catalog } = get();
    const cubeDef = catalog.find((c) => c.cube_id === cubeId);
    if (!cubeDef) {
      console.warn(`addCubeNode: cube "${cubeId}" not found in catalog`);
      return;
    }

    // Initialize params from cubeDef.inputs defaults
    const params: Record<string, unknown> = {};
    for (const param of cubeDef.inputs) {
      params[param.name] = defaultParamValue(param);
    }

    const newNode: CubeFlowNode = {
      id: crypto.randomUUID(),
      type: 'cube',
      position,
      data: {
        cube_id: cubeId,
        cubeDef,
        params,
        isNew: true,
      },
    };

    set((state) => ({ nodes: [...state.nodes, newNode], isDirty: true }));
  },

  // Clear the isNew flag after entrance animation completes
  clearNodeNew: (nodeId) =>
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === nodeId
          ? { ...node, data: { ...node.data, isNew: false } }
          : node
      ),
    })),

  // Remove a node, its connected edges, and its results in one atomic update
  removeNode: (nodeId) => {
    get().pushSnapshot();
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== nodeId),
      edges: state.edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
      results: Object.fromEntries(
        Object.entries(state.results).filter(([id]) => id !== nodeId)
      ),
      isDirty: true,
    }));
  },

  // Update a single param value inside a node's data — immutable, marks dirty
  updateNodeParam: (nodeId, paramName, value) => {
    get().pushSnapshot();
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === nodeId
          ? {
              ...node,
              data: {
                ...node.data,
                params: {
                  ...node.data.params,
                  [paramName]: value,
                },
              },
            }
          : node
      ),
      isDirty: true,
    }));
  },

  // Results management
  setResults: (nodeId, rows, truncated) =>
    set((state) => ({
      results: {
        ...state.results,
        [nodeId]: { rows, truncated },
      },
    })),

  clearResults: () => set({ results: {} }),

  // Workflow metadata actions
  setWorkflowName: (name) => set({ workflowName: name, isDirty: true }),

  setWorkflowMeta: (id, name) => set({ workflowId: id, workflowName: name }),

  // Serialize and persist to API
  saveWorkflow: async () => {
    const { nodes, edges, workflowId, workflowName } = get();
    const graph = serializeGraph(nodes, edges);

    let response;
    if (workflowId === null) {
      response = await createWorkflow(workflowName, graph);
    } else {
      response = await updateWorkflow(workflowId, workflowName, graph);
    }

    set({ workflowId: response.id, isDirty: false, savedHistoryIndex: get().historyIndex });
    return response.id;
  },

  // Load a workflow from API and restore canvas state
  loadWorkflow: async (id) => {
    set({ isLoadingWorkflow: true, workflowName: '' });
    try {
      const state = get();
      let { catalog } = state;

      // Guard: ensure catalog is loaded before deserializing
      if (catalog.length === 0) {
        state.setCatalogLoading(true);
        try {
          catalog = await getCatalog();
          get().setCatalog(catalog);
        } finally {
          get().setCatalogLoading(false);
        }
      }

      const response = await getWorkflow(id);
      const { nodes, edges } = deserializeGraph(response.graph_json, catalog);

      set({
        nodes,
        edges,
        workflowId: response.id,
        workflowName: response.name,
        isDirty: false,
        results: {},
        executionStatus: {},
        history: [{ nodes: structuredClone(nodes), edges: structuredClone(edges) }],
        historyIndex: 0,
        savedHistoryIndex: 0,
      });
    } finally {
      set({ isLoadingWorkflow: false });
    }
  },

  // Reset to empty state for a new workflow
  resetWorkflow: () =>
    set({
      nodes: [],
      edges: [],
      workflowId: null,
      workflowName: 'Untitled Workflow',
      isDirty: false,
      results: {},
      executionStatus: {},
      isRunning: false,
      completedCount: 0,
      totalCount: 0,
      selectedResultNodeId: null,
      history: [{ nodes: [], edges: [] }],
      historyIndex: 0,
      savedHistoryIndex: 0,
    }),

  // Execution actions
  startExecution: () =>
    set({
      isRunning: true,
      executionStatus: {},
      completedCount: 0,
      totalCount: 0,
    }),

  stopExecution: () => set({ isRunning: false }),

  // Connection drag actions (for magnetic handles)
  startConnectionDrag: (nodeId, handleId) => {
    const { nodes } = get();
    const node = nodes.find((n) => n.id === nodeId);
    let sourceParamType: ParamType | null = null;
    if (node) {
      if (handleId === '__full_result__') {
        sourceParamType = ParamType.JSON_OBJECT;
      } else {
        const param = node.data.cubeDef.outputs.find((p) => p.name === handleId);
        sourceParamType = param?.type ?? null;
      }
    }
    set({
      connectionDrag: {
        sourceNodeId: nodeId,
        sourceHandleId: handleId,
        sourceParamType,
        mouseX: 0,
        mouseY: 0,
      },
    });
  },

  updateConnectionDragPosition: (x, y) =>
    set((state) => {
      if (!state.connectionDrag) return {};
      return {
        connectionDrag: { ...state.connectionDrag, mouseX: x, mouseY: y },
      };
    }),

  endConnectionDrag: () => set({ connectionDrag: null, magneticTargets: {} }),

  // Magnetic guide line targets
  registerMagneticTarget: (handleId, screenX, screenY, color) =>
    set((state) => ({
      magneticTargets: {
        ...state.magneticTargets,
        [handleId]: { screenX, screenY, color },
      },
    })),

  unregisterMagneticTarget: (handleId) =>
    set((state) => {
      const { [handleId]: _, ...rest } = state.magneticTargets;
      return { magneticTargets: rest };
    }),

  clearMagneticTargets: () => set({ magneticTargets: {} }),

  setNodeExecutionStatus: (nodeId, event) =>
    set((state) => {
      const newStatus = {
        status: event.status,
        error: event.error,
        outputs: event.outputs,
        execution_ms: event.execution_ms,
      };

      let { completedCount, totalCount } = state;

      if (event.status === 'pending') {
        totalCount += 1;
      } else if (event.status === 'done' || event.status === 'error' || event.status === 'skipped') {
        completedCount += 1;
      }

      // If the event has outputs, update results for this node
      let results = state.results;
      if (event.outputs && event.status === 'done') {
        // Extract the primary data array from cube outputs.
        // Prefer an explicit 'rows' key; otherwise find the first array of
        // objects (the main data table), then any array, then fall back to
        // Object.values().
        let rows: unknown[];
        if (Array.isArray(event.outputs.rows)) {
          rows = event.outputs.rows as unknown[];
        } else {
          const vals = Object.values(event.outputs);
          const objArr = vals.find(
            (v) => Array.isArray(v) && v.length > 0 && typeof v[0] === 'object' && v[0] !== null,
          );
          if (objArr) {
            rows = objArr as unknown[];
          } else {
            const anyArr = vals.find((v) => Array.isArray(v));
            rows = anyArr ? (anyArr as unknown[]) : (vals as unknown[]);
          }
        }
        const truncated = event.truncated ?? false;
        results = {
          ...state.results,
          [nodeId]: { rows, truncated },
        };
      }

      return {
        executionStatus: {
          ...state.executionStatus,
          [nodeId]: newStatus,
        },
        completedCount,
        totalCount,
        results,
      };
    }),
}));
