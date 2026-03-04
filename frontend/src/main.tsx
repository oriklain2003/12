import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import './styles/theme.css';
import './styles/glass.css';
import './index.css';
import { EditorPage } from './pages/EditorPage';

// Minimal dashboard placeholder — replaced in Plan 02
function DashboardPlaceholder() {
  return (
    <div style={{ padding: '40px', color: '#fff' }}>
      Dashboard — coming in Plan 02
    </div>
  );
}

const router = createBrowserRouter([
  { path: '/', element: <DashboardPlaceholder /> },
  { path: '/workflow/new', element: <EditorPage /> },
  { path: '/workflow/:id', element: <EditorPage /> },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
