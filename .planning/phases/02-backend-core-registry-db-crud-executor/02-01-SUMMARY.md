---
phase: 02-backend-core-registry-db-crud-executor
plan: "01"
subsystem: api

tags: [fastapi, sqlalchemy, alembic, postgresql, jsonb, asyncpg, pydantic]

requires:
  - phase: 01-types-schemas-project-scaffolding
    provides: BaseCube abstract class, ParamType/CubeCategory/CubeDefinition schemas, WorkflowGraph/WorkflowCreate/WorkflowUpdate/WorkflowResponse schemas, SQLAlchemy async engine and Base, FastAPI app scaffold

provides:
  - CubeRegistry singleton with pkgutil-based auto-discovery (backend/app/engine/registry.py)
  - EchoCube stub (backend/app/cubes/echo_cube.py)
  - AddNumbersCube stub (backend/app/cubes/add_numbers.py)
  - Workflow SQLAlchemy ORM model with UUID pk and JSONB graph_json (backend/app/models/workflow.py)
  - Alembic migration configuration (alembic.ini, alembic/env.py, alembic/script.py.mako)
  - Alembic migration 001 that creates workflows table (backend/alembic/versions/001_create_workflows.py)
  - GET /api/cubes/catalog endpoint returning all cube definitions with __full_result__ outputs
  - Full workflow CRUD: POST/GET/PUT/DELETE /api/workflows[/{id}]

affects:
  - 02-02 (executor plan — uses registry and Workflow model)
  - 03-async-execution-sse (uses workflow CRUD and registry)
  - 04-frontend (consumes catalog and CRUD APIs)

tech-stack:
  added: [alembic, asyncpg (via DATABASE_URL), sqlalchemy JSONB dialect]
  patterns:
    - pkgutil.iter_modules for zero-registration cube auto-discovery
    - async Alembic env.py using async_engine_from_config + NullPool
    - WorkflowGraph JSONB serialized via model_dump() on write, model_validate() on read
    - FastAPI router prefix with empty-string route paths (not "/") to avoid redirect-on-trailing-slash

key-files:
  created:
    - backend/app/engine/registry.py
    - backend/app/cubes/echo_cube.py
    - backend/app/cubes/add_numbers.py
    - backend/app/models/workflow.py
    - backend/alembic.ini
    - backend/alembic/env.py
    - backend/alembic/script.py.mako
    - backend/alembic/versions/001_create_workflows.py
    - backend/app/routers/cubes.py
    - backend/app/routers/workflows.py
  modified:
    - backend/app/main.py

key-decisions:
  - "Route paths use empty string '' not '/' to avoid FastAPI 307 redirect on missing trailing slash"
  - "graph_json round-trips via model_dump() + WorkflowGraph.model_validate() for correct Pydantic v2 handling of JSONB dict"
  - "Alembic migration created manually (not autogenerate) to avoid asyncpg reflection issues"
  - "Registry uses BaseCube.__subclasses__() after pkgutil import, not manual registration"

patterns-established:
  - "Cube registration pattern: create class in backend/app/cubes/, auto-discovered on next import"
  - "Workflow CRUD pattern: _to_response() helper reconstructs WorkflowGraph from JSONB dict"

requirements-completed: [BACK-03, BACK-04, BACK-05, BACK-06, BACK-07]

duration: 2min
completed: 2026-03-03
---

# Phase 02 Plan 01: Backend Core Registry, DB, CRUD, Executor Summary

**pkgutil-based CubeRegistry auto-discovery, EchoCube + AddNumbersCube stubs, Workflow SQLAlchemy ORM with Alembic migration, and full REST CRUD for /api/cubes/catalog and /api/workflows**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-03T19:59:52Z
- **Completed:** 2026-03-03T20:01:52Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- CubeRegistry singleton auto-discovers BaseCube subclasses from the cubes package using pkgutil.iter_modules without any manual registration
- Workflow ORM model with UUID primary key and JSONB graph_json field backed by Alembic async migration applied to the database
- Full REST CRUD (create, list, get, update, delete) for workflows with correct Pydantic v2 JSONB round-trip handling
- GET /api/cubes/catalog returns all registered cubes with auto-appended __full_result__ outputs verified end-to-end via ASGI test client

## Task Commits

Each task was committed atomically:

1. **Task 1: CubeRegistry, stub cubes, Workflow ORM, Alembic migration** - `bbffcba` (feat)
2. **Task 2: Catalog endpoint, workflow CRUD router, main.py wiring** - `12757fd` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `backend/app/engine/registry.py` - CubeRegistry singleton with pkgutil auto-discovery
- `backend/app/cubes/echo_cube.py` - EchoCube: echoes string input back as output
- `backend/app/cubes/add_numbers.py` - AddNumbersCube: adds two numbers, returns sum
- `backend/app/models/workflow.py` - Workflow SQLAlchemy 2.0 ORM model (UUID pk, JSONB graph_json, timestamps)
- `backend/alembic.ini` - Alembic configuration with async URL override
- `backend/alembic/env.py` - Async Alembic env with async_engine_from_config + NullPool
- `backend/alembic/script.py.mako` - Standard Mako template for generated migrations
- `backend/alembic/versions/001_create_workflows.py` - Manual migration creates workflows table
- `backend/app/routers/cubes.py` - GET /api/cubes/catalog endpoint
- `backend/app/routers/workflows.py` - Full CRUD router for /api/workflows
- `backend/app/main.py` - Added include_router calls for cubes and workflows routers

## Decisions Made

- Route paths use empty string `""` not `"/"` in FastAPI routers to avoid 307 redirect when callers omit trailing slash
- graph_json JSONB field round-trips via `body.graph_json.model_dump()` on write and `WorkflowGraph.model_validate(wf.graph_json)` on read — required because `from_attributes=True` alone does not handle the dict-to-model coercion for JSONB
- Alembic migration written manually rather than via autogenerate to avoid asyncpg reflection complexity at migration time
- Registry uses `BaseCube.__subclasses__()` after pkgutil import to collect all discovered subclasses without maintaining a manual registry list

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed 307 redirect on workflow POST endpoint**
- **Found during:** Task 2 verification
- **Issue:** POST /api/workflows returned 307 redirect because route was registered as `"/"` under prefix `/api/workflows`, causing redirect to `/api/workflows/` when caller omitted trailing slash
- **Fix:** Changed POST and GET list route paths from `"/"` to `""` so the router matches `/api/workflows` without redirect
- **Files modified:** backend/app/routers/workflows.py
- **Verification:** Full CRUD test cycle passed including create returning 200
- **Committed in:** 12757fd (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Essential fix for correct HTTP behavior. No scope creep.

## Issues Encountered

None — redirect fix was straightforward and caught immediately by verification.

## User Setup Required

None - no external service configuration required. The workflows table was created automatically by the Alembic migration which ran against the existing DATABASE_URL from .env.

## Next Phase Readiness

- CubeRegistry and stub cubes ready for executor (Plan 02-02)
- Workflow CRUD API complete and tested end-to-end
- Alembic migration infrastructure in place for future schema changes
- No blockers for Plan 02-02 (WorkflowExecutor with topological sort + SSE)

---
*Phase: 02-backend-core-registry-db-crud-executor*
*Completed: 2026-03-03*
