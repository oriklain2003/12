/**
 * Editor page — wraps the full canvas layout and handles route-based
 * workflow loading/reset on mount.
 *
 * Routes: /workflow/new (empty canvas) and /workflow/:id (loads existing)
 */

import { useEffect } from 'react';
import { useParams, useBlocker } from 'react-router-dom';
import { ReactFlowProvider } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Toaster } from 'sonner';
import { FlowCanvas } from '../components/Canvas/FlowCanvas';
import { CubeCatalog } from '../components/Sidebar/CubeCatalog';
import { Toolbar } from '../components/Toolbar/Toolbar';
import { ResultsDrawer } from '../components/Results/ResultsDrawer';
import { WelcomeTour } from '../components/WelcomeTour/WelcomeTour';
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
          </ReactFlowProvider>
          <ResultsDrawer />
        </div>
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
