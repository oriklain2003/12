/**
 * Hook for streaming workflow execution progress via SSE.
 *
 * POSTs the graph to /api/workflows/run/stream and parses the SSE
 * response manually (EventSource only supports GET).
 */

import { useCallback, useRef } from 'react';
import type { CubeStatusEvent } from '../types/execution';
import type { WorkflowGraph } from '../types/workflow';
import { useFlowStore } from '../store/flowStore';
import { API_BASE } from '../api/config';

export function useWorkflowSSE() {
  const abortRef = useRef<AbortController | null>(null);

  const startStream = useCallback((graph: WorkflowGraph) => {
    // Abort any existing stream
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }

    // Signal execution start — resets counters and sets isRunning = true
    useFlowStore.getState().startExecution();

    const controller = new AbortController();
    abortRef.current = controller;

    (async () => {
      try {
        const res = await fetch(`${API_BASE}/workflows/run/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(graph),
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          console.error('useWorkflowSSE: request failed', res.status);
          useFlowStore.getState().stopExecution();
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE frames from buffer
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? ''; // keep incomplete last line in buffer

          for (const line of lines) {
            if (!line.startsWith('data:')) continue;
            const raw = line.slice(5).trim();
            if (!raw) continue;

            let data: CubeStatusEvent;
            try {
              data = JSON.parse(raw) as CubeStatusEvent;
            } catch {
              continue;
            }

            useFlowStore.getState().setNodeExecutionStatus(data.node_id, data);

            const { completedCount, totalCount } = useFlowStore.getState();
            if (totalCount > 0 && completedCount >= totalCount) {
              reader.cancel();
              useFlowStore.getState().stopExecution();
              return;
            }
          }
        }

        // Stream ended naturally
        useFlowStore.getState().stopExecution();
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          console.error('useWorkflowSSE: stream error', err);
        }
        useFlowStore.getState().stopExecution();
      } finally {
        abortRef.current = null;
      }
    })();
  }, []);

  const stopStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    useFlowStore.getState().stopExecution();
  }, []);

  return { startStream, stopStream };
}
