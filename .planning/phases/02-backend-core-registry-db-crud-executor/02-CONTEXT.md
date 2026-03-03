# Phase 2: Backend Core — Registry, DB, CRUD, Executor - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Full backend API functional via curl/Postman. Includes: CubeRegistry with auto-discovery, SQLAlchemy Workflow model + Alembic migration, full workflow CRUD endpoints, WorkflowExecutor (topo sort, cycle detection, input resolution, Full Result, row limiting), and three cubes (two test stubs + one real database cube).

</domain>

<decisions>
## Implementation Decisions

### Execution response shape
- Per-cube results as array-of-objects (row-based table format)
- Each row is an object with the same keys, different values
- Response keyed by node_id with status + outputs per cube
- Example structure:
  ```json
  {
    "node-1": {
      "status": "done",
      "outputs": {
        "flights": [
          {"flight_id": "ABC123", "callsign": "ELY001", "altitude": 35000},
          {"flight_id": "DEF456", "callsign": "THY502", "altitude": 28000}
        ]
      },
      "truncated": false
    }
  }
  ```

### Failure behavior
- Independent branches continue executing when a cube fails
- Failed cube gets `"status": "error"` with error message
- Downstream dependents of the failed cube are skipped (marked as skipped with reason)
- All other cubes with satisfied dependencies still execute

### Cubes to build
- **echo_cube** — Test stub that echoes its input
- **add_numbers** — Test stub that adds two numbers
- **all_flights** — Real production cube querying `research.flight_metadata` (and joining `research.normal_tracks` for polygon/position-based filtering)

### All Flights cube parameters
- **Time filter:** Accepts relative time (last X hours/minutes/seconds) OR absolute time range (two datetimes)
- **Flight IDs:** Input param accepting list_of_strings — manual entry or from connection
- **Callsign:** String filter
- **Altitude range:** Min/max altitude range — filters flights where all points are between the specified altitudes
- **Polygon geofence:** Array of lat/lon coordinate pairs defining a boundary — filters flights that had positions within the polygon (queries `research.normal_tracks` for position data)

### Data sources
- `research.flight_metadata` — Primary table for flight metadata queries (time, callsign, flight IDs)
- `research.normal_tracks` — Flight track/position data, used for polygon geofence filtering and altitude filtering along the flight path

### Claude's Discretion
- CubeRegistry auto-discovery mechanism (importlib vs pkgutil vs __init__ registration)
- Alembic migration structure and naming
- Exact SQL query construction for the flights cube
- How polygon point-in-polygon check is implemented (PostGIS vs manual calculation)
- WorkflowExecutor internal architecture (dependency graph representation)
- Error message formatting
- How "skipped" status is communicated for dependents of failed cubes

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `schemas/cube.py`: Full type system (ParamType, CubeCategory, ParamDefinition, CubeDefinition) — registry and catalog endpoint consume these directly
- `schemas/workflow.py`: WorkflowGraph, WorkflowNode, WorkflowEdge + CRUD schemas (WorkflowCreate, WorkflowUpdate, WorkflowResponse) — router endpoints use these as-is
- `cubes/base.py`: BaseCube abstract class with `definition` property auto-appending `__full_result__` — all cubes subclass this
- `database.py`: Async engine, session factory, `get_db` dependency, `get_raw_connection` for direct SQL — executor and cubes use these
- `config.py`: `result_row_limit = 100` already configured — executor applies this cap

### Established Patterns
- Pydantic models for all data contracts (schemas/)
- Async SQLAlchemy with asyncpg for database access
- FastAPI dependency injection for sessions (`get_db`)
- `get_raw_connection` available for direct SQL queries (useful for cubes querying research schema)

### Integration Points
- `engine/registry.py` — New, discovers cubes from `cubes/` package, serves catalog endpoint
- `engine/executor.py` — New, consumes WorkflowGraph, uses registry to instantiate cubes
- `models/workflow.py` — New, SQLAlchemy model using `database.Base`
- `routers/cubes.py` — New, depends on registry
- `routers/workflows.py` — New, depends on models + executor
- `app/main.py` — Existing, needs router includes

</code_context>

<specifics>
## Specific Ideas

- Results should feel like database query results — rows with consistent columns, ready to render as a table
- The all_flights cube is a real production cube, not a placeholder — it should work against the live Tracer 42 database
- Altitude filter means "all points between altitudes" — filtering flights whose entire track stays within the range
- Polygon filter means "was sometime in that space" — flights that had any position report within the polygon boundary

</specifics>

<deferred>
## Deferred Ideas

- Polygon drawing/dragging UI on the canvas — frontend phase (Phase 4 or 6)
- Additional real data cubes (filter_flights, get_anomalies, count_by_field) — Phase 7

</deferred>

---

*Phase: 02-backend-core-registry-db-crud-executor*
*Context gathered: 2026-03-03*
