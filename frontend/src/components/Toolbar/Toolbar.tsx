/**
 * Top toolbar for the workflow editor.
 *
 * Contains:
 *  - Dashboard link (React Router Link — no full-page reload)
 *  - Editable workflow name input synced with Zustand store
 *  - Unsaved changes dot indicator
 *  - Save button (POST for new, PUT for existing)
 *  - Run button (triggers SSE execution stream)
 *  - Progress bar (visible during execution)
 *  - Keyboard shortcuts: Ctrl+S (save), Ctrl+Enter (run)
 */

import { useCallback, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useFlowStore, serializeGraph } from '../../store/flowStore';
import { useWorkflowSSE } from '../../hooks/useWorkflowSSE';
import './Toolbar.css';

export function Toolbar() {
  const navigate = useNavigate();

  // Store selectors
  const workflowName = useFlowStore((s) => s.workflowName);
  const setWorkflowName = useFlowStore((s) => s.setWorkflowName);
  const saveWorkflow = useFlowStore((s) => s.saveWorkflow);
  const workflowId = useFlowStore((s) => s.workflowId);
  const isDirty = useFlowStore((s) => s.isDirty);
  const isRunning = useFlowStore((s) => s.isRunning);
  const completedCount = useFlowStore((s) => s.completedCount);
  const totalCount = useFlowStore((s) => s.totalCount);

  const { startStream } = useWorkflowSSE();

  // ── Save handler ────────────────────────────────────────────────────────────

  const handleSave = useCallback(async () => {
    if (workflowName.trim() === '') {
      toast.error('Please enter a workflow name');
      return;
    }

    const wasNew = workflowId === null;

    try {
      const id = await saveWorkflow();
      toast.success('Workflow saved');

      // If this was a new workflow, update the URL to /workflow/:id
      if (wasNew) {
        navigate(`/workflow/${id}`, { replace: true });
      }
    } catch {
      toast.error('Failed to save workflow');
    }
  }, [workflowName, workflowId, saveWorkflow, navigate]);

  // ── Run handler ─────────────────────────────────────────────────────────────

  const handleRun = useCallback(async () => {
    if (isRunning) return;

    let id = workflowId;

    // Save first if no workflow ID yet
    if (id === null) {
      await handleSave();
      // Re-read workflowId from store after save
      id = useFlowStore.getState().workflowId;
      if (id === null) {
        // Save failed — bail out
        return;
      }
    }

    const { nodes, edges } = useFlowStore.getState();
    const graph = serializeGraph(nodes, edges);
    startStream(graph);
  }, [isRunning, workflowId, handleSave, startStream]);

  // ── Keyboard shortcuts ──────────────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isCtrl = e.ctrlKey || e.metaKey;
      const target = e.target as HTMLElement;
      const isInputField = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA';

      // Ctrl+S / Ctrl+Enter work even inside inputs
      if (isCtrl && e.key === 's') {
        e.preventDefault();
        handleSave();
        return;
      }

      if (isCtrl && e.key === 'Enter') {
        e.preventDefault();
        handleRun();
        return;
      }

      // Delete/Backspace: skip if focused on an input or textarea
      // (React Flow handles these natively on the canvas)
      if (isInputField) return;
    };

    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [handleSave, handleRun]);

  // ── Progress percentage ─────────────────────────────────────────────────────

  const progressPct = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <header className="toolbar glass">
      <div className="toolbar__left">
        <Link to="/" className="toolbar__brand" title="Dashboard">
          <img src="/onyx-logo.svg" alt="ONYX" className="toolbar__brand-logo" />
          <span className="toolbar__brand-divider" />
          <span className="toolbar__brand-product">12</span>
        </Link>
      </div>

      <div className="toolbar__center">
        <input
          type="text"
          className="toolbar__name-input nodrag"
          value={workflowName}
          onChange={(e) => setWorkflowName(e.target.value)}
          aria-label="Workflow name"
          spellCheck={false}
        />
        {isDirty && (
          <span className="toolbar__dirty-dot" aria-label="Unsaved changes" title="Unsaved changes" />
        )}
      </div>

      <div className="toolbar__actions">
        {isRunning && (
          <div className="toolbar__progress">
            <div className="toolbar__progress-bar">
              <div
                className="toolbar__progress-fill"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="toolbar__progress-label">{completedCount}/{totalCount} cubes</span>
          </div>
        )}

        <button
          className="toolbar__btn toolbar__btn--save"
          onClick={handleSave}
          disabled={isRunning}
        >
          Save
        </button>
        <button
          className={`toolbar__btn toolbar__btn--run${isRunning ? ' toolbar__btn--running' : ''}`}
          onClick={handleRun}
          disabled={isRunning}
        >
          {isRunning ? 'Running...' : 'Run'}
        </button>
      </div>
    </header>
  );
}
