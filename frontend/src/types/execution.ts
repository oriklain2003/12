/**
 * Execution type definitions for SSE progress tracking.
 * Mirrors backend/app/schemas/execution.py CubeStatusEvent.
 */

export type CubeStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped';

export interface CubeStatusEvent {
  node_id: string;
  status: CubeStatus;
  outputs?: Record<string, unknown>;
  truncated?: boolean;
  execution_ms?: number;
  error?: string;
  reason?: string;
}
