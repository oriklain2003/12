import { apiFetch } from './client';
import { API_BASE } from './config';
import type { AgentMode, AgentSSEEvent } from '../types/agent';
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

/**
 * Stream agent chat responses as Server-Sent Events.
 * Uses fetch + ReadableStream (not EventSource — POST not supported by EventSource).
 * Per D-13: full workflow graph serialized into every request.
 */
export async function* streamAgentChat(
  message: string,
  sessionId: string | null,
  workflowId: string | null,
  workflowGraph: WorkflowGraph | null,
  mode: AgentMode,
  executionErrors?: Record<string, unknown> | null,
  executionResults?: Record<string, unknown> | null,
): AsyncGenerator<AgentSSEEvent> {
  const response = await fetch(`${API_BASE}/agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      persona: 'canvas_agent',
      workflow_id: workflowId,
      workflow_graph: workflowGraph,
      execution_errors: executionErrors ?? null,
      execution_results: executionResults ?? null,
      mode,
    }),
  });

  if (!response.ok) {
    throw new Error(`Agent chat failed: ${response.status} ${response.statusText}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) {
        if (line.startsWith('data:')) {
          const payload = line.slice(5).trim();
          if (!payload) continue;
          try {
            yield JSON.parse(payload) as AgentSSEEvent;
          } catch {
            // Skip malformed SSE data
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
