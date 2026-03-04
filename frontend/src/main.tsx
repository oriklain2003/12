import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import './styles/theme.css';
import './styles/glass.css';
import './index.css';
import { EditorPage } from './pages/EditorPage';
import { DashboardPage } from './pages/DashboardPage';

const router = createBrowserRouter([
  { path: '/', element: <DashboardPage /> },
  { path: '/workflow/new', element: <EditorPage /> },
  { path: '/workflow/:id', element: <EditorPage /> },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
