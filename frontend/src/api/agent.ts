import { apiFetch } from './client';
import type { WorkflowGraph } from '../types/workflow';

export interface ValidationIssue {
  severity: 'error' | 'warning';
  node_id: string | null;
  cube_name: string | null;
  param_name: string | null;
  message: string;
  rule: string;
}

export interface ValidationResponse {
  issues: ValidationIssue[];
}

export const validateWorkflow = (graph: WorkflowGraph): Promise<ValidationResponse> =>
  apiFetch<ValidationResponse>('/agent/validate', {
    method: 'POST',
    body: JSON.stringify({ graph }),
  });
