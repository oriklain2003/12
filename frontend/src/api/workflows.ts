import { apiFetch } from './client';
import type { WorkflowResponse, WorkflowGraph } from '../types/workflow';

export const getWorkflows = () => apiFetch<WorkflowResponse[]>('/workflows');

export const getWorkflow = (id: string) => apiFetch<WorkflowResponse>(`/workflows/${id}`);

export const createWorkflow = (name: string, graph: WorkflowGraph) =>
  apiFetch<WorkflowResponse>('/workflows', {
    method: 'POST',
    body: JSON.stringify({ name, graph_json: graph }),
  });

export const updateWorkflow = (id: string, name: string, graph: WorkflowGraph) =>
  apiFetch<WorkflowResponse>(`/workflows/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ name, graph_json: graph }),
  });

export const deleteWorkflow = (id: string) =>
  apiFetch<void>(`/workflows/${id}`, { method: 'DELETE' });
