# Phase 5: Workflow Management & Execution Integration - Research

**Researched:** 2026-03-04
**Domain:** React Router v7, SSE/EventSource, Zustand state expansion, React Flow canvas locking
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Dashboard layout**
- Card grid layout (not table/list)
- Each card shows: workflow name, creation date, last updated date
- Delete action should be easy — no complex confirmation modal (simple inline confirm or single-click with lightweight confirmation)
- Empty state: "No saved workflows" message
- Click card to open workflow in editor
- "Create new" action navigates to /workflow/new

**Save/Load behavior**
- Manual save only — no auto-save
- Unsaved changes dot indicator (visual cue that current state differs from last saved state)
- New workflow flow: user must input a name → Save creates the workflow (POST)
- Existing workflow: Save updates in place (PUT)
- The toolbar name input field (already exists) serves as the name entry point

**Execution status on nodes**
- Status indicator rendered inside the CubeNode component (not external overlay)
- Running state: spinning animation on the node
- Done state: green check indicator
- Pending state: gray/neutral indicator
- Error state: error message displayed on top of the cube node (floating above), so the user can continue to see and edit the node content underneath
- Error message text visible directly — not hidden behind a tooltip or click

**Progress bar & run UX**
- Thin progress bar in the toolbar area showing "X/Y cubes completed"
- Canvas is locked during execution — no editing while running (nodes not draggable, params not editable, connections not modifiable)
- Run button should indicate running state (disabled or changed appearance)

**Keyboard shortcuts**
- Delete: removes selected nodes/edges
- Ctrl+S: saves workflow
- Ctrl+Enter: runs workflow
- Standard behavior per WFLOW-07

### Claude's Discretion
- Exact dashboard card styling and hover effects
- Progress bar color and animation
- How canvas locking is implemented (pointer-events, overlay, React Flow interactionMode)
- Unsaved changes detection mechanism (dirty flag comparison)
- Transition animations between routes
- How the spinning animation looks on the CubeNode (CSS spinner, animated border, pulsing glow)
- Exact error banner positioning and styling above nodes
- Whether delete confirmation is a toast-undo pattern or a small inline "Are you sure?" prompt

### Deferred Ideas (OUT OF SCOPE)
- Results drawer with full table + map view — Phase 6
- Auto-save / save-on-run — not for v1, manual save only
- Workflow duplication/cloning — potential future feature
- Execution history / run logs — future phase
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WFLOW-01 | React Router with routes: / (dashboard), /workflow/:id (editor), /workflow/new (new workflow) | React Router v7 `createBrowserRouter` + `RouterProvider` pattern; existing `react-router-dom` v7.13.1 installed |
| WFLOW-02 | Dashboard page listing all saved workflows with name, last modified date, and actions (open, rename, delete, create new) | `getWorkflows()` API already implemented; card grid layout using CSS Grid |
| WFLOW-03 | Save serializes current flow state (nodes, edges, params) to backend via PUT; Load deserializes and restores canvas | `createWorkflow`/`updateWorkflow` API implemented; `WorkflowGraph` schema maps to store nodes/edges; needs serialization logic in store |
| WFLOW-04 | Run button triggers SSE connection, streams per-cube status updates to Zustand store, updates CubeNode indicators in real-time | SSE at `GET /api/workflows/{id}/run/stream`; native `EventSource` API; custom `useWorkflowSSE` hook |
| WFLOW-05 | Each CubeNode shows execution status indicator: gray (pending), blue spinner (running), green check (done), red X (error with message) | `CubeStatusEvent` schema known; status stored per-node in Zustand; CubeNode reads from store via selector |
| WFLOW-06 | Error messages from failed cubes display inline on the CubeNode with the error text | Error event has `error: str` field; absolute-positioned overlay above node body |
| WFLOW-07 | Keyboard shortcuts — Delete removes selected nodes/edges, Ctrl+S saves workflow, Ctrl+Enter runs workflow | React Flow `deleteKeyCode` prop for Delete; `useEffect` with `keydown` listener for Ctrl+S/Ctrl+Enter |
| WFLOW-08 | Overall pipeline progress indicator during execution showing "X/Y cubes completed" with progress bar in toolbar area | Count of `done`+`error`+`skipped` events vs total node count; thin CSS progress bar in Toolbar |
</phase_requirements>

---

## Summary

