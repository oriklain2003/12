---
phase: 04-frontend-canvas-nodes-sidebar-dark-theme
plan: 03
subsystem: ui
tags: [react-flow, zustand, typescript, dark-theme, canvas, sidebar, toolbar, drag-drop]

# Dependency graph
requires:
  - phase: 04-01
    provides: TypeScript types, API client, Vite scaffold, dark theme CSS vars
  - phase: 04-02
    provides: Zustand flowStore, CubeNode component hierarchy, ParamHandle colors

provides:
  - FlowCanvas with React Flow v12, dot grid background, drop handler, connection validation
  - MismatchEdge custom edge (dashed orange for type mismatches)
  - CubeCatalog sidebar: grouped by category, searchable, collapsible to icon strip
  - Toolbar: editable workflow name, Save/Run placeholder buttons, Dashboard link
  - App.tsx root shell wiring all components with ReactFlowProvider and Toaster

affects: [05-workflow-management-execution, phase-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "nodeTypes and edgeTypes defined at module level (React Flow v12 requirement — prevents re-registration warnings)"
    - "isValidConnection typed as IsValidConnection<Edge> (React Flow v12 accepts Edge | Connection)"
    - "Custom onConnect in component (not store) to detect type mismatches and assign edge.type='mismatch'"
    - "Sidebar drag handle only (not card) sets application/cube-id on dataTransfer"
    - "const + type alias pattern for enums (satisfies erasableSyntaxOnly)"

key-files:
  created:
    - frontend/src/components/Canvas/FlowCanvas.tsx
    - frontend/src/components/Canvas/FlowCanvas.css
    - frontend/src/components/Canvas/MismatchEdge.tsx
    - frontend/src/components/Sidebar/CubeCatalog.tsx
    - frontend/src/components/Sidebar/CubeCatalog.css
    - frontend/src/components/Toolbar/Toolbar.tsx
    - frontend/src/components/Toolbar/Toolbar.css
  modified:
    - frontend/src/App.tsx
    - frontend/src/App.css
    - frontend/src/types/cube.ts
    - frontend/src/api/client.ts

key-decisions:
  - "Full Result rejection: toast.error + return false from isValidConnection (prevents connection entirely)"
  - "Type mismatches allowed: custom onConnect assigns edge.type='mismatch' for dashed orange rendering"
  - "Sidebar drag initiation on handle element only (not whole card) per user decision"
  - "Toolbar Run/Save are Phase 5 placeholders — console.log only, no disabled state needed yet"
  - "cube.ts enums converted to const+type alias pattern to satisfy erasableSyntaxOnly tsconfig flag"
  - "ApiError.status moved from constructor shorthand to explicit property (erasableSyntaxOnly fix)"

patterns-established:
  - "React Flow provider wraps canvas component (ReactFlowProvider in App, useReactFlow inside FlowCanvas)"
  - "Module-level nodeTypes/edgeTypes registration prevents React Flow re-registration on re-renders"
  - "useFlowStore.getState() inside callbacks (not reactive hooks) for non-reactive reads in event handlers"

requirements-completed: [FRONT-03, FRONT-08, FRONT-10, FRONT-12]

# Metrics
duration: 10min
completed: 2026-03-03
---

# Phase 04 Plan 03: Canvas, Sidebar, Toolbar, App Shell Summary

**React Flow canvas with drop-to-create, type-mismatch edge highlighting, and collapsible cube catalog sidebar wired into a full dark-theme editor shell**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-03T22:57:26Z
- **Completed:** 2026-03-03T23:07:00Z
- **Tasks:** 2 of 3 (Task 3 is human-verify checkpoint)
- **Files modified:** 11

## Accomplishments
- FlowCanvas wraps React Flow v12 with dark colorMode, dot grid background, pan/zoom; handles sidebar drag-drop via `screenToFlowPosition`
- MismatchEdge renders dashed orange straight lines for type-mismatched connections; isValidConnection blocks Full Result to non-accepting inputs with toast
- CubeCatalog sidebar: fetches catalog on mount, groups by category, search filter, drag handles only, collapses to 48px icon strip
- Toolbar renders editable workflow name input, outline Save button, accent Run button (Phase 5 placeholders), Dashboard link
- App.tsx wires sidebar + canvas + toolbar with `ReactFlowProvider` wrapping canvas and `Toaster` from sonner

## Task Commits

Each task was committed atomically:

1. **Task 1: Create FlowCanvas with connection validation and MismatchEdge** - `0828bf4` (feat)
2. **Task 2: Create CubeCatalog sidebar, Toolbar, and wire App shell** - `7c7d47e` (feat)

**Plan metadata:** (pending — after human verify checkpoint)

## Files Created/Modified
- `frontend/src/components/Canvas/FlowCanvas.tsx` - React Flow wrapper with drop handling and connection validation
- `frontend/src/components/Canvas/FlowCanvas.css` - Full-size canvas container styles
- `frontend/src/components/Canvas/MismatchEdge.tsx` - Custom dashed orange edge for type mismatches
- `frontend/src/components/Sidebar/CubeCatalog.tsx` - Collapsible grouped catalog with drag and search
- `frontend/src/components/Sidebar/CubeCatalog.css` - Sidebar layout, card, handle, icon strip styles
- `frontend/src/components/Toolbar/Toolbar.tsx` - Toolbar with Run, Save, name input, Dashboard link
- `frontend/src/components/Toolbar/Toolbar.css` - Toolbar layout and button styles
- `frontend/src/App.tsx` - Root shell wiring all components with ReactFlowProvider and Toaster
- `frontend/src/App.css` - Full-viewport column layout with flex body
- `frontend/src/types/cube.ts` - (auto-fix) Converted enums to const+type alias
- `frontend/src/api/client.ts` - (auto-fix) ApiError constructor shorthand converted

## Decisions Made
- Full Result rejection blocks connection entirely (return false) and shows error toast
- Type mismatches allowed: visually distinguished with dashed orange MismatchEdge
- Sidebar drag handle (`:::` grip) initiates drag only — not the full cube card
- Run/Save are Phase 5 placeholders, no disabled state (will be wired in Phase 5)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed isValidConnection TypeScript signature mismatch**
- **Found during:** Task 2 (production build verification)
- **Issue:** `isValidConnection` typed as `(connection: Connection) => boolean` but React Flow v12 `IsValidConnection<Edge>` expects `(edge: Edge | Connection) => boolean` — build failed
- **Fix:** Imported `IsValidConnection` type from `@xyflow/react`, typed callback with `useCallback<IsValidConnection<Edge>>(...)`
- **Files modified:** `frontend/src/components/Canvas/FlowCanvas.tsx`
- **Verification:** `pnpm build` passes clean
- **Committed in:** `7c7d47e` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed erasableSyntaxOnly TypeScript violations in cube.ts**
- **Found during:** Task 2 (production build verification)
- **Issue:** TypeScript `enum` declarations violate `erasableSyntaxOnly: true` in tsconfig.app.json — tsc -b fails
- **Fix:** Converted `ParamType` and `CubeCategory` enums to `const` objects with `type` alias (`as const` + `(typeof X)[keyof typeof X]` pattern)
- **Files modified:** `frontend/src/types/cube.ts`
- **Verification:** `pnpm build` passes clean
- **Committed in:** `7c7d47e` (Task 2 commit)

**3. [Rule 1 - Bug] Fixed erasableSyntaxOnly violation in ApiError constructor**
- **Found during:** Task 2 (production build verification)
- **Issue:** `constructor(public status: number, ...)` shorthand violates `erasableSyntaxOnly: true` — tsc -b fails
- **Fix:** Moved `status` to an explicit class property `status: number` with assignment in constructor body
- **Files modified:** `frontend/src/api/client.ts`
- **Verification:** `pnpm build` passes clean
- **Committed in:** `7c7d47e` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 - Bug)
**Impact on plan:** All fixes required for production build correctness. The `erasableSyntaxOnly` violations were pre-existing from Plans 01-02 but only surfaced during `pnpm build` (not `npx tsc --noEmit`). No scope creep.

## Issues Encountered
- `npx tsc --noEmit` uses `noEmit: true` in tsconfig, which skips the strict `tsc -b` mode — the `erasableSyntaxOnly` and type compatibility errors only appeared during `pnpm build`. Fixed inline per deviation rules.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Complete visual editor shell ready: canvas, sidebar, toolbar, all wired together
- Human verification (Task 3 checkpoint) required before proceeding to Phase 5
- Phase 5 will wire: workflow save/load CRUD, Run button execution, SSE progress, dashboard route
- To start servers: `cd frontend && pnpm dev` (port 5173) + `cd backend && uv run uvicorn app.main:app --reload` (port 8000)

## Self-Check: PASSED

---
*Phase: 04-frontend-canvas-nodes-sidebar-dark-theme*
*Completed: 2026-03-03*
