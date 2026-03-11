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

import { useCallback, useEffect, useState, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useFlowStore, serializeGraph } from '../../store/flowStore';
import { useWorkflowSSE } from '../../hooks/useWorkflowSSE';
import { useTourStore } from '../WelcomeTour/useTourStore';
import { ThemeSettings } from '../Settings/ThemeSettings';
import './Toolbar.css';

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

export function Toolbar() {
  const navigate = useNavigate();

  // Store selectors
  const workflowName = useFlowStore((s) => s.workflowName);
  const setWorkflowName = useFlowStore((s) => s.setWorkflowName);
  const saveWorkflow = useFlowStore((s) => s.saveWorkflow);
  const workflowId = useFlowStore((s) => s.workflowId);
  const isDirty = useFlowStore((s) => s.isDirty);
  const isRunning = useFlowStore((s) => s.isRunning);
  const isLoadingWorkflow = useFlowStore((s) => s.isLoadingWorkflow);
  const completedCount = useFlowStore((s) => s.completedCount);
  const totalCount = useFlowStore((s) => s.totalCount);

  const [showShortcuts, setShowShortcuts] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const shortcutsRef = useRef<HTMLDivElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);

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

      // Toggle shortcuts panel
      if (e.key === '?') {
        e.preventDefault();
        setShowShortcuts((v) => !v);
        return;
      }
      if (e.key === 'Escape') {
        setShowShortcuts(false);
        return;
      }

      // Undo/Redo (only when not in an input field so native text undo still works)
      if (isCtrl && (e.key === 'z' || e.key === 'Z')) {
        e.preventDefault();
        if (e.shiftKey) {
          useFlowStore.getState().redo();
        } else {
          useFlowStore.getState().undo();
        }
        return;
      }
      if (isCtrl && e.key === 'y') {
        e.preventDefault();
        useFlowStore.getState().redo();
        return;
      }
    };

    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [handleSave, handleRun]);

  // ── Close shortcuts on outside click ────────────────────────────────────────

  useEffect(() => {
    if (!showShortcuts) return;
    const handler = (e: MouseEvent) => {
      if (shortcutsRef.current && !shortcutsRef.current.contains(e.target as Node)) {
        setShowShortcuts(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showShortcuts]);

  // ── Close settings on outside click ─────────────────────────────────────────

  useEffect(() => {
    if (!showSettings) return;
    const handler = (e: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setShowSettings(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showSettings]);

  // ── Progress percentage ─────────────────────────────────────────────────────

  const progressPct = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <header className="toolbar glass" data-tour="toolbar">
      <div className="toolbar__left">
        <Link to="/" className="toolbar__brand" title="Dashboard">
          <img src="/onyx-logo.svg" alt="ONYX" className="toolbar__brand-logo" />
          <span className="toolbar__brand-divider" />
          <span className="toolbar__brand-product">12</span>
        </Link>
      </div>

      <div className="toolbar__center">
        {isLoadingWorkflow ? (
          <div className="toolbar__name-skeleton" aria-label="Loading workflow">
            <div className="toolbar__name-shimmer" />
          </div>
        ) : (
          <>
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
          </>
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

        <div className="toolbar__help-wrapper" ref={settingsRef}>
          <button
            className="toolbar__help-btn"
            onClick={() => setShowSettings((v) => !v)}
            title="Appearance settings"
            aria-label="Appearance settings"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
          {showSettings && <ThemeSettings />}
        </div>

        <div className="toolbar__help-wrapper" ref={shortcutsRef}>
          <button
            className="toolbar__help-btn"
            onClick={() => setShowShortcuts((v) => !v)}
            title="Keyboard shortcuts (?)"
            aria-label="Keyboard shortcuts"
            data-tour="help-btn"
          >
            ?
          </button>
          {showShortcuts && (
            <div className="toolbar__shortcuts">
              <div className="toolbar__shortcuts-title">Keyboard Shortcuts</div>
              <div className="toolbar__shortcuts-list">
                <div className="toolbar__shortcut-row">
                  <span className="toolbar__shortcut-keys">
                    <kbd>{isMac ? '⌘' : 'Ctrl'}</kbd><kbd>S</kbd>
                  </span>
                  <span>Save</span>
                </div>
                <div className="toolbar__shortcut-row">
                  <span className="toolbar__shortcut-keys">
                    <kbd>{isMac ? '⌘' : 'Ctrl'}</kbd><kbd>⏎</kbd>
                  </span>
                  <span>Run</span>
                </div>
                <div className="toolbar__shortcut-row">
                  <span className="toolbar__shortcut-keys">
                    <kbd>{isMac ? '⌘' : 'Ctrl'}</kbd><kbd>Z</kbd>
                  </span>
                  <span>Undo</span>
                </div>
                <div className="toolbar__shortcut-row">
                  <span className="toolbar__shortcut-keys">
                    <kbd>{isMac ? '⌘' : 'Ctrl'}</kbd><kbd>{isMac ? '⇧' : 'Shift'}</kbd><kbd>Z</kbd>
                  </span>
                  <span>Redo</span>
                </div>
                <div className="toolbar__shortcut-row">
                  <span className="toolbar__shortcut-keys">
                    <kbd>{isMac ? '⌘' : 'Ctrl'}</kbd><kbd>K</kbd>
                  </span>
                  <span>Command palette</span>
                </div>
                <div className="toolbar__shortcut-row">
                  <span className="toolbar__shortcut-keys">
                    <kbd>Del</kbd>
                  </span>
                  <span>Delete selected</span>
                </div>
                <div className="toolbar__shortcut-row">
                  <span className="toolbar__shortcut-keys">
                    <kbd>?</kbd>
                  </span>
                  <span>Toggle this panel</span>
                </div>
              </div>
              <button
                className="toolbar__tour-btn glass-btn"
                onClick={() => {
                  setShowShortcuts(false);
                  useTourStore.getState().startTour();
                }}
              >
                Take Tour
              </button>
            </div>
          )}
        </div>

        <button
          className="toolbar__btn toolbar__btn--save"
          onClick={handleSave}
          disabled={isRunning || isLoadingWorkflow}
          title={`Save (${isMac ? '⌘' : 'Ctrl+'}S)`}
          data-tour="save-btn"
        >
          Save
        </button>
        <button
          className={`toolbar__btn toolbar__btn--run${isRunning ? ' toolbar__btn--running' : ''}`}
          onClick={handleRun}
          disabled={isRunning || isLoadingWorkflow}
          title={`Run (${isMac ? '⌘' : 'Ctrl+'}⏎)`}
          data-tour="run-btn"
        >
          {isRunning ? 'Running...' : 'Run'}
        </button>
      </div>
    </header>
  );
}