Phase 5 closes the full product loop: users can navigate between a dashboard of saved workflows and the canvas editor, save/load flow state, and run workflows with live per-node status feedback via SSE. All foundational infrastructure is already in place — the missing work is wiring it up with React Router, store extensions, and a handful of new UI components.

The project already has `react-router-dom` v7.13.1 installed but not yet used. The routing integration requires wrapping `main.tsx` with `RouterProvider` and splitting the monolithic `App.tsx` into page components. The Zustand store needs four additions: a `workflowId`/`workflowName` tracking state, a `dirtyFlag` for unsaved changes detection, an `executionStatus` map per-node, and an `isRunning` boolean. The SSE implementation uses the native browser `EventSource` API (no extra library), encapsulated in a `useWorkflowSSE` custom hook that feeds events into the Zustand store. Canvas locking during execution is accomplished by conditionally passing `nodesDraggable={false}`, `nodesConnectable={false}`, and `elementsSelectable={false}` to the `<ReactFlow>` component when `isRunning` is true.

**Primary recommendation:** Wire React Router first (WFLOW-01), then extend the store (foundation for all other WFLOW requirements), then build Dashboard, then wire Save/Load into Toolbar, then implement SSE hook + execution status in CubeNode.

---

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-router-dom | 7.13.1 | SPA routing — dashboard ↔ editor navigation | Already in package.json; v7 is current major |
| zustand | 5.0.11 | Global state for nodes, edges, execution status | Already used for canvas state |
| @xyflow/react | 12.10.1 | Canvas, interaction props for locking | Already used |
| sonner | 2.0.7 | Toast notifications (save errors, run errors) | Already integrated |

### No Additional Libraries Needed
All required functionality is covered by installed packages:
- **EventSource**: Native browser API — no library needed for SSE
- **Keyboard shortcuts**: Native DOM `keydown` listener — no library needed
- **Progress bar**: CSS-only — no library needed
- **CSS spinner**: CSS `@keyframes` — no library needed

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native EventSource | `eventsource` npm package | Not needed — browser support is universal for SSE |
| keydown listener | `@react-hookz/web` useKeyboardEvent | Overkill — two shortcuts don't justify a library |
| CSS spinner | Lottie animation | Too heavy for a simple loading indicator |

**Installation:** No new packages required. Everything is already installed.

---

## Architecture Patterns

### Recommended File Structure

```
frontend/src/
├── pages/
│   ├── DashboardPage.tsx        # NEW: / route — card grid + create button
│   └── EditorPage.tsx           # NEW: /workflow/:id and /workflow/new routes
├── components/
│   ├── Dashboard/
│   │   ├── WorkflowList.tsx     # NEW: grid of WorkflowCard components
│   │   └── WorkflowCard.tsx     # NEW: individual card with actions
│   ├── CubeNode/
│   │   ├── CubeNode.tsx         # MODIFY: add status indicator + error banner
│   │   └── CubeNode.css         # MODIFY: add status styles
│   └── Toolbar/
│       ├── Toolbar.tsx          # MODIFY: wire save/run, add progress bar
│       └── Toolbar.css          # MODIFY: add progress bar styles
├── hooks/
│   └── useWorkflowSSE.ts        # NEW: EventSource hook
├── store/
│   └── flowStore.ts             # MODIFY: add workflow metadata + execution state
└── App.tsx                      # MODIFY: replace with RouterProvider
```

### Pattern 1: React Router v7 SPA Setup

**What:** Wrap the app in `createBrowserRouter` + `RouterProvider` instead of the existing `App.tsx` shell.
**When to use:** Required for all multi-page SPA navigation.

```typescript
// Source: https://reactrouter.com/api/data-routers/createBrowserRouter
// frontend/src/main.tsx — replace StrictMode wrapper

import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { DashboardPage } from './pages/DashboardPage';
import { EditorPage } from './pages/EditorPage';
import './styles/theme.css';
import './styles/glass.css';
import './index.css';

const router = createBrowserRouter([
  {
    path: '/',
    element: <DashboardPage />,
  },
  {
    path: '/workflow/new',
    element: <EditorPage />,
  },
  {
    path: '/workflow/:id',
    element: <EditorPage />,
  },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
```

**Key insight:** `ReactFlowProvider` and `Toaster` move into `EditorPage.tsx`, not the root.

### Pattern 2: EditorPage — useParams for load-on-mount

**What:** `EditorPage` reads `:id` from URL params and loads the workflow on mount.

