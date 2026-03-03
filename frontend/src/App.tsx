/**
 * Root application shell.
 * Layout: Toolbar (top) + Sidebar (left) + Canvas (right/main)
 *
 * ReactFlowProvider wraps FlowCanvas so that useReactFlow() works inside it.
 * Toaster from sonner provides error/info toasts (e.g. Full Result rejection).
 */

import { ReactFlowProvider } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Toaster } from 'sonner';
import { FlowCanvas } from './components/Canvas/FlowCanvas';
import { CubeCatalog } from './components/Sidebar/CubeCatalog';
import { Toolbar } from './components/Toolbar/Toolbar';
import './App.css';

function App() {
  return (
    <div className="app">
      <Toolbar />
      <div className="app__body">
        <CubeCatalog />
        <ReactFlowProvider>
          <FlowCanvas />
        </ReactFlowProvider>
      </div>
      <Toaster position="bottom-right" theme="dark" />
    </div>
  );
}

export default App;
