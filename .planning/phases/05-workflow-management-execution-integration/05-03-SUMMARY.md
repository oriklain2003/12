---
phase: 05-workflow-management-execution-integration
plan: 03
subsystem: frontend-execution
tags: [sse, toolbar, execution, canvas-locking, keyboard-shortcuts, status-indicators]
dependency_graph:
  requires: [05-01]
  provides: [complete-execution-loop, save-run-workflow, live-node-status]
  affects: [frontend/src/hooks, frontend/src/components/Toolbar, frontend/src/components/Canvas, frontend/src/components/CubeNode]
tech_stack:
  added: [EventSource SSE client, sonner toast notifications, React Router Link]
  patterns: [useRef for EventSource lifecycle, useCallback for stable handlers, Zustand getState() for non-reactive reads in hooks]
key_files:
  created:
    - frontend/src/hooks/useWorkflowSSE.ts
  modified:
    - frontend/src/components/Toolbar/Toolbar.tsx
    - frontend/src/components/Toolbar/Toolbar.css
    - frontend/src/components/Canvas/FlowCanvas.tsx
    - frontend/src/components/CubeNode/CubeNode.tsx
    - frontend/src/components/CubeNode/CubeNode.css
decisions:
  - useRef<EventSource | null> holds SSE connection to survive renders without triggering re-renders
  - EventSource must be explicitly closed on completion — auto-reconnects on server close
  - Error banner positioned inside .cube-node (position: relative) at bottom: calc(100% + 6px) to float above node
  - Close button hidden (not disabled) during execution to cleanly prevent node removal
  - Keyboard shortcut handler guards against INPUT/TEXTAREA for Delete but allows Ctrl+S and Ctrl+Enter in all contexts
metrics:
  duration: 3min
  completed_date: "2026-03-04"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 5
---

# Phase 05 Plan 03: Execution Loop Wiring Summary

**One-liner:** Full execution loop wired — SSE hook streams live per-node status with spinner/check/error indicators, Toolbar saves/runs with Ctrl+S/Ctrl+Enter shortcuts, canvas locks during execution, and error banners float above nodes.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create useWorkflowSSE hook, wire Toolbar, add canvas locking | cd5d19f | useWorkflowSSE.ts, Toolbar.tsx, Toolbar.css, FlowCanvas.tsx |
| 2 | Add execution status indicator and error banner to CubeNode | 9a2ccea | CubeNode.tsx, CubeNode.css |

## What Was Built

### useWorkflowSSE Hook (`frontend/src/hooks/useWorkflowSSE.ts`)

New hook implementing SSE-based workflow execution streaming:

- Exports `useWorkflowSSE()` returning `{ startStream, stopStream }`
- Uses `useRef<EventSource | null>` to hold connection across renders
- `startStream(workflowId)`: closes existing connection, calls `startExecution()`, creates `new EventSource('/api/workflows/{id}/run/stream')`
- Listens for `'cube_status'` typed events (NOT default `'message'` — backend sends named events)
- After each event, checks `completedCount >= totalCount` and explicitly closes on completion (EventSource auto-reconnects otherwise)
- `onerror`: closes connection and calls `stopExecution()`

### Toolbar (`frontend/src/components/Toolbar/Toolbar.tsx`)

Complete rewrite from placeholder to fully wired toolbar:

- Workflow name synced from Zustand store (removed local `useState`)
- Unsaved changes dot (`toolbar__dirty-dot`) shown when `isDirty === true`
- `handleSave`: validates name, calls `saveWorkflow()`, shows toast, navigates to `/workflow/:id` on first save
- `handleRun`: saves first if no `workflowId`, then calls `startStream(id)`
- Progress bar shown during `isRunning`: thin 4px bar with width animated to `(completedCount/totalCount)*100%`
- Run button changes to "Running..." with `toolbar__btn--running` class and disabled state
- Dashboard link changed from `<a href="/">` to `<Link to="/">` (SPA navigation)
- Keyboard shortcuts via `useEffect` + `keydown` listener: Ctrl+S saves, Ctrl+Enter runs

### FlowCanvas (`frontend/src/components/Canvas/FlowCanvas.tsx`)

Added canvas locking during execution:

```tsx
nodesDraggable={!isRunning}
nodesConnectable={!isRunning}
elementsSelectable={!isRunning}
edgesReconnectable={!isRunning}
deleteKeyCode={isRunning ? null : ['Delete', 'Backspace']}
```

### CubeNode (`frontend/src/components/CubeNode/CubeNode.tsx` + `CubeNode.css`)

Added execution status indicators:

- **Status badge in header**: `cube-node__status--{status}` class variants
  - `pending`: gray circle (no icon)
  - `running`: blue circle with `cube-node__spinner` (CSS keyframe animation)
  - `done`: green circle with checkmark SVG
  - `error`: red circle with X SVG
  - `skipped`: muted circle with dash SVG
- **Error banner**: absolute positioned ABOVE the node (`bottom: calc(100% + 6px)`), visible without obscuring node content, backdrop-blur for legibility
- **Running glow**: `cube-node--running` class adds `box-shadow: 0 0 20px rgba(99, 102, 241, 0.2)`
- **Close button**: hidden (not disabled) during `isRunning` to prevent accidental node removal

## Decisions Made

1. **useRef for EventSource**: Not state — connection lifecycle managed imperatively. Avoids triggering re-renders on connect/disconnect.

2. **Explicit close on terminal state**: EventSource auto-reconnects when server closes the stream. Must check `completedCount >= totalCount` after each event and call `es.close()` explicitly.

3. **Error banner inside .cube-node**: The banner is a child of the node div (which has `position: relative`), using `position: absolute; bottom: calc(100% + 6px)` to float above. React Flow renders each node in its own container so this is the correct approach.

4. **Hide close button during execution**: Hiding (conditional render) rather than disabling is cleaner UX — the button disappears and can't be accidentally clicked.

5. **Keyboard shortcuts allow Ctrl+S/Ctrl+Enter in inputs**: The handler only skips Delete/Backspace for INPUT/TEXTAREA elements, but Ctrl+S and Ctrl+Enter work everywhere including the workflow name input.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `frontend/src/hooks/useWorkflowSSE.ts` exists with `EventSource` usage
- [x] `frontend/src/components/Toolbar/Toolbar.tsx` contains `saveWorkflow` and `Link to="/"`
- [x] `frontend/src/components/Canvas/FlowCanvas.tsx` contains `isRunning` for canvas locking
- [x] `frontend/src/components/CubeNode/CubeNode.tsx` contains `executionStatus`
- [x] `frontend/src/components/CubeNode/CubeNode.css` contains `cube-node__error-banner` and `cube-node__spinner`
- [x] TypeScript: zero errors (`npx tsc --noEmit` clean)
- [x] Commits cd5d19f and 9a2ccea exist

## Self-Check: PASSED