```typescript
// Source: https://reactrouter.com/api/hooks/useParams
// frontend/src/pages/EditorPage.tsx

import { useParams } from 'react-router-dom';
import { useEffect } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import { Toaster } from 'sonner';
import { Toolbar } from '../components/Toolbar/Toolbar';
import { CubeCatalog } from '../components/Sidebar/CubeCatalog';
import { FlowCanvas } from '../components/Canvas/FlowCanvas';
import { useFlowStore } from '../store/flowStore';

export function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const loadWorkflow = useFlowStore((s) => s.loadWorkflow);
  const resetWorkflow = useFlowStore((s) => s.resetWorkflow);

  useEffect(() => {
    if (id) {
      loadWorkflow(id);  // GET /api/workflows/:id → restore nodes/edges/name/id
    } else {
      resetWorkflow();   // /workflow/new → clear canvas
    }
    return () => {
      // Clean up SSE on unmount
      useFlowStore.getState().stopExecution();
    };
  }, [id]);

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
```

### Pattern 3: Zustand Store Extensions

**What:** Add workflow metadata, dirty tracking, and execution state to the existing store.

```typescript
// Extension to existing FlowState interface in flowStore.ts

// New state fields
interface FlowState {
  // ... existing fields ...

  // Workflow metadata
  workflowId: string | null;       // null = unsaved new workflow
  workflowName: string;             // synced with Toolbar name input
  isDirty: boolean;                 // true = unsaved changes exist

  // Execution state
  isRunning: boolean;
  executionStatus: Record<string, {
    status: 'pending' | 'running' | 'done' | 'error' | 'skipped';
    error?: string;
    outputs?: Record<string, unknown>;
  }>;
  completedCount: number;  // done + error + skipped
  totalCount: number;      // total nodes in execution

  // New actions
  setWorkflowName: (name: string) => void;
  saveWorkflow: () => Promise<void>;
  loadWorkflow: (id: string) => Promise<void>;
  resetWorkflow: () => void;
  startExecution: () => void;
  stopExecution: () => void;
  setNodeExecutionStatus: (
    nodeId: string,
    status: CubeStatusEvent
  ) => void;
}
```

**Dirty flag strategy:** Set `isDirty = true` whenever `nodes`, `edges`, or `params` change (in `onNodesChange`, `onEdgesChange`, `updateNodeParam`). Set `isDirty = false` after successful save or load.

### Pattern 4: useWorkflowSSE Hook

**What:** Custom hook encapsulating `EventSource` lifecycle for the SSE stream.
**When to use:** Called from `Toolbar` when Run is clicked, passing workflow ID.

```typescript
// Source: MDN EventSource API + project SSE endpoint
// frontend/src/hooks/useWorkflowSSE.ts

import { useRef, useCallback } from 'react';
import { useFlowStore } from '../store/flowStore';
import type { CubeStatusEvent } from '../types/execution';

export function useWorkflowSSE() {
  const esRef = useRef<EventSource | null>(null);
  const store = useFlowStore.getState;

  const startStream = useCallback((workflowId: string) => {
    // Close any existing connection
    if (esRef.current) {
      esRef.current.close();
    }

    useFlowStore.getState().startExecution();

    const url = `/api/workflows/${workflowId}/run/stream`;
    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener('cube_status', (event: MessageEvent) => {
      const data: CubeStatusEvent = JSON.parse(event.data);
      useFlowStore.getState().setNodeExecutionStatus(data.node_id, data);

      // Detect completion: all nodes have reached terminal status
      const state = useFlowStore.getState();
      const allDone = Object.values(state.executionStatus).every(
        (s) => ['done', 'error', 'skipped'].includes(s.status)
      );
      if (allDone && state.totalCount > 0) {
        es.close();
        useFlowStore.getState().stopExecution();
      }
    });

    es.onerror = () => {
      es.close();
      useFlowStore.getState().stopExecution();
    };
  }, []);

  const stopStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    useFlowStore.getState().stopExecution();
  }, []);

  return { startStream, stopStream };
}
```

**Critical:** The backend SSE endpoint is `GET /api/workflows/{id}/run/stream`. The event type is `cube_status`. The `EventSource` URL must go through the Vite proxy (same `/api` prefix used by `apiFetch`).

