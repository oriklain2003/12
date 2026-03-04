/**
 * Hook for streaming workflow execution progress via SSE.
 *
 * Connects to GET /api/workflows/{id}/run/stream and dispatches
 * cube_status events to the Zustand store for per-node status updates.
 *
 * IMPORTANT: EventSource auto-reconnects on server close.
 * We must explicitly close the connection when all nodes reach terminal state.
 */

import { useCallback, useRef } from 'react';
import type { CubeStatusEvent } from '../types/execution';
import { useFlowStore } from '../store/flowStore';

export function useWorkflowSSE() {
  const esRef = useRef<EventSource | null>(null);

  const startStream = useCallback((workflowId: string) => {
    // Close any existing connection first
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    // Signal execution start — resets counters and sets isRunning = true
    useFlowStore.getState().startExecution();

    const es = new EventSource(`/api/workflows/${workflowId}/run/stream`);
    esRef.current = es;

    // Listen specifically for 'cube_status' typed events (NOT default 'message')
    es.addEventListener('cube_status', (event: MessageEvent) => {
      let data: CubeStatusEvent;
      try {
        data = JSON.parse(event.data) as CubeStatusEvent;
      } catch (err) {
        console.error('useWorkflowSSE: failed to parse cube_status event', err);
        return;
      }

      // Dispatch status update to store
      useFlowStore.getState().setNodeExecutionStatus(data.node_id, data);

      // Check if all nodes have reached terminal state — if so, close the stream.
      // EventSource would auto-reconnect on server close, so we must close explicitly.
      const { completedCount, totalCount } = useFlowStore.getState();
      if (totalCount > 0 && completedCount >= totalCount) {
        es.close();
        esRef.current = null;
        useFlowStore.getState().stopExecution();
      }
    });

    es.onerror = () => {
      console.error('useWorkflowSSE: SSE connection error');
      es.close();
      esRef.current = null;
      useFlowStore.getState().stopExecution();
    };
  }, []);

  const stopStream = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    useFlowStore.getState().stopExecution();
  }, []);

  return { startStream, stopStream };
}
