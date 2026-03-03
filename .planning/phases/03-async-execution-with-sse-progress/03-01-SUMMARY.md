---
phase: 03-async-execution-with-sse-progress
plan: 01
subsystem: api
tags: [sse, streaming, fastapi, pydantic, sse-starlette, httpx-sse, async-generator]

# Dependency graph
requires:
  - phase: 02-backend-core
    provides: execute_graph, topological_sort, resolve_inputs, apply_row_limit, WorkflowGraph, Workflow ORM
provides:
  - CubeStatusEvent Pydantic model with 5 status variants (pending/running/done/error/skipped)
  - stream_graph async generator yielding real-time per-cube events
  - GET /api/workflows/{id}/run/stream SSE endpoint via EventSourceResponse
  - execute_graph refactored to delegate to stream_graph (no code duplication)
affects: [05-workflow-management, phase-5-frontend-execution-integration]

# Tech tracking
tech-stack:
  added: [httpx-sse (dev), sse-starlette (already in deps - now used)]
  patterns: [SSE-via-async-generator, TDD-red-green, stream-then-collect pattern for backward compat]

key-files:
  created:
    - backend/app/schemas/execution.py
    - backend/tests/test_stream_graph.py
    - backend/tests/test_sse_stream.py
  modified:
    - backend/app/engine/executor.py
    - backend/app/routers/workflows.py
    - backend/pyproject.toml

key-decisions:
  - "stream_graph assumes pre-validated graph (no cycles) — callers validate first and raise HTTPException before streaming"
  - "execute_graph delegates to stream_graph internally to eliminate duplication between sync and streaming paths"
  - "Cycle validation for SSE happens before EventSourceResponse is returned — preserves HTTP 400 error semantics"
  - "request parameter is Optional[Request] in stream_graph — None when called from execute_graph or tests without HTTP context"
  - "ServerSentEvent used instead of JSONServerSentEvent — data serialized via model_dump_json(exclude_none=True)"
  - "asyncio.CancelledError re-raised in stream_graph generator per sse-starlette requirement for clean teardown"

patterns-established:
  - "SSE-via-async-generator: inner event_publisher() async generator wraps stream_graph and yields ServerSentEvent objects"
  - "Stream-then-collect: stream_graph yields events; execute_graph collects only done/error/skipped events into result dict"
  - "Pre-SSE validation: topological_sort called before EventSourceResponse to allow returning HTTP errors"

requirements-completed: [BACK-13]

# Metrics
duration: 3min
completed: 2026-03-03
---

# Phase 03 Plan 01: SSE Streaming Execution Summary

**Real-time per-cube SSE streaming via stream_graph async generator and GET /api/workflows/{id}/run/stream endpoint using sse-starlette EventSourceResponse**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-03T21:13:22Z
- **Completed:** 2026-03-03T21:16:32Z
- **Tasks:** 2
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- CubeStatusEvent Pydantic model with 5 status literals enables typed SSE payloads
- stream_graph async generator emits pending events for all nodes before execution begins, then running/done/error/skipped per node in topological order, with client-disconnect detection
- execute_graph refactored to collect events from stream_graph — single implementation for both sync and streaming paths
- GET /api/workflows/{id}/run/stream SSE endpoint validates graph before streaming (returns HTTP 400 on cycles, 404 on missing workflow), streams cube_status events with 15s ping and no-buffering header
- 23 tests total (7 stream_graph unit tests + 5 SSE integration tests + 11 existing executor tests) all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: CubeStatusEvent schema + stream_graph async generator** - `fa4d294` (feat)
2. **Task 2: SSE route handler + integration tests** - `c523d3c` (feat)

**Plan metadata:** (docs commit — see below)

_Note: TDD tasks each followed RED (failing test) then GREEN (implementation) flow_

## Files Created/Modified

- `backend/app/schemas/execution.py` - CubeStatusEvent Pydantic model with 5 status literals
- `backend/app/engine/executor.py` - Added stream_graph async generator; refactored execute_graph to delegate to it
- `backend/app/routers/workflows.py` - Added GET /{workflow_id}/run/stream SSE endpoint with EventSourceResponse
- `backend/tests/test_stream_graph.py` - 7 unit tests for stream_graph covering all status transitions
- `backend/tests/test_sse_stream.py` - 5 integration tests for SSE endpoint
- `backend/pyproject.toml` - Added httpx-sse to dev dependencies

## Decisions Made

- stream_graph assumes graph is pre-validated (no cycle check inside generator) — callers do topological_sort before invoking stream_graph and raise HTTPException. This keeps the generator clean and allows HTTP error codes.
- execute_graph delegates to stream_graph to eliminate code duplication between sync and streaming execution paths.
- The SSE route uses pre-stream validation pattern: topological_sort is called before EventSourceResponse is returned so HTTP 400 can still be sent if a cycle is detected.
- request parameter is Optional in stream_graph so it can be called without an HTTP context from execute_graph and tests.
- ServerSentEvent (not JSONServerSentEvent) used with model_dump_json(exclude_none=True) for clean JSON serialization.
- asyncio.CancelledError is re-raised in stream_graph per sse-starlette documentation requirement.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SSE streaming endpoint is complete and tested — ready for Phase 5 frontend to consume cube_status events for live node status indicators
- POST /api/workflows/{id}/run continues to work unchanged (backward compatible)
- stream_graph generator is fully decoupled from HTTP concerns and can be composed in future use cases

## Self-Check: PASSED

All files created and commits verified:
- FOUND: backend/app/schemas/execution.py
- FOUND: backend/app/engine/executor.py
- FOUND: backend/app/routers/workflows.py
- FOUND: backend/tests/test_stream_graph.py
- FOUND: backend/tests/test_sse_stream.py
- FOUND: .planning/phases/03-async-execution-with-sse-progress/03-01-SUMMARY.md
- FOUND commit: fa4d294 (Task 1)
- FOUND commit: c523d3c (Task 2)

---
*Phase: 03-async-execution-with-sse-progress*
*Completed: 2026-03-03*