**Completion detection:** The backend emits `pending` for all N nodes first, then `running`/`done`/`error`/`skipped` for each. Terminal states are `done`, `error`, `skipped`. Track total node count from the `pending` burst count. When `completedCount === totalCount`, close the connection.

### Pattern 5: Canvas Locking During Execution

**What:** Pass boolean props to `<ReactFlow>` to disable all editing while `isRunning` is true.
**Implementation:** Read `isRunning` from store in `FlowCanvas.tsx`.

```typescript
// In FlowCanvas.tsx — add isRunning from store
const isRunning = useFlowStore((s) => s.isRunning);

// Pass to ReactFlow component
<ReactFlow
  // ... existing props ...
  nodesDraggable={!isRunning}
  nodesConnectable={!isRunning}
  elementsSelectable={!isRunning}
  edgesReconnectable={!isRunning}
/>
```

**Why this approach:** Cleanest API-level solution with no DOM overlay needed. All four props together prevent dragging, connecting, selecting, and edge editing.

### Pattern 6: Keyboard Shortcuts

**What:** Global `keydown` listener in a `useEffect` inside `EditorPage` (or Toolbar).

```typescript
// In Toolbar.tsx or EditorPage.tsx
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    // Prevent shortcuts when typing in inputs
    const tag = (e.target as HTMLElement).tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;

    if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSave();
    }
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleRun();
    }
  };
  document.addEventListener('keydown', handleKeyDown);
  return () => document.removeEventListener('keydown', handleKeyDown);
}, [handleSave, handleRun]);
```

**Delete key:** React Flow handles Delete natively via the `deleteKeyCode` prop. The default includes `'Backspace'`. To also support `'Delete'`:

```typescript
// In ReactFlow component
deleteKeyCode={['Delete', 'Backspace']}
```

**IMPORTANT:** The input fields on CubeNode already have the `nodrag` class. The keyboard handler must guard against `INPUT`/`TEXTAREA` targets to prevent triggering shortcuts while typing in param fields.

### Pattern 7: Save/Load Serialization

**What:** Map between the Zustand store's `CubeFlowNode[]` and the API's `WorkflowGraph` type.

**Save (store → API):**
```typescript
// Serialize current store state to WorkflowGraph
const serializeGraph = (
  nodes: CubeFlowNode[],
  edges: Edge[]
): WorkflowGraph => ({
  nodes: nodes.map((n) => ({
    id: n.id,
    type: n.type ?? 'cube',
    position: n.position,
    data: {
      cube_id: n.data.cube_id,
      params: n.data.params,
    },
  })),
  edges: edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle ?? null,
    targetHandle: e.targetHandle ?? null,
  })),
});
```

**Load (API → store):**
```typescript
// Deserialize WorkflowGraph back to CubeFlowNode[]
// Must re-attach cubeDef from catalog (not stored in graph)
const deserializeGraph = (
  graph: WorkflowGraph,
  catalog: CubeDefinition[]
): CubeFlowNode[] => {
  return graph.nodes.map((n) => {
    const cubeDef = catalog.find((c) => c.cube_id === n.data.cube_id)!;
    return {
      id: n.id,
      type: 'cube',
      position: n.position,
      data: {
        cube_id: n.data.cube_id,
        cubeDef,           // re-hydrated from catalog
        params: n.data.params,
      },
    };
  });
};
```

**Critical insight:** `WorkflowGraph` nodes only store `cube_id` and `params` — not the full `CubeDefinition`. On load, `cubeDef` must be re-hydrated from the in-memory catalog. The catalog must be loaded before `loadWorkflow` is called. The existing `catalogLoading` flag ensures this ordering.

### Pattern 8: Workflow Name for New Workflows

**What:** For `/workflow/new`, the user types a name in the Toolbar name input, then clicks Save. Save checks `workflowId === null` to decide between POST (create) and PUT (update).

```typescript
// In flowStore.ts saveWorkflow action
saveWorkflow: async () => {
  const { workflowId, workflowName, nodes, edges } = get();
  const graph = serializeGraph(nodes, edges);

  if (workflowId === null) {
    // New workflow — POST
    const response = await createWorkflow(workflowName, graph);
    set({ workflowId: response.id, isDirty: false });
    // Navigate to /workflow/:id so the URL updates
    // Use navigate() — store can't call navigate directly;
    // caller (Toolbar) must handle navigation after save resolves
  } else {
    // Existing workflow — PUT
    await updateWorkflow(workflowId, workflowName, graph);
    set({ isDirty: false });
  }
},
```

