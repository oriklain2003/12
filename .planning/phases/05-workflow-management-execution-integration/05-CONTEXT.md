# Phase 5: Workflow Management & Execution Integration - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Full loop — dashboard listing saved workflows, save/load workflow state, run with live SSE status indicators on CubeNodes, keyboard shortcuts, and pipeline progress bar. Routes: / (dashboard), /workflow/:id (editor), /workflow/new (new workflow).

Requirements: WFLOW-01 through WFLOW-08.

</domain>

<decisions>
## Implementation Decisions

### Dashboard layout
- Card grid layout (not table/list)
- Each card shows: workflow name, creation date, last updated date
- Delete action should be easy — no complex confirmation modal (simple inline confirm or single-click with lightweight confirmation)
- Empty state: "No saved workflows" message
- Click card to open workflow in editor
- "Create new" action navigates to /workflow/new

### Save/Load behavior
- Manual save only — no auto-save
- Unsaved changes dot indicator (visual cue that current state differs from last saved state)
- New workflow flow: user must input a name → Save creates the workflow (POST)
- Existing workflow: Save updates in place (PUT)
- The toolbar name input field (already exists) serves as the name entry point

### Execution status on nodes
- Status indicator rendered inside the CubeNode component (not external overlay)
- Running state: spinning animation on the node
- Done state: green check indicator
- Pending state: gray/neutral indicator
- Error state: error message displayed on top of the cube node (floating above), so the user can continue to see and edit the node content underneath
- Error message text visible directly — not hidden behind a tooltip or click

### Progress bar & run UX
- Thin progress bar in the toolbar area showing "X/Y cubes completed"
- Canvas is locked during execution — no editing while running (nodes not draggable, params not editable, connections not modifiable)
- Run button should indicate running state (disabled or changed appearance)

### Keyboard shortcuts
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

</decisions>

<specifics>
## Specific Ideas

- Error messages float on top of the cube so the node content remains visible and editable — error should not obscure the node's inputs/outputs
- Dashboard should feel lightweight — card grid, not a heavy table with sortable columns
- "No saved workflows" empty state keeps it simple — no elaborate illustrations needed
- Unsaved changes dot is a small visual indicator (like a dot on the Save button or next to the workflow name)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/workflows.ts`: Full CRUD functions already implemented (getWorkflows, getWorkflow, createWorkflow, updateWorkflow, deleteWorkflow)
- `api/client.ts`: apiFetch<T> generic wrapper with ApiError class
- `store/flowStore.ts`: Zustand store with nodes, edges, catalog, results, params — needs save/load/run actions added
- `Toolbar.tsx`: Has Save/Run placeholder buttons and editable name input — ready to wire up
- `CubeNode.tsx`: Custom node component — needs status indicator and error banner additions
- `ResultsPanel.tsx`: Already reads results from store — execution results flow naturally
- `sonner` toast library already integrated for error/info messages
- `react-router-dom` v7 already installed — not yet used

### Established Patterns
- Dark theme via CSS custom properties (`theme.css`)
- Liquid glass effect via `glass` CSS class (backdrop-filter: blur(12px) saturate(150%))
- Zustand selectors for component-level state reads (ParamField pattern)
- Category color accents on CubeNode headers
- SSE backend endpoint at `GET /api/workflows/{id}/run/stream` — streams CubeStatusEvent (pending, running, done, error)

### Integration Points
- `App.tsx` currently renders Toolbar + CubeCatalog + FlowCanvas directly — needs React Router wrapping with route-based page components
- `Toolbar.tsx` Save/Run handlers are console.log placeholders — wire to store actions
- `flowStore.ts` needs: execution status per node, save/load actions, SSE connection management, dirty state tracking
- SSE events from Phase 3 backend include: node_id, status (pending/running/done/error), outputs, error message
- Dashboard page is new — needs DashboardPage component + WorkflowList/WorkflowCard sub-components

</code_context>

<deferred>
## Deferred Ideas

- Results drawer with full table + map view — Phase 6
- Auto-save / save-on-run — not for v1, manual save only
- Workflow duplication/cloning — potential future feature
- Execution history / run logs — future phase

</deferred>

---

*Phase: 05-workflow-management-execution-integration*
*Context gathered: 2026-03-04*
