/**
 * Editor page — wraps the full canvas layout and handles route-based
 * workflow loading/reset on mount.
 *
 * Routes: /workflow/new (empty canvas) and /workflow/:id (loads existing)
 */

import { useEffect, useRef } from 'react';
// NOTE: Zustand actions are accessed via useFlowStore.getState() inside effects
// to avoid unstable references causing infinite re-render loops.
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
  const workflowName = useFlowStore((s) => s.workflowName);
  const isDirty = useFlowStore((s) => s.isDirty);

  // Chat panel auto-open Fix mode state
  const isRunning = useFlowStore((s) => s.isRunning);
  const executionStatus = useFlowStore((s) => s.executionStatus);

  // Guard: fire auto-open Fix mode only once per execution, reset on new run
  const autoFixFired = useRef(false);

  // Apply persisted theme on mount
  useEffect(() => {
    useThemeStore.getState().applyTheme();
  }, []);

  // Load/reset workflow on mount
  useEffect(() => {
    const store = useFlowStore.getState();
    if (id) {
      store.loadWorkflow(id).catch((err) => {
        console.error('Failed to load workflow:', err);
      });
    } else {
      store.resetWorkflow();
    }

    return () => {
      useFlowStore.getState().stopExecution();
    };
  }, [id]);

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
      const store = useFlowStore.getState();
      store.setChatPanelOpen(true);
      store.setChatPanelMode('fix');
      store.addChatMessage({
        id: crypto.randomUUID(),
        role: 'agent',
        content: `I see errors in ${errorNodes.length} cube(s) from the last run. Want me to diagnose the issues and suggest a fix?`,
        timestamp: Date.now(),
        type: 'auto_fix_prompt',
      });
    }
  }, [isRunning, executionStatus]);

  // Listen for "Discuss Results" follow-up handoff from ResultsDrawer
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      const store = useFlowStore.getState();
      // Start a fresh follow-up session
      store.setChatSessionId(null);
      store.clearChat();
      store.setChatPersona(detail.persona ?? 'results_followup');
      store.setChatPanelMode('general');
      store.setChatPanelOpen(true);
      // Seed with the interpretation as context
      if (detail.interpretationSummary) {
        store.addChatMessage({
          id: crypto.randomUUID(),
          role: 'agent',
          content: detail.interpretationSummary,
          timestamp: Date.now(),
          type: 'interpretation_context',
        });
      }
    };
    window.addEventListener('open-results-followup', handler);
    return () => window.removeEventListener('open-results-followup', handler);
  }, []);

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