**Navigation after new workflow save:** Since Zustand can't call React Router's `navigate()`, the `Toolbar` component calls `saveWorkflow()`, awaits it, then calls `navigate('/workflow/' + workflowId)` from the updated store state.

### Anti-Patterns to Avoid

- **Don't store `cubeDef` in the backend graph:** `WorkflowGraph` stores only `cube_id + params`. Re-hydrate on load.
- **Don't open SSE before saving:** The SSE endpoint needs the workflow ID. For unsaved workflows, save first, then run.
- **Don't put RouterProvider inside a component:** It must be at the root render level (in `main.tsx`).
- **Don't use `<a href="/">` for navigation:** The Toolbar already uses an `<a>` tag for the dashboard link. With React Router, replace with `<Link to="/">` to avoid full-page reloads.
- **Don't listen for SSE completion solely by `es.close()` from the server:** The server closes the stream, but `EventSource` may auto-reconnect. Detect completion in the `cube_status` handler by checking terminal states, then call `es.close()` explicitly on the client.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SPA routing | Custom history/location management | React Router v7 `createBrowserRouter` | Already installed, handles history, params, navigation |
| SSE reconnection | Custom retry logic with timers | Native `EventSource` auto-reconnect | Browser handles reconnect automatically; close explicitly on terminal state |
| Toast notifications | Custom notification component | `sonner` (already integrated) | Already used in Phase 4 for connection errors |
| Serialization format | Custom binary/compressed format | JSON via existing `WorkflowGraph` Pydantic schema | Backend schema already defined; maps directly |
| Canvas interaction disable | CSS pointer-events overlay | React Flow `nodesDraggable` / `nodesConnectable` props | API-level control, no z-index fighting |

---

## Common Pitfalls

### Pitfall 1: SSE Completion Detection
**What goes wrong:** The backend closes the SSE stream when done, but `EventSource` treats server-close as a disconnect and auto-reconnects, starting a new execution unexpectedly.
**Why it happens:** `EventSource.readyState` becomes `CONNECTING` (0) after server close, not `CLOSED` (2).
**How to avoid:** In the `cube_status` event handler, count terminal events. When `completedCount === totalCount`, explicitly call `es.close()`. Don't rely on server-initiated close.
**Warning signs:** The run button re-enables, then disables again unexpectedly after execution ends.

### Pitfall 2: cubeDef Missing After Load
**What goes wrong:** Canvas loads with nodes but they render as empty/broken because `cubeDef` is undefined.
**Why it happens:** `WorkflowGraph` only stores `cube_id`, not the full definition. If catalog hasn't loaded yet when `loadWorkflow` runs, `catalog.find()` returns undefined.
**How to avoid:** Check `catalog.length > 0` before deserializing. Add a guard in `loadWorkflow` that waits for catalog or returns early. In `EditorPage`, ensure catalog fetch completes before `loadWorkflow` is called.
**Warning signs:** Console errors like "Cannot read properties of undefined" from CubeNode trying to access `cubeDef.category`.

### Pitfall 3: Delete Shortcut Fires Inside Input Fields
**What goes wrong:** User types in a CubeNode param field, presses Delete/Backspace, and the node gets deleted.
**Why it happens:** React Flow's `deleteKeyCode` applies globally, including when inputs inside nodes are focused.
**How to avoid:** React Flow already handles this: when focus is inside an input within the node, the default delete behavior is suppressed. BUT the custom Ctrl+S / Ctrl+Enter handler must check `e.target.tagName` before acting. Verify React Flow's default behavior holds for the `Delete` key in this project's CubeNode structure.
**Warning signs:** Nodes disappearing while editing parameter values.

### Pitfall 4: Routing Breaks ReactFlowProvider Scope
**What goes wrong:** React Flow hooks (`useReactFlow`, `useNodes`) throw errors after adding Router because `ReactFlowProvider` scope changes.
**Why it happens:** Moving `ReactFlowProvider` from `App.tsx` to `EditorPage.tsx` can leave components that depend on `useReactFlow` outside the provider if the component tree structure changes.
**How to avoid:** Keep `ReactFlowProvider` wrapping `FlowCanvas` in `EditorPage` exactly as it was in `App.tsx`. Confirm `FlowCanvas` is the only component using `useReactFlow`.
**Warning signs:** "could not find ReactFlow context" error in console.

