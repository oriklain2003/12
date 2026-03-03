/**
 * TypeScript type definitions for workflow schemas.
 * Mirrors backend/app/schemas/workflow.py
 */

export interface Position {
  x: number;
  y: number;
}

export interface WorkflowNodeData {
  cube_id: string;
  params: Record<string, unknown>;
}

export interface WorkflowNode {
  id: string;
  type: string;
  position: Position;
  data: WorkflowNodeData;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle: string | null;
  targetHandle: string | null;
}

export interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface WorkflowResponse {
  id: string;
  name: string;
  graph_json: WorkflowGraph;
  created_at: string;
  updated_at: string;
}
