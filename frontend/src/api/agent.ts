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

/** Build workflow directly from the last approved preview — no LLM round-trip. */
export const buildFromPreview = (sessionId: string): Promise<{
  status: 'created' | 'validation_failed' | 'error';
  workflow_id?: string;
  workflow_name?: string;
  message?: string;
  errors?: Array<{ severity: string; message: string; rule: string }>;
}> =>
  apiFetch('/agent/build-from-preview', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
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
  persona: string = 'canvas_agent',
): AsyncGenerator<AgentSSEEvent> {
  const response = await fetch(`${API_BASE}/agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      persona,
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

/**
 * Stream one-shot interpretation of cube results via SSE.
 * Per D-05: SSE-based, not sync. Per D-03: interprets selected cube only.
 */
export async function* streamInterpret(
  workflowId: string | null,
  workflowGraph: Record<string, unknown> | null,
  executionResults: Record<string, unknown> | null,
  selectedCubeId: string,
  cubeName: string,
  cubeCategory: string,
): AsyncGenerator<AgentSSEEvent> {
  const response = await fetch(`${API_BASE}/agent/interpret`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workflow_id: workflowId,
      workflow_graph: workflowGraph,
      execution_results: executionResults,
      selected_cube_id: selectedCubeId,
      cube_name: cubeName,
      cube_category: cubeCategory,
    }),
  });

  if (!response.ok) {
    throw new Error(`Interpret failed: ${response.status} ${response.statusText}`);
  }

  // SSE reading loop — identical to streamAgentChat
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
