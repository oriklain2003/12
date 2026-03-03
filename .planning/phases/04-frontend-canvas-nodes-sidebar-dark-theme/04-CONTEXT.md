# Phase 4: Frontend Canvas, Nodes, Sidebar & Dark Theme - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Full visual editor — drag cubes from sidebar onto canvas, configure parameters inline, connect node outputs to inputs. Includes dark theme, liquid glass styling, Zustand store, API client, and connection validation. Does NOT include workflow save/load, SSE execution, routing, or dashboard (Phase 5).

Requirements: FRONT-02 through FRONT-12.

</domain>

<decisions>
## Implementation Decisions

### Node visual design & dark theme
- Dark theme with CSS custom properties for the entire app
- Liquid glass effect on nodes — find a well-regarded implementation from GitHub/open-source libraries (backdrop-filter blur + saturation approach from ROADMAP)
- Category visual distinction — Claude's discretion (color accents, icons, header bars)

### Parameter editing on nodes
- Simple types (string, number, boolean): standard inputs (text, number, checkbox)
- Complex types (list_of_strings, list_of_numbers, json_object): research online solutions for compact input widgets — must not dominate the node or take excessive canvas space
- Editors should be compact — roughly a third of the node height at most
- "Hidden when connected" behavior: Claude's discretion on how to indicate a param is receiving its value from a connection

### Catalog sidebar
- Drag initiation via a drag handle on each cube card (not the entire card)
- Collapsed state shows as an icon strip (not fully hidden)
- Search input filters cubes by name inclusion (substring match)
- Grouped by CubeCategory as specified in requirements

### Connection visuals & validation
- Solid lines for valid connections (not animated or gradient)
- Straight edge routing (not bezier or step)
- Type mismatch: dashed orange edge with warning (per FRONT-12)
- Full Result incompatibility: error toast when user attempts to connect Full Result to an input without accepts_full_result=true — connection prevented
- Color-coded handles by ParamType as specified (FRONT-05)

### Claude's Discretion
- Category visual differentiation approach (color scheme, icons, header styling)
- Exact dark theme color palette and CSS variable naming
- Liquid glass library/implementation choice
- Complex type input widget selection (tag inputs, textareas, JSON editors, etc.)
- How "hidden when connected" is visually communicated on the node
- Zustand store internal structure and action design
- API client error handling patterns
- Toolbar layout and styling
- Results preview compact layout on nodes

</decisions>

<specifics>
## Specific Ideas

- Liquid glass effect should come from a proven open-source approach — not custom-built from scratch
- Complex param editors should be space-efficient; the canvas is the primary workspace, nodes should stay compact
- Icon strip for collapsed sidebar keeps the catalog accessible without wasting horizontal space

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `types/cube.ts`: ParamType, CubeCategory, ParamDefinition, CubeDefinition — used for node rendering, handle colors, catalog grouping
- `types/workflow.ts`: WorkflowNode, WorkflowEdge, WorkflowGraph — used for Zustand store and React Flow integration
- `@xyflow/react` v12 already installed — provides canvas, node/edge rendering, handle system
- `zustand` v5 already installed — state management
- `react-router-dom` v7 installed — but routing is Phase 5; available if needed for basic setup

### Established Patterns
- No frontend patterns exist yet — this phase establishes all conventions (component structure, styling approach, state management patterns)
- Backend API at `/api/*` proxied via Vite config — API client should target these paths

### Integration Points
- `GET /api/cubes/catalog` — fetches cube definitions for sidebar catalog
- Vite proxy already configured to forward `/api` to backend port 8000
- TypeScript types already mirror backend schemas — no translation layer needed

</code_context>

<deferred>
## Deferred Ideas

- Workflow save/load and dashboard — Phase 5
- SSE execution with live status indicators on nodes — Phase 5
- Keyboard shortcuts (Ctrl+S, Ctrl+Enter, Delete) — Phase 5
- Results drawer with table + map — Phase 6
- Polygon drawing UI on canvas — future phase

</deferred>

---

*Phase: 04-frontend-canvas-nodes-sidebar-dark-theme*
*Context gathered: 2026-03-03*