### Pitfall 5: Unsaved Changes on Navigation
**What goes wrong:** User navigates away from `/workflow/:id` to the dashboard and loses unsaved changes silently.
**Why it happens:** React Router does not block navigation by default.
**How to avoid:** This phase does NOT implement navigation blocking (not in requirements). The `isDirty` dot indicator is the only warning mechanism. This is acceptable per the locked decisions.

### Pitfall 6: Running an Unsaved Workflow
**What goes wrong:** User clicks Run on a brand-new workflow (no ID yet) — SSE endpoint needs `/api/workflows/{id}/run/stream` but there's no ID.
**Why it happens:** New workflows at `/workflow/new` have `workflowId === null`.
**How to avoid:** The Run handler must check: if `workflowId === null`, save first, then run. Show a toast "Saving workflow before running..." to inform the user.

### Pitfall 7: Progress Bar Count Including "pending" Events
**What goes wrong:** Progress shows "5/3 cubes completed" because `pending` events were counted as completion events.
**Why it happens:** The SSE stream sends `pending` for all nodes first, then transitions. Counting all events instead of only terminal ones inflates the number.
**How to avoid:** Only increment `completedCount` on `done`, `error`, and `skipped` statuses. Set `totalCount` from the first burst of `pending` events (count them as they arrive).

---

## Code Examples

### SSE Event Shape (from backend schema)

```typescript
// Source: backend/app/schemas/execution.py — CubeStatusEvent
// frontend/src/types/execution.ts (new file to create)

export type CubeStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped';

export interface CubeStatusEvent {
  node_id: string;
  status: CubeStatus;
  outputs?: Record<string, unknown>;   // present on 'done'
  truncated?: boolean;                  // present on 'done'
  error?: string;                       // present on 'error'
  reason?: string;                      // present on 'skipped'
}
```

### CubeNode Status Indicator (inside node)

```typescript
// Inside CubeNode.tsx — read status from store
const executionStatus = useFlowStore(
  (s) => s.executionStatus[id]
);

// Status indicator in the header area
{executionStatus && (
  <span className={`cube-node__status cube-node__status--${executionStatus.status}`}>
    {executionStatus.status === 'running' && <span className="cube-node__spinner" />}
    {executionStatus.status === 'done' && <CheckIcon />}
    {executionStatus.status === 'error' && <ErrorIcon />}
  </span>
)}

// Error banner (floating above node, absolute positioned)
{executionStatus?.status === 'error' && executionStatus.error && (
  <div className="cube-node__error-banner">
    {executionStatus.error}
  </div>
)}
```

### Error Banner CSS Pattern

```css
/* Positioned above the node, does not obscure node content */
.cube-node__error-banner {
  position: absolute;
  bottom: calc(100% + 6px);  /* float above the node */
  left: 0;
  right: 0;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid var(--color-error);
  border-radius: var(--radius-sm);
  color: var(--color-error);
  font-size: 11px;
  padding: 6px 10px;
  z-index: 10;
  word-break: break-word;
}
```

### Progress Bar in Toolbar

```typescript
// Toolbar — progress state from store
const isRunning = useFlowStore((s) => s.isRunning);
const completedCount = useFlowStore((s) => s.completedCount);
const totalCount = useFlowStore((s) => s.totalCount);
const progress = totalCount > 0 ? completedCount / totalCount : 0;

// JSX in toolbar
{isRunning && (
  <div className="toolbar__progress-bar">
    <div
      className="toolbar__progress-bar__fill"
      style={{ width: `${progress * 100}%` }}
    />
    <span className="toolbar__progress-label">
      {completedCount}/{totalCount} cubes
    </span>
  </div>
)}
```

### Unsaved Changes Indicator

```typescript
// Next to the workflow name input in Toolbar
const isDirty = useFlowStore((s) => s.isDirty);

// In JSX
<div className="toolbar__center">
  <input
    type="text"
    className="toolbar__name-input nodrag"
    value={workflowName}
    onChange={(e) => setWorkflowName(e.target.value)}
  />
  {isDirty && <span className="toolbar__dirty-dot" aria-label="Unsaved changes" />}
</div>
```

### Dashboard Card Grid

