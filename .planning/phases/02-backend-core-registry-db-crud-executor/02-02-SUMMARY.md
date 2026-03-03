---
phase: 02-backend-core-registry-db-crud-executor
plan: "02"
subsystem: api
tags: [fastapi, sqlalchemy, asyncpg, pytest, pytest-asyncio, topological-sort, workflow-execution]

# Dependency graph
requires:
  - phase: 02-backend-core-registry-db-crud-executor plan 01
    provides: CubeRegistry, BaseCube, Workflow ORM model, CRUD endpoints, echo/add_numbers cubes

provides:
  - WorkflowExecutor engine with topological sort (Kahn's algorithm) and cycle detection
  - resolve_inputs: connection values override manual params; __full_result__ bundles all outputs
  - apply_row_limit: caps list outputs at 100 rows, returns truncated flag
  - execute_graph: async orchestrator with failure isolation and skip propagation
  - POST /api/workflows/{id}/run endpoint returning per-node results dict
  - AllFlights production cube querying research.flight_metadata with all filters
  - Python ray-casting point_in_polygon for geofence filtering (no PostGIS)

affects: [phase-03-sse, phase-07-real-db-cubes, frontend-execution-integration]

# Tech tracking
tech-stack:
  added: [pytest>=9.0.2, pytest-asyncio>=1.3.0]
  patterns:
    - Kahn's topological sort for DAG execution ordering
    - Connection override pattern (manual params merged, connections win)
    - Full Result bundling via __full_result__ sourceHandle sentinel
    - Row limiting with truncation flag on any list output
    - Failure isolation: failed/skipped set, independent branches continue
    - Mock registry pattern for executor unit tests using unittest.mock.patch

key-files:
  created:
    - backend/app/engine/executor.py
    - backend/app/cubes/all_flights.py
    - backend/tests/__init__.py
    - backend/tests/test_executor.py
  modified:
    - backend/app/routers/workflows.py
    - backend/pyproject.toml

key-decisions:
  - "pytest-asyncio asyncio_mode=auto set in pyproject.toml [tool.pytest.ini_options] to avoid per-test @pytest.mark.asyncio decorator"
  - "execute_graph uses patch('app.engine.executor.registry') mock pattern in tests — no test-specific registry, just mock the module-level singleton"
  - "AllFlights uses engine.connect() directly (not FastAPI DB dependency) to keep BaseCube.execute(**inputs) signature clean"
  - "SQL uses SQLAlchemy text() with :param style bindings for parameterized queries against asyncpg"
  - "polygon filter queries research.normal_tracks separately then ray-casts in Python — PostGIS not on Tracer 42 RDS"

patterns-established:
  - "Cube DB access pattern: async with engine.connect() as conn: — cubes own their DB connections, not injected"
  - "Executor isolation: failed_or_skipped set tracks bad nodes; upstream check before each execution"
  - "Results dict shape: {node_id: {status, outputs, truncated}} for done; {status, message, outputs} for error; {status, reason, outputs} for skipped"

requirements-completed: [BACK-08, BACK-09, BACK-10, BACK-11, BACK-12]

# Metrics
duration: 6min
completed: 2026-03-03
---

# Phase 02 Plan 02: WorkflowExecutor + Run Endpoint + AllFlights Cube Summary

**WorkflowExecutor engine with Kahn's topological sort, Full Result bundling, row limiting, and failure isolation, plus POST /run endpoint and AllFlights cube querying Tracer 42 flight_metadata**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-03T20:43:00Z
- **Completed:** 2026-03-03T20:48:47Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- WorkflowExecutor engine: topological sort (Kahn's), cycle detection (ValueError->400), input resolution with connection override, Full Result (__full_result__ sentinel), row limiting (100 rows, truncated flag), and failure isolation with skip propagation
- POST /api/workflows/{id}/run endpoint integrated into existing CRUD router; 400 on cycle, 404 on missing, 500 on unexpected errors
- AllFlights production cube with 8 optional inputs (time range, absolute time, flight_ids, callsign, altitude range, polygon) and Python ray-casting geofence filter
- 11 pytest-asyncio tests all passing, TDD approach (RED then GREEN)

## Task Commits

Each task was committed atomically:

1. **Task 1: WorkflowExecutor with topological sort, input resolution, Full Result, row limiting, failure isolation** - `b2f3dfa` (feat)
2. **Task 2: Run endpoint and AllFlights production cube** - `21da6e8` (feat)

**Plan metadata:** TBD (docs: complete plan)

_Note: Task 1 was TDD — tests written first (RED), then implementation (GREEN). All 11 tests pass._

## Files Created/Modified

- `backend/app/engine/executor.py` - WorkflowExecutor: topological_sort, resolve_inputs, apply_row_limit, execute_graph
- `backend/app/cubes/all_flights.py` - AllFlights cube: flight_metadata query + polygon ray-casting
- `backend/tests/__init__.py` - Empty package marker for test discovery
- `backend/tests/test_executor.py` - 11 pytest-asyncio tests covering all executor functions
- `backend/app/routers/workflows.py` - Added POST /{workflow_id}/run endpoint
- `backend/pyproject.toml` - Added pytest, pytest-asyncio dev deps; asyncio_mode=auto config

## Decisions Made

- pytest-asyncio asyncio_mode=auto set globally so tests don't need per-test decorator
- Mock registry pattern: `patch("app.engine.executor.registry")` in tests avoids test-only registration side effects
- AllFlights cube creates its own DB connection (`async with engine.connect()`) to keep BaseCube.execute(**inputs) signature clean — no FastAPI DI injection into cubes
- SQL uses SQLAlchemy `text()` with `:param` style bindings for asyncpg parameterization
- Polygon geofence filter queries `research.normal_tracks` and applies Python ray-casting because PostGIS is not available on the Tracer 42 RDS instance

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all components worked as designed on first implementation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Backend execution runtime is complete. Any workflow graph can now be submitted, topologically sorted, and executed with proper input resolution, row limiting, and failure isolation.
- Phase 3 (SSE progress streaming) can build directly on execute_graph — just needs to wrap it with event emission between node executions.
- AllFlights cube ready for real-data testing once database connection is active (requires .env DATABASE_URL).

## Self-Check: PASSED

All files exist on disk. All commits verified in git log.

---
*Phase: 02-backend-core-registry-db-crud-executor*
*Completed: 2026-03-03*
