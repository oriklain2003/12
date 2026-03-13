---
phase: 16-fix-signal-health-cube-bugs-and-performance
plan: 01
subsystem: api
tags: [sqlalchemy, asyncio, adsb, signal-health, batch-queries, kalman, fastapi]

# Dependency graph
requires:
  - phase: 14-signal-health-analyzer
    provides: rule_based.py and kalman.py with per-hex async detection functions
  - phase: 15-cube-unit-tests
    provides: 53 signal health tests verifying detection and classification logic
provides:
  - batch async detection functions in rule_based.py (detect_integrity_events_batch_async, detect_shutdowns_batch_async)
  - batch positions fetch in kalman.py (fetch_positions_batch_async with 200-hex chunking)
  - startup-loaded coverage baseline (no TTL) via start_coverage_baseline_build()
  - CPU-bound Kalman/physics work offloaded to executor threads via run_in_executor
  - FastAPI lifespan hook replacing deprecated @app.on_event("startup")
affects: [16-02-signal-health-restructure, signal_health_analyzer_cube]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Batch ANY(:hex_list) queries instead of per-hex loops (N queries -> 1 query)
    - Partition batch results by hex via setdefault(hex, []).append(row)
    - asyncio.run_in_executor for CPU-bound numpy/scipy work in async context
    - asynccontextmanager lifespan hook for FastAPI startup tasks
    - Coverage baseline loaded once at startup, no TTL invalidation

key-files:
  created: []
  modified:
    - backend/app/signal/rule_based.py
    - backend/app/signal/kalman.py
    - backend/app/main.py

key-decisions:
  - "Batch functions use ANY(:hex_list) not a loop — reduces 4*N queries to 3 total for Plan 02"
  - "Coverage baseline simplified: loaded once at startup with 48-hour lookback, no TTL invalidation"
  - "CPU-bound kalman_filter, detect_position_jumps, detect_altitude_divergence, physics_cross_validation wrapped in run_in_executor to avoid blocking event loop"
  - "_serialize_datetimes removed — start/end serialized inline in classify_flight_async return dict"
  - "classify_flight_async now requires start_ts and end_ts (removes None-default auto-detect path)"
  - "Legacy per-hex functions kept with compatibility comment — tests and scripts still reference them"
  - "fetch_positions_batch_async uses chunk_size=200 to avoid overly large ANY() arrays"

patterns-established:
  - "Batch DB pattern: ANY(:hex_list) + setdefault partition — reuse for future multi-hex queries"
  - "Executor threading: loop.run_in_executor(None, sync_fn, args) for all numpy/scipy work"

requirements-completed: [SH-BATCH, SH-BASELINE, SH-KALMAN]

# Metrics
duration: 5min
completed: 2026-03-13
---

# Phase 16 Plan 01: Batch async APIs, startup baseline, and executor threading for signal health modules

**Batch ANY(:hex_list) detection functions + startup-loaded coverage baseline + run_in_executor for Kalman/physics, replacing per-hex loops and deprecated @app.on_event**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-13T16:02:07Z
- **Completed:** 2026-03-13T16:07:20Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `detect_integrity_events_batch_async()` and `detect_shutdowns_batch_async()` to rule_based.py using `ANY(:hex_list)` SQL pattern, partitioning results by hex
- Added `fetch_positions_batch_async()` to kalman.py with 200-hex chunking across multiple DB connections
- Wrapped all CPU-bound Kalman/physics computation in `asyncio.run_in_executor` to avoid blocking the event loop
- Simplified coverage baseline: removed TTL machinery, added `start_coverage_baseline_build()` called from FastAPI lifespan hook with 48-hour lookback
- Replaced deprecated `@app.on_event("startup")` with `@asynccontextmanager async def lifespan(app)` pattern
- Removed `_serialize_datetimes()` helper; datetime serialization now inline in `classify_flight_async`
- Made `classify_flight_async` require timestamps and accept optional pre-fetched `positions` argument
- All 53 existing signal health tests continue to pass

## Task Commits

1. **Task 1: Batch functions in rule_based.py + simplified baseline** - `7b5d77b` (feat)
2. **Task 2: Batch positions fetch + executor wrapping + cleanup in kalman.py** - `2dd1924` (feat)
3. **Task 3: Replace @app.on_event("startup") with lifespan hook in main.py** - `3615983` (feat)

## Files Created/Modified

- `backend/app/signal/rule_based.py` - Added batch detection functions, simplified baseline (no TTL), added start_coverage_baseline_build()
- `backend/app/signal/kalman.py` - Added fetch_positions_batch_async(), run_in_executor wrapping, removed _serialize_datetimes, updated classify_flight_async signature
- `backend/app/main.py` - Replaced @app.on_event with asynccontextmanager lifespan hook

## Decisions Made

- Batch functions use `ANY(:hex_list)` not a Python loop — reduces 4*N queries to 3 total, which Plan 02 will consume
- Coverage baseline simplified from TTL-based cache with background trigger to startup-only load with 48-hour lookback (user decision from RESEARCH.md)
- `_serialize_datetimes` removed; plan specifies inline serialization is cleaner and sufficient
- `classify_flight_async` now requires timestamps — removes the auto-detect fallback path that called `fetch_time_range_async`, which the cube always supplies explicitly
- `fetch_positions_batch_async` chunks at 200 hexes to avoid PostgreSQL ANY() performance degradation with large arrays

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. Pre-existing `test_area_spatial_filter.py::test_fr_provider_polygon` failure is unrelated to this plan (phase 12 issue, not signal health).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 02 (signal_health_analyzer.py restructure) can now consume:
  - `detect_integrity_events_batch_async(hex_list, start_ts, end_ts)` returning `dict[str, list[dict]]`
  - `detect_shutdowns_batch_async(hex_list, start_ts, end_ts)` returning `dict[str, list[dict]]`
  - `fetch_positions_batch_async(hex_list, start_ts, end_ts)` returning `dict[str, list[dict]]`
  - `classify_flight_async(hex_code, start_ts, end_ts, positions=positions)` with pre-fetched positions
  - `get_coverage_baseline()` returning the startup-loaded baseline dict

---
*Phase: 16-fix-signal-health-cube-bugs-and-performance*
*Completed: 2026-03-13*
