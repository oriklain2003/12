# Phase 7: Real DB Cubes, End-to-End & Docker - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Production cubes querying real Tracer 42 data, a polygon drawing widget for geofence input, end-to-end pipeline verification, and Docker containerization for deployment. Filter Flights cube dropped — AllFlights handles all filtering.

</domain>

<decisions>
## Implementation Decisions

### AllFlights cube enhancement
- No new Get Flights or Filter Flights cubes — enhance existing `AllFlightsCube` in `all_flights.py`
- DATA-01 and DATA-02 requirements merged into this single cube
- Add more filter options (airport, region, country) alongside existing filters (time, callsign, altitude, polygon, flight_ids)
- Cube accepts both absolute dates (two datetimes) and relative time (last N seconds) — execute method decides how to translate params to SQL
- Keep current output fields: flight_id, callsign, first_seen_ts, last_seen_ts, min/max_altitude_ft, origin/destination_airport, is_anomaly, is_military, start/end_lat/lon
- More output fields to be added in future phases

### Polygon map widget
- New frontend ParamField type for `widget_hint: "polygon"`
- Clicking the polygon param opens a map overlay
- User clicks on the map to place polygon points, forming a geofence boundary
- Polygon coordinates sent as JSON array of [lat, lon] pairs to the cube

### Get Anomalies cube
- New cube querying `research.anomaly_reports` for given flight_ids
- Accepts flight_ids array as input (connected from AllFlights output)
- Returns anomaly records with severity and report data

### Count By Field cube
- Pure Python using pandas DataFrame groupby on data received from upstream cube
- Accepts any data array and a `group_by_field` name
- Groups by the specified field and counts occurrences
- Output: array of `{value, count}` objects
- Example: group flights by origin_airport → [{value: "LLBG", count: 42}, {value: "LTFM", count: 23}]
- Handles any flat field — single group field

### Docker deployment
- No special preferences — make deployment-ready
- Backend Dockerfile: multi-stage with uv sync → slim Python runtime
- Frontend Dockerfile: multi-stage with pnpm build → nginx serving SPA
- docker-compose.yml: backend + frontend services, .env for config
- nginx proxies /api to backend

### Claude's Discretion
- Additional filter options to add to AllFlights (airport ILIKE, country, region bounding box)
- Get Anomalies output columns and filter options
- Polygon map widget UX details (close behavior, point editing, visual style)
- Docker health checks, port mapping, container naming
- nginx configuration details
- pandas vs manual Python for Count By Field (pandas preferred but Claude can adjust if dependency is unwanted)

</decisions>

<specifics>
## Specific Ideas

- Polygon filter UX: "click it and it opens a map, then click there to create a polygon" — interactive map drawing, not manual coordinate entry
- Count By Field should use pandas DataFrame for the groupby operation
- The cube execute method translates user-friendly params to SQL — user shouldn't think about query construction
- End-to-end pipeline: Get Flights (168h) → Get Anomalies → Count By Field should work with real data

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `all_flights.py`: AllFlightsCube with time/flight_ids/callsign/altitude/polygon filters and `point_in_polygon` ray-casting — extend this directly
- `base.py`: BaseCube abstract class with auto `__full_result__` output — new cubes subclass this
- `engine/executor.py`: WorkflowExecutor with topo sort, input resolution, row limiting — no changes needed
- `engine/registry.py`: Auto-discovery via `__subclasses__()` — new cube files auto-register
- `database.py`: `engine.connect()` pattern used by AllFlightsCube — reuse for Get Anomalies
- `ParamField.tsx`: Existing param editor with widget_hint support (datetime, relative_time) — extend for polygon
- `schemas/cube.py`: ParamType enum and ParamDefinition with widget_hint field — polygon widget uses this

### Established Patterns
- Cubes use `engine.connect()` directly, not FastAPI DI (Phase 2 decision)
- Widget hints on ParamDefinition drive frontend param editors (datetime → DateTimeInput, relative_time → RelativeTimeInput)
- Results as array-of-objects (row-based table format)
- Parameterized SQL with `text()` and dict params

### Integration Points
- New cube files in `backend/app/cubes/` auto-discovered by registry
- New ParamField widget type in `frontend/src/components/CubeNode/ParamField.tsx`
- Polygon map component as new file in CubeNode or shared components
- Docker files at project root (`docker-compose.yml`) and per-service (`backend/Dockerfile`, `frontend/Dockerfile`)

</code_context>

<deferred>
## Deferred Ideas

- Polygon drawing/editing UI improvements (vertex dragging, shape presets) — future enhancement
- Additional AllFlights output fields — user will specify in future phases
- Multiple group-by fields for Count By Field — future enhancement

</deferred>

---

*Phase: 07-real-db-cubes-end-to-end-docker*
*Context gathered: 2026-03-04*
