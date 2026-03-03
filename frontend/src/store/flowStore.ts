/**
 * Central Zustand store for the visual workflow canvas.
 * Single source of truth for nodes, edges, catalog, and results.
 */

import { create } from 'zustand';
import type { Node, Edge, NodeChange, EdgeChange, Connection } from '@xyflow/react';
import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react';
import type { CubeDefinition } from '../types/cube';
import { ParamType } from '../types/cube';

// ─── Type definitions (collocated here, not in a separate file) ──────────────

export type CubeNodeData = {
  cube_id: string;
  cubeDef: CubeDefinition;
  params: Record<string, unknown>;
};

export type CubeFlowNode = Node<CubeNodeData, 'cube'>;

// ─── Store interface ─────────────────────────────────────────────────────────

interface FlowState {
  // State
  nodes: CubeFlowNode[];
  edges: Edge[];
  catalog: CubeDefinition[];
  results: Record<string, { rows: unknown[]; truncated: boolean }>;
  catalogLoading: boolean;

  // Actions
  setCatalog: (catalog: CubeDefinition[]) => void;
  setCatalogLoading: (loading: boolean) => void;
  onNodesChange: (changes: NodeChange<CubeFlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  addCubeNode: (cubeId: string, position: { x: number; y: number }) => void;
  updateNodeParam: (nodeId: string, paramName: string, value: unknown) => void;
  setResults: (nodeId: string, rows: unknown[], truncated: boolean) => void;
  clearResults: () => void;
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
  // Initial state
  nodes: [],
  edges: [],
  catalog: [],
  results: {},
  catalogLoading: false,

  // Catalog
  setCatalog: (catalog) => set({ catalog }),
  setCatalogLoading: (loading) => set({ catalogLoading: loading }),

  // React Flow change handlers — delegate to xyflow utilities
  onNodesChange: (changes) =>
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes),
    })),

  onEdgesChange: (changes) =>
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
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

    set((state) => ({ nodes: [...state.nodes, newNode] }));
  },

  // Update a single param value inside a node's data — immutable
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
}));
