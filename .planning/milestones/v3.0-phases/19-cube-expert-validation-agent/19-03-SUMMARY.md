---
phase: 19-cube-expert-validation-agent
plan: 03
subsystem: frontend/validation
tags: [validation, react, zustand, issues-panel, node-highlighting]
dependency_graph:
  requires: [19-01]
  provides: [IssuesPanel, validateWorkflow, validationIssues state, highlightedNodeId state]
  affects: [frontend/src/components/Toolbar/Toolbar.tsx, frontend/src/pages/EditorPage.tsx, frontend/src/components/CubeNode/CubeNode.tsx]
tech_stack:
  added: []
  patterns: [pre-run validation hook, collapsible issues panel, click-to-highlight node, Zustand state extension]
key_files:
  created:
    - frontend/src/api/agent.ts
    - frontend/src/components/Validation/IssuesPanel.tsx
    - frontend/src/components/Validation/IssuesPanel.css
  modified:
    - frontend/src/store/flowStore.ts
    - frontend/src/components/Toolbar/Toolbar.tsx
    - frontend/src/pages/EditorPage.tsx
    - frontend/src/components/CubeNode/CubeNode.tsx
    - frontend/src/components/CubeNode/CubeNode.css
decisions:
  - IssuesPanel must be inside ReactFlowProvider in EditorPage DOM tree to use useReactFlow() fitView hook — placed between FlowCanvas and closing provider tag
  - handleRun uses finally block for setIsValidating(false) so button always re-enables even on network error; execution proceeds on validation failure (graceful degradation)
  - isExpanded state syncs with hasErrors on each panel open — errors auto-expand, warnings start collapsed per UI-SPEC
metrics:
  duration: ~20 minutes
  completed: "2026-03-24"
  tasks_completed: 2
  files_changed: 8
  tests_added: 0
---

# Phase 19 Plan 03: Frontend Validation Integration Summary

IssuesPanel component with collapsible header and clickable issue rows, pre-run validation hook in Toolbar blocking execution on errors, node highlighting via Zustand highlightedNodeId + fitView, and Zustand store extended with 4 validation state fields.

## What Was Built

### frontend/src/api/agent.ts (new)

`validateWorkflow(graph) -> Promise<ValidationResponse>` — calls `POST /api/agent/validate` via `apiFetch`. Exports `ValidationIssue` and `ValidationResponse` interfaces matching the backend Pydantic schemas from plan 19-01.

### frontend/src/store/flowStore.ts (modified)

Four new state fields added to `FlowState` interface and `create()` initializer:
- `validationIssues: ValidationIssue[]` — current issues from last validation run
- `showIssuesPanel: boolean` — controls panel render
- `highlightedNodeId: string | null` — node to highlight on canvas
- `isValidating: boolean` — disables Run button during API call

Four corresponding setters: `setValidationIssues`, `setShowIssuesPanel`, `setHighlightedNodeId`, `setIsValidating`.

### frontend/src/components/Validation/IssuesPanel.tsx (new)

Collapsible panel component that:
- Renders only when `showIssuesPanel` is true
- Header: "ISSUES" heading (11px/600/uppercase), error count in `--color-error`, warning count in `--color-warning`, collapse toggle button (28px touch target)
- Auto-expands when errors present (blocks execution), starts collapsed for warnings-only
- Issue rows: 2px left border by severity, `●` icon, cube name + param name in 11px monospace, message in 12px DM Sans
- Click row: calls `setHighlightedNodeId(issue.node_id)` + `fitView({ nodes: [{ id }], padding: 0.3, duration: 300 })`

### frontend/src/components/Validation/IssuesPanel.css (new)

Follows 19-UI-SPEC tokens exactly: `--color-surface`, `--color-surface-raised`, `--color-error`, `--color-warning`, `--color-text-muted`, `--color-text-dim`, `--color-text-secondary`, `--color-surface-hover`, `--font-mono`.

### frontend/src/components/Toolbar/Toolbar.tsx (modified)

`handleRun` now:
1. Guards on `isRunning || isValidating`
2. Calls `validateWorkflow(graph)` with `setIsValidating(true/false)` in try/finally
3. Errors → `setValidationIssues(issues)` + `setShowIssuesPanel(true)` + early return (blocks `startStream`)
4. Warnings-only → show panel, then `startStream` proceeds
5. Clean pass → `setShowIssuesPanel(false)`, silent `startStream`
6. Network error → logs, proceeds with execution (graceful degradation)

Run button: `disabled={isLoadingWorkflow || isValidating}`, label `{isValidating ? 'Validating...' : 'Run'}`.

### frontend/src/pages/EditorPage.tsx (modified)

Imports `IssuesPanel`, places it inside `<ReactFlowProvider>` after `<FlowCanvas />` so `useReactFlow()` hook is available within the panel.

### frontend/src/components/CubeNode/CubeNode.tsx + CubeNode.css (modified)

CubeNode reads `highlightedNodeId` from store, applies `cube-node--highlighted` class when `highlightedNodeId === id`. CSS adds `box-shadow: var(--shadow-node-selected)` and `z-index: 10`.

## Task Commits

| Task | Description | Commit |
|------|-------------|--------|
| Task 1 | API client, Zustand state, IssuesPanel component + CSS | a1f76bb |
| Task 2 | Toolbar wiring, EditorPage layout, CubeNode highlighting | ced3d83 |

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria satisfied.

## Known Stubs

None. The IssuesPanel is fully wired to live Zustand state and the validation API. No mock data or placeholder values.

## Checkpoint Status: APPROVED

Task 3 (human-verify) approved by user — all 4 test scenarios passed in browser:
- Test A: Missing required param blocks execution with issues panel — PASS
- Test B: Clean validation is silent pass-through — PASS
- Test C: Click-to-highlight scrolls canvas to offending node — PASS
- Test D: Orphan node warning does not block execution — PASS

## Self-Check: PASSED

- `frontend/src/api/agent.ts` — exists, contains `validateWorkflow`, `ValidationIssue`, `/agent/validate`
- `frontend/src/store/flowStore.ts` — contains `validationIssues`, `showIssuesPanel`, `highlightedNodeId`, `isValidating`
- `frontend/src/components/Validation/IssuesPanel.tsx` — contains `IssuesPanel`, `useReactFlow`, `fitView`, `setHighlightedNodeId`
- `frontend/src/components/Validation/IssuesPanel.css` — contains `.issues-panel`, `--color-error`, `--color-warning`
- `frontend/src/components/Toolbar/Toolbar.tsx` — contains `validateWorkflow`, `setIsValidating`, `setValidationIssues`, `setShowIssuesPanel`, `isValidating ? 'Validating...' : 'Run'`
- `frontend/src/pages/EditorPage.tsx` — contains `IssuesPanel`, `<IssuesPanel />`
- `frontend/src/components/CubeNode/CubeNode.tsx` — contains `highlightedNodeId`, `cube-node--highlighted`
- `frontend/src/components/CubeNode/CubeNode.css` — contains `cube-node--highlighted`, `--shadow-node-selected`
- TypeScript: `npx tsc --noEmit` exits 0 (verified after both tasks)
- Commits a1f76bb, ced3d83 verified in git log
