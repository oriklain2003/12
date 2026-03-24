/**
 * Editor page — wraps the full canvas layout and handles route-based
 * workflow loading/reset on mount.
 *
 * Routes: /workflow/new (empty canvas) and /workflow/:id (loads existing)
 */

import { useEffect, useRef } from 'react';
import { useParams, useBlocker } from 'react-router-dom';
import { ReactFlowProvider } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Toaster } from 'sonner';
import { FlowCanvas } from '../components/Canvas/FlowCanvas';
import { CubeCatalog } from '../components/Sidebar/CubeCatalog';
import { Toolbar } from '../components/Toolbar/Toolbar';
import { ResultsDrawer } from '../components/Results/ResultsDrawer';
import { IssuesPanel } from '../components/Validation/IssuesPanel';
import { WelcomeTour } from '../components/WelcomeTour/WelcomeTour';
import { ChatPanel } from '../components/Chat/ChatPanel';
import { useFlowStore } from '../store/flowStore';
import { useThemeStore } from '../store/themeStore';
import '../App.css';

export function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const loadWorkflow = useFlowStore((s) => s.loadWorkflow);
  const resetWorkflow = useFlowStore((s) => s.resetWorkflow);
  const stopExecution = useFlowStore((s) => s.stopExecution);
  const workflowName = useFlowStore((s) => s.workflowName);
  const isDirty = useFlowStore((s) => s.isDirty);

  // Chat panel auto-open Fix mode state
  const isRunning = useFlowStore((s) => s.isRunning);
  const executionStatus = useFlowStore((s) => s.executionStatus);
  const setChatPanelOpen = useFlowStore((s) => s.setChatPanelOpen);
  const setChatPanelMode = useFlowStore((s) => s.setChatPanelMode);
  const addChatMessage = useFlowStore((s) => s.addChatMessage);

  // Guard: fire auto-open Fix mode only once per execution, reset on new run
  const autoFixFired = useRef(false);

  // Apply persisted theme on mount
  useEffect(() => {
    useThemeStore.getState().applyTheme();
  }, []);

  // Load/reset workflow on mount
  useEffect(() => {
    if (id) {
      loadWorkflow(id).catch((err) => {
        console.error('Failed to load workflow:', err);
      });
    } else {
      resetWorkflow();
    }

    return () => {
      stopExecution();
    };
  }, [id, loadWorkflow, resetWorkflow, stopExecution]);

  // Dynamic browser tab title
  useEffect(() => {
    document.title = workflowName?.trim()
      ? `${workflowName} — ONYX 12`
      : 'ONYX 12';
    return () => { document.title = 'ONYX 12'; };
  }, [workflowName]);

  // Auto-open Fix mode when execution finishes with errors (D-04, D-06)
  // useRef guard prevents repeated firing for the same failed run
  useEffect(() => {
    if (isRunning) {
      // Reset the guard when a new run starts
      autoFixFired.current = false;
      return;
    }
    // Only fire once per execution completion
    if (autoFixFired.current) return;

    const errorNodes = Object.entries(executionStatus).filter(
      ([, s]) => s.status === 'error'
    );
    if (errorNodes.length > 0) {
      autoFixFired.current = true;
      setChatPanelOpen(true);
      setChatPanelMode('fix');
      addChatMessage({
        id: crypto.randomUUID(),
        role: 'agent',
        content: `I see errors in ${errorNodes.length} cube(s) from the last run. Want me to diagnose the issues and suggest a fix?`,
        timestamp: Date.now(),
        type: 'auto_fix_prompt',
      });
    }
  }, [isRunning, executionStatus, setChatPanelOpen, setChatPanelMode, addChatMessage]);

  // Browser close/refresh guard
  useEffect(() => {
    if (!isDirty) return;
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  // In-app navigation guard
  const blocker = useBlocker(isDirty);

  return (
    <div className="app">
      <Toolbar />
      <div className="app__body">
        <CubeCatalog />
        <div className="app__canvas-area">
          <ReactFlowProvider>
            <FlowCanvas />
            <IssuesPanel />
          </ReactFlowProvider>
          <ResultsDrawer />
        </div>
        <ChatPanel />
      </div>
      <Toaster position="bottom-right" theme="dark" />
      <WelcomeTour />

      {blocker.state === 'blocked' && (
        <div className="unsaved-overlay">
          <div className="unsaved-dialog glass">
            <h3>Unsaved Changes</h3>
            <p>You have unsaved changes that will be lost.</p>
            <div className="unsaved-dialog__actions">
              <button className="glass-btn" onClick={() => blocker.reset?.()}>Cancel</button>
              <button className="glass-btn glass-btn--accent" onClick={() => blocker.proceed?.()}>Discard</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
