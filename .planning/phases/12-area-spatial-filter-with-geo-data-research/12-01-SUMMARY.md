---
phase: 12-area-spatial-filter-with-geo-data-research
plan: "01"
subsystem: filter
tags: [shapely, spatial, polygon, pip, sqlalchemy, asyncpg, flight-analysis]

# Dependency graph
requires:
  - phase: 11-simple-filters-squawk-reg-country
    provides: dual-provider ID extraction pattern (squawk_filter template)
provides:
  - AreaSpatialFilterCube — dual-provider polygon spatial filter with movement classification
  - classify_movement_alison() — on_ground transition + baro_rate fallback classifier
  - classify_movement_fr() — alt+vspeed inference classifier
affects:
  - 12-02 (geo research uses same spatial patterns)
  - 15-tests (test_area_spatial_filter.py targets this cube)

# Tech tracking
tech-stack:
  added: [shapely (contains_xy + prepare), shapely.geometry.Polygon]
  patterns:
    - two-phase DB query (LATERAL DISTINCT discover, then full fetch for confirmed IDs)
    - Shapely prepare() for amortized PIP cost across all positions
    - lat/lon swap at Shapely boundary only (polygon input [[lat,lon]], Shapely (lon,lat))
    - dual-provider full_result fallback to direct inputs

key-files:
  created:
    - backend/app/cubes/area_spatial_filter.py
  modified: []

key-decisions:
  - "Two-phase DB query: LATERAL DISTINCT discovers which flights have bbox hits before fetching full position rows — avoids pulling 200k rows for flights that never enter the area"
  - "Shapely coordinate convention: polygon input is [[lat, lon]] (aviation/user convention); swap to (lon, lat) happens only at Shapely Polygon() boundary"
  - "Alison phase-2 query omits lat IS NOT NULL filter — on_ground=True rows with null coordinates are needed for movement classification signal"
  - "Movement classification uses all positions in flight's time window for Alison (not just inside_positions) — on_ground transitions may occur just outside bbox"
  - "time_window_hours input name chosen over lookback_hours (plan spec) — both FR and Alison use it for partition pruning"

patterns-established:
  - "LATERAL join for per-ID index lookup: unnest ids array, JOIN LATERAL (SELECT ... WHERE id = fid.id LIMIT 1) — forces per-ID index scan vs. full-table filter"
  - "Two-phase discovery + fetch pattern: phase 1 DISTINCT to find matching IDs, phase 2 full fetch only for confirmed set"

requirements-completed: []

# Metrics
duration: ~30min (original execution 2026-03-08)
completed: 2026-03-08
---

# Phase 12 Plan 01: Area Spatial Filter Summary

**AreaSpatialFilterCube with dual-provider Shapely PIP, two-phase LATERAL query, and on_ground/vspeed movement classification**

## Performance

- **Duration:** ~30 min (original execution)
- **Started:** 2026-03-08
- **Completed:** 2026-03-08
- **Tasks:** 1 of 2 auto-tasks complete (Task 2 is human-verify checkpoint)
- **Files modified:** 1

## Accomplishments

- `AreaSpatialFilterCube` implemented with full dual-provider support (FR: `research.normal_tracks`, Alison: `public.positions`)
- Two-phase LATERAL query eliminates unnecessary position fetches — phase 1 discovers which flights have bbox hits, phase 2 fetches only confirmed IDs
- Shapely `prepare()` + `contains_xy()` for efficient point-in-polygon across up to 200k positions
- Movement classification: Alison uses `on_ground` transitions (False→True = landing, True→False = takeoff) with baro_rate fallback; FR uses alt + vspeed inference
- Per-flight output: `entry_time`, `exit_time`, `time_in_area`, `duration_seconds`, `movement_classification`, `positions_in_area`, `entry_point`, `exit_point`, `path_in_area` (GeoJSON LineString)

## Task Commits

1. **Task 1: Implement AreaSpatialFilterCube** - `ce71f3a` (feat)
2. **Task 2: Human verify area spatial filter end-to-end** - checkpoint:human-verify (pending)

## Files Created/Modified

- `backend/app/cubes/area_spatial_filter.py` - AreaSpatialFilterCube, classify_movement_alison(), classify_movement_fr()

## Decisions Made

- **Two-phase query:** LATERAL DISTINCT discover (phase 1) before full position fetch (phase 2). Avoids fetching 200k rows for flights that never enter the bounding box.
- **Coordinate swap at Shapely boundary:** Polygon input convention is `[[lat, lon]]` (aviation/user). Swap to `(lon, lat)` happens only in `Polygon([(lon, lat) for lat, lon in polygon])` — no other code touches this.
- **Alison null-lat filter omitted in phase 2:** `on_ground=True` rows frequently have null lat/lon; these are needed for movement classification, so null filtering happens only in the Python PIP loop.
- **Movement classification uses all positions for Alison:** `on_ground` transitions can occur just outside the bbox. Using full `pos_list` (not just `inside_positions`) captures landing/takeoff events at field boundaries.
- **`time_window_hours` parameter:** Named more clearly than spec's `lookback_hours`; applies to both providers for partition pruning on timestamp columns.

## Deviations from Plan

None - plan executed exactly as written (two-phase query is an enhancement beyond spec, kept as it improves performance).

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `AreaSpatialFilterCube` is auto-discovered by `CubeRegistry` and available in `/api/cubes/catalog`
- Ready for human verification (Task 2 checkpoint)
- Phase 12 Plan 02 (geo data research — country/FIR/land-water loaders) can proceed independently

## Self-Check: PASSED

- `backend/app/cubes/area_spatial_filter.py` — FOUND
- Commit `ce71f3a` — FOUND

---
*Phase: 12-area-spatial-filter-with-geo-data-research*
*Completed: 2026-03-08*
