/**
 * Editor page — wraps the full canvas layout and handles route-based
 * workflow loading/reset on mount.
 *
 * Routes: /workflow/new (empty canvas) and /workflow/:id (loads existing)
 */

import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { ReactFlowProvider } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Toaster } from 'sonner';
import { FlowCanvas } from '../components/Canvas/FlowCanvas';
import { CubeCatalog } from '../components/Sidebar/CubeCatalog';
import { Toolbar } from '../components/Toolbar/Toolbar';
import { ResultsDrawer } from '../components/Results/ResultsDrawer';
import { useFlowStore } from '../store/flowStore';
import '../App.css';

export function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const loadWorkflow = useFlowStore((s) => s.loadWorkflow);
  const resetWorkflow = useFlowStore((s) => s.resetWorkflow);
  const stopExecution = useFlowStore((s) => s.stopExecution);

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
    </div>
  );
}
