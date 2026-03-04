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

  // Workflow metadata
  workflowId: string | null;
  workflowName: string;
  isDirty: boolean;

  // Execution state
  isRunning: boolean;
  executionStatus: Record<string, { status: CubeStatus; error?: string; outputs?: Record<string, unknown> }>;
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

  // Execution actions
  startExecution: () => void;
  stopExecution: () => void;
  setNodeExecutionStatus: (nodeId: string, event: CubeStatusEvent) => void;
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

  // Initial workflow metadata
  workflowId: null,
  workflowName: 'Untitled Workflow',
  isDirty: false,

  // Initial execution state
  isRunning: false,
  executionStatus: {},
  completedCount: 0,
  totalCount: 0,

  // Catalog
  setCatalog: (catalog) => set({ catalog }),
  setCatalogLoading: (loading) => set({ catalogLoading: loading }),

  // React Flow change handlers — delegate to xyflow utilities, mark dirty
  onNodesChange: (changes) =>
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes),
      isDirty: true,
    })),

  onEdgesChange: (changes) =>
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
      isDirty: true,
    })),

  onConnect: (connection) =>
    set((state) => ({
      edges: addEdge(connection, state.edges),
    })),

  // Add a new cube node from the catalog
  addCubeNode: (cubeId, position) => {
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
      },
    };

    set((state) => ({ nodes: [...state.nodes, newNode], isDirty: true }));
  },

  // Remove a node, its connected edges, and its results in one atomic update
  removeNode: (nodeId) =>
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== nodeId),
      edges: state.edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
      results: Object.fromEntries(
        Object.entries(state.results).filter(([id]) => id !== nodeId)
      ),
      isDirty: true,
    })),

  // Update a single param value inside a node's data — immutable, marks dirty
  updateNodeParam: (nodeId, paramName, value) =>
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
    })),

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

    set({ workflowId: response.id, isDirty: false });
    return response.id;
  },

  // Load a workflow from API and restore canvas state
  loadWorkflow: async (id) => {
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
    });
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

  setNodeExecutionStatus: (nodeId, event) =>
    set((state) => {
      const newStatus = {
        status: event.status,
        error: event.error,
        outputs: event.outputs,
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
        const rows = Array.isArray(event.outputs.rows)
          ? (event.outputs.rows as unknown[])
          : Object.values(event.outputs);
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
