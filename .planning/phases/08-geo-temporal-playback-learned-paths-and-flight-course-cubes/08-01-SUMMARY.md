---
phase: 08-geo-temporal-playback-learned-paths-and-flight-course-cubes
plan: 01
subsystem: api
tags: [geojson, cube, schema, sqlalchemy, flight-tracks]

# Dependency graph
requires:
  - phase: 07-real-db-cubes-end-to-end-docker
    provides: BaseCube pattern, CubeDefinition schema, engine.connect() DB access pattern
provides:
  - CubeDefinition.widget field (Python + TypeScript) — schema foundation for visualization cubes
  - result_row_limit bumped to 10000 — supports high-volume track queries
  - GetFlightCourseCube — flight track data source returning GeoJSON Points or LineStrings
affects:
  - 08-02-geo-temporal-playback-widget
  - 08-03-learned-paths-cube
  - any future visualization cube using widget field

# Tech tracking
tech-stack:
  added: []
  patterns:
    - GeoJSON coordinates use [lon, lat] order (GeoJSON spec, not [lat, lon])
    - Early empty-array guard before SQL ANY() to prevent PostgreSQL type error
    - Points mode adds geometry field inline to track rows; Lines mode groups via collections.defaultdict

key-files:
  created:
    - backend/app/cubes/get_flight_course.py
  modified:
    - backend/app/schemas/cube.py
    - backend/app/cubes/base.py
    - backend/app/config.py
    - frontend/src/types/cube.ts

key-decisions:
  - "GeoJSON coordinates follow spec order [lon, lat], not display order [lat, lon]"
  - "Lines mode skips flights with fewer than 2 valid coordinate points to avoid degenerate LineStrings"
  - "widget field defaults to None in BaseCube.definition via getattr(self, 'widget', None) — no change needed to existing cubes"
  - "result_row_limit raised from 100 to 10000 to support full flight track queries"

patterns-established:
  - "widget: str | None on CubeDefinition — visualization cubes set class-level widget = 'widget_name'"
  - "Empty flight_ids early guard — return empty results before ANY() SQL to prevent PostgreSQL errors"

requirements-completed: [GEO-01, GEO-02, GEO-03]

# Metrics
duration: 8min
completed: 2026-03-05
---

# Phase 8 Plan 01: CubeDefinition widget field, row cap bump, and Get Flight Course cube

**CubeDefinition extended with widget field in Python and TypeScript, result_row_limit raised to 10000, and GetFlightCourseCube added returning GeoJSON Points or LineStrings from research.normal_tracks**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-05T12:02:00Z
- **Completed:** 2026-03-05T12:10:51Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added `widget: str | None = None` to `CubeDefinition` in Python and `widget?: string | null` in TypeScript
- Updated `BaseCube.definition` to pass widget through via `getattr(self, 'widget', None)` — existing cubes unaffected
- Raised `result_row_limit` from 100 to 10000 in `config.py`
- Implemented `GetFlightCourseCube` with two output modes: points (GeoJSON Point per track row) and lines (GeoJSON LineString per flight)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add widget field to CubeDefinition and bump row cap** - `aa9f1d2` (feat)
2. **Task 2: Implement Get Flight Course cube** - `c6a003f` (feat)

## Files Created/Modified
- `backend/app/schemas/cube.py` - Added `widget: str | None = None` to CubeDefinition
- `backend/app/cubes/base.py` - Updated definition property to pass widget via getattr
- `backend/app/config.py` - Changed result_row_limit default from 100 to 10000
- `frontend/src/types/cube.ts` - Added `widget?: string | null` to CubeDefinition interface
- `backend/app/cubes/get_flight_course.py` - New cube: queries normal_tracks, returns GeoJSON points or lines

## Decisions Made
- GeoJSON coordinates follow spec order `[lon, lat]`, not display order `[lat, lat]`
- Lines mode skips flights with fewer than 2 valid coordinate points to avoid degenerate LineStrings
- `widget` passes through `getattr(self, 'widget', None)` so existing cubes need no changes
- `result_row_limit` raised to 10000 since flight track queries can produce thousands of rows per flight

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `CubeDefinition.widget` field is available for visualization cubes in phase 08-02 (geo-temporal playback widget)
- `GetFlightCourseCube` provides the flight track data source for the playback pipeline
- Row cap of 10000 supports full track loading without hitting the old 100-row ceiling

---
*Phase: 08-geo-temporal-playback-learned-paths-and-flight-course-cubes*
*Completed: 2026-03-05*
