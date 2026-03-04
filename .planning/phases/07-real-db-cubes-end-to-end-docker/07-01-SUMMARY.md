---
phase: 07-real-db-cubes-end-to-end-docker
plan: 01
subsystem: database
tags: [fastapi, sqlalchemy, pandas, postgresql, cubes, data-source, aggregation]

# Dependency graph
requires:
  - phase: 02-backend-core
    provides: BaseCube, CubeRegistry, engine (SQLAlchemy async), AllFlights base cube
  - phase: 03-async-execution-with-sse-progress
    provides: WorkflowExecutor pipeline
provides:
  - AllFlights cube with airport ILIKE filter, bounding-box region filter, and airline/airline_code columns
  - GetAnomalies cube querying research.anomaly_reports by flight_ids with optional min_severity
  - CountByField aggregation cube using pandas groupby, handles array and full_result dict input
  - pandas dependency in pyproject.toml
affects:
  - 07-02 (Docker + end-to-end test uses these cubes)
  - frontend UI (catalog shows new cube params and widgets)

# Tech tracking
tech-stack:
  added: [pandas==3.0.1, numpy==2.4.2]
  patterns:
    - AllFlights uses engine.connect() directly (not FastAPI DI) to keep BaseCube.execute(**inputs) signature clean
    - GetAnomalies guards empty flight_ids to avoid PostgreSQL ANY() error
    - CountByField extracts first list value from full_result dict via next(v for v in data.values() if isinstance(v, list))

key-files:
  created:
    - backend/app/cubes/get_anomalies.py
    - backend/app/cubes/count_by_field.py
  modified:
    - backend/app/cubes/all_flights.py
    - backend/pyproject.toml
    - backend/uv.lock

key-decisions:
  - "GetAnomalies guards empty flight_ids early (before SQL) to avoid PostgreSQL ANY() type error with empty array"
  - "CountByField accepts both plain list and full_result dict — extracts first list value from dict to enable direct wiring from any cube"
  - "AllFlights bounding-box filter uses start_lat/start_lon (flight origin point) rather than both start and end — simpler and sufficient for region queries"
  - "CountByField uses dropna=False in groupby to preserve NaN/None groups rather than silently dropping them"

patterns-established:
  - "Empty input guard pattern: check for empty list/dict before DB query to avoid SQL errors"
  - "Full-result dict handling: extract first list value via next() comprehension for accepts_full_result inputs"

requirements-completed: [DATA-01, DATA-02, DATA-03, DATA-04, DATA-05]

# Metrics
duration: 8min
completed: 2026-03-04
---

# Phase 7 Plan 01: Real DB Cubes Summary

**AllFlights enhanced with airport/bounding-box filters and airline columns; GetAnomalies and CountByField cubes added to enable full AllFlights -> GetAnomalies -> CountByField pipeline with real Tracer 42 data**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-04T00:00:00Z
- **Completed:** 2026-03-04T00:08:00Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments
- AllFlights cube enhanced with airport ILIKE filter (matches origin or destination), bounding-box filter (min/max lat/lon on start_lat/start_lon), airline and airline_code columns in SELECT, and widget_hint="polygon" on polygon param
- GetAnomalies cube created querying research.anomaly_reports — guards empty flight_ids, supports optional min_severity filter, returns anomaly records and unique flight_ids
- CountByField aggregation cube created using pandas groupby — handles plain array or full_result dict input, returns [{value, count}] sorted descending
- pandas 3.0.1 added as production dependency

## Task Commits

Each task was committed atomically:

1. **Task 1: Enhance AllFlights + add GetAnomalies and CountByField cubes** - `9d6e07f` (feat)

## Files Created/Modified
- `backend/app/cubes/all_flights.py` - Added airport, min_lat, max_lat, min_lon, max_lon input params; widget_hint=polygon; airline/airline_code in SELECT; airport ILIKE and bounding-box filter logic
- `backend/app/cubes/get_anomalies.py` - New cube: queries research.anomaly_reports by flight_ids list, optional min_severity, guards empty input
- `backend/app/cubes/count_by_field.py` - New aggregation cube: pandas groupby, handles array and full_result dict input, returns sorted counts
- `backend/pyproject.toml` - Added pandas dependency
- `backend/uv.lock` - Updated with pandas 3.0.1 and numpy 2.4.2

## Decisions Made
- GetAnomalies guards empty flight_ids early (before SQL) to avoid PostgreSQL ANY() type error with empty array
- CountByField accepts both plain list and full_result dict — extracts first list value via `next()` comprehension
- AllFlights bounding-box filter uses start_lat/start_lon (flight origin point) — simpler and sufficient for region queries
- CountByField uses dropna=False in groupby to preserve NaN/None groups

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- CubeRegistry uses `all()` method not `get_all()` — discovered during verification, corrected test command immediately (no code change needed)

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All DATA requirements (01-05) complete
- End-to-end pipeline AllFlights -> GetAnomalies -> CountByField is ready for integration test
- Ready for 07-02 (Docker setup and end-to-end testing against live Tracer 42 data)

---
*Phase: 07-real-db-cubes-end-to-end-docker*
*Completed: 2026-03-04*
