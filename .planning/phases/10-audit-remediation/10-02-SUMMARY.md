---
phase: 10-audit-remediation
plan: 02
subsystem: api
tags: [fastapi, react, typescript, cleanup, tech-debt]

# Dependency graph
requires:
  - phase: 08-geo-temporal-playback
    provides: result_row_limit raised from 100 to 10000

provides:
  - Correct 10,000-row truncation warning in ResultsTable UI
  - Corrected apply_row_limit docstring in executor.py
  - Removed dead POST /{workflow_id}/run sync endpoint from workflows router

affects: [api, frontend-results, backend-executor]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - frontend/src/components/Results/ResultsTable.tsx
    - backend/app/engine/executor.py
    - backend/app/routers/workflows.py

key-decisions:
  - "POST /{workflow_id}/run (sync endpoint) removed — frontend uses only GET /{workflow_id}/run/stream for execution; confirmed no frontend or test references to sync endpoint before deletion"
  - "GET /{workflow_id}/run/stream preserved — SSE stream endpoint is the live execution path"
  - "execute_graph import removed from workflows.py — only caller was run_workflow which was deleted"

patterns-established: []

requirements-completed: [BACK-08, BACK-11, GEO-02]

# Metrics
duration: 8min
completed: 2026-03-05
---

# Phase 10 Plan 02: Stale Row Limit References and Dead Endpoint Removal Summary

**Fixed stale 100-row display strings to 10,000 in ResultsTable and executor.py, and removed dead synchronous POST /{workflow_id}/run endpoint from the workflows router.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-05T14:35:00Z
- **Completed:** 2026-03-05T14:43:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- ResultsTable truncation warning now correctly says "Showing first 10,000 rows" (was "100 rows")
- executor.py `apply_row_limit` docstring now references the actual limit of 10,000 (was 100)
- Dead synchronous `run_workflow` POST handler removed from workflows router — 28 lines of dead code eliminated
- Unused `execute_graph` and `Any` imports cleaned from workflows.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix stale row limit references in frontend and backend** - `9ddaea3` (fix)
2. **Task 2: Remove dead POST /{workflow_id}/run endpoint** - `63ea75d` (fix)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `frontend/src/components/Results/ResultsTable.tsx` - Truncation warning text updated to 10,000 rows
- `backend/app/engine/executor.py` - apply_row_limit docstring updated to reference 10,000
- `backend/app/routers/workflows.py` - Removed run_workflow handler, execute_graph import, and Any import

## Decisions Made

- Confirmed no frontend or backend test references to `POST /{workflow_id}/run` before deletion — safe to remove
- Preserved `GET /{workflow_id}/run/stream` (stream_workflow) — this is the live execution path used by both tests and frontend
- Pre-existing test failure `test_stream_graph_row_limiting` (expects truncation at 200 rows but limit is 10,000) is out of scope for this plan — logged as known issue

## Deviations from Plan

None - plan executed exactly as written. The plan's pre-checks (grep for frontend/test references) were performed and confirmed zero usages before deletion.

## Issues Encountered

During Task 2 execution, initial read of `workflows.py` showed a modified working-tree version (which already had a `POST /run/stream` direct-graph endpoint replacing the `GET /{workflow_id}/run/stream`). The stash revealed the committed file had both the sync endpoint AND the SSE stream endpoint. Applied the correct edit to the committed base: removed only `run_workflow` (POST sync), preserved `stream_workflow` (GET SSE). Tests confirm correct behavior after edit.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All v1.0 audit items for BACK-08, BACK-11, and GEO-02 are resolved
- Backend starts cleanly with no dead endpoints or stale doc strings
- Pre-existing test failure `test_stream_graph_row_limiting` should be addressed in a follow-up plan (test expects old 200-row threshold, actual limit is 10,000)

---
*Phase: 10-audit-remediation*
*Completed: 2026-03-05*

## Self-Check: PASSED

- FOUND: `.planning/phases/10-audit-remediation/10-02-SUMMARY.md`
- FOUND: `frontend/src/components/Results/ResultsTable.tsx`
- FOUND: `backend/app/engine/executor.py`
- FOUND: `backend/app/routers/workflows.py`
- FOUND: commit `9ddaea3` (Task 1)
- FOUND: commit `63ea75d` (Task 2)