```typescript
// WorkflowList.tsx
export function WorkflowList() {
  const [workflows, setWorkflows] = useState<WorkflowResponse[]>([]);

  useEffect(() => {
    getWorkflows().then(setWorkflows).catch(() => {
      toast.error('Failed to load workflows');
    });
  }, []);

  if (workflows.length === 0) {
    return <div className="workflow-list__empty">No saved workflows</div>;
  }

  return (
    <div className="workflow-list__grid">
      {workflows.map((wf) => (
        <WorkflowCard key={wf.id} workflow={wf} onDelete={...} />
      ))}
    </div>
  );
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| React Router v5 `<Switch>` + `<Route>` | v7 `createBrowserRouter` + `RouterProvider` | React Router v6.4+ | Data loaders, cleaner route config |
| WebSocket for real-time | EventSource (SSE) for server-push | Project design decision | Simpler for unidirectional stream; no library needed |
| Global `window` navigation | React Router `useNavigate()` hook | v6+ | Component-level navigation, no full reload |

**Deprecated/outdated:**
- `<BrowserRouter>` + `<Routes>` + `<Route>`: Still valid but the data router pattern (`createBrowserRouter`) is preferred for route-level data fetching and better TypeScript integration.
- The existing `<a href="/">` in `Toolbar.tsx`: Must become `<Link to="/">` to avoid full-page reload.

---

## Open Questions

1. **Catalog ordering on load**
   - What we know: `loadWorkflow` needs `catalog` to be populated to re-hydrate `cubeDef`.
   - What's unclear: The catalog fetch is triggered by `CubeCatalog` component's `useEffect` — if EditorPage mounts and triggers `loadWorkflow` before `CubeCatalog` has fetched the catalog, nodes will fail to hydrate.
   - Recommendation: Move catalog fetch into `EditorPage`'s `useEffect` (or a shared hook) that runs before `loadWorkflow`. Alternatively, have `loadWorkflow` in the store wait for `catalog.length > 0` with a retry or a Promise-based catalog ready signal.

2. **Route for renamed workflows**
   - What we know: After save, the URL should be `/workflow/:id`. After creating a new workflow, the URL must update from `/workflow/new` to `/workflow/:id`.
   - What's unclear: The store's `saveWorkflow` action cannot call `navigate()` — it must return the new ID and let the Toolbar call `navigate()`.
   - Recommendation: `saveWorkflow` returns `Promise<string>` (the workflow ID). The Toolbar's `handleSave` calls `navigate('/workflow/' + id, { replace: true })` after save resolves.

3. **SSE and Vite proxy buffering**
   - What we know: The backend sets `X-Accel-Buffering: no` header specifically to prevent nginx buffering of SSE.
   - What's unclear: Vite's dev proxy may buffer SSE responses, causing events to arrive in batches rather than individually.
   - Recommendation: Add `headers: { 'Cache-Control': 'no-cache' }` awareness in the SSE fetch. If Vite buffering is observed during development, add `proxy.ws: true` or configure Vite proxy with `agent` settings. In production this is a non-issue.

---

## Sources

### Primary (HIGH confidence)
- Codebase analysis — `frontend/src/store/flowStore.ts`, `frontend/src/api/workflows.ts`, `backend/app/routers/workflows.py`, `backend/app/schemas/execution.py` — all implementation details verified from source
- `frontend/package.json` — confirmed library versions: react-router-dom 7.13.1, @xyflow/react 12.10.1, zustand 5.0.11, sonner 2.0.7
- [React Flow API Reference](https://reactflow.dev/api-reference/react-flow) — confirmed `nodesDraggable`, `nodesConnectable`, `elementsSelectable`, `edgesReconnectable`, `deleteKeyCode` props
- [createBrowserRouter - React Router](https://reactrouter.com/api/data-routers/createBrowserRouter) — confirmed current v7 routing pattern

### Secondary (MEDIUM confidence)
- [React Router v7 upgrade guide](https://reactrouter.com/upgrading/v6) — confirmed v7 API compatibility with `react-router-dom` import path
- Web search verification of EventSource/SSE patterns — confirmed native browser API approach is standard

### Tertiary (LOW confidence)
- Vite proxy SSE buffering behavior — based on community knowledge, not verified against Vite 7 docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed in package.json
- Architecture: HIGH — all integration points verified against existing source code
- Pitfalls: HIGH — derived from actual code analysis (serialization gap, EventSource reconnect behavior)
- SSE event schema: HIGH — verified against `backend/app/schemas/execution.py`

**Research date:** 2026-03-04
**Valid until:** 2026-05-04 (stable libraries, 60-day window)
