---
phase: 23-shared-utility-foundation-duration-filter
plan: "01"
subsystem: backend-cubes-utils
tags: [utilities, time-utils, historical-query, tdd, asyncio]
dependency_graph:
  requires: []
  provides:
    - backend/app/cubes/utils/time_utils.py (epoch_cutoff, validate_datetime_pair, TIME_MODE_PARAMS)
    - backend/app/cubes/utils/historical_query.py (get_callsign_history, get_route_history)
  affects:
    - Phase 24-26 behavioral cubes (import from cubes/utils/)
tech_stack:
  added: []
  patterns:
    - asyncio.gather for concurrent per-entity DB queries
    - Centralized ParamDefinition list (TIME_MODE_PARAMS) shared across cubes
    - Epoch-only time representation (no datetime mixing)
key_files:
  created:
    - backend/app/cubes/utils/__init__.py
    - backend/app/cubes/utils/time_utils.py
    - backend/app/cubes/utils/historical_query.py
    - backend/tests/test_time_utils.py
    - backend/tests/test_historical_query.py
  modified: []
decisions:
  - "cubes/utils/__init__.py is empty — no imports to prevent CubeRegistry auto-discovery side effects"
  - "TIME_MODE_PARAMS uses widget_hint='toggle' for time_mode to enable frontend toggle widget"
  - "Both history functions default to 604800s (7 days) per D-02 decision"
metrics:
  duration: "3 minutes"
  completed_date: "2026-03-29"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 0
---

# Phase 23 Plan 01: Shared Utility Foundation — Summary

**One-liner:** Created `cubes/utils/` package with epoch helpers, datetime pair validation, `TIME_MODE_PARAMS` reusable param list, and batch-async `get_callsign_history`/`get_route_history` using `asyncio.gather` with deduplication, backed by 24 TDD tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create cubes/utils/ package with time_utils.py | 0ff268f | `utils/__init__.py`, `time_utils.py`, `test_time_utils.py` |
| 2 | Create historical_query.py with batch async functions | 8d443c7 | `historical_query.py`, `test_historical_query.py` |

## What Was Built

### Task 1: time_utils.py

- `epoch_cutoff(lookback_seconds)` — returns `int(time.time()) - lookback_seconds` for rolling window queries
- `validate_datetime_pair(start_time, end_time)` — returns `None` for valid (both or neither), error dict for partial input
- `TIME_MODE_PARAMS: list[ParamDefinition]` — 4 reusable param definitions for behavioral cubes: `time_mode` (toggle, default="lookback"), `lookback_days` (default=7), `start_time` (datetime widget), `end_time` (datetime widget)
- 12 unit tests covering all functions and edge cases

### Task 2: historical_query.py

- `get_callsign_history(callsigns, lookback_seconds=604800)` — deduplicates input, fires `asyncio.gather` with one query per unique callsign against `research.flight_metadata`, returns `{callsign: [row_dicts]}`
- `get_route_history(routes, lookback_seconds=604800)` — deduplicates `(origin, dest)` tuples, fires `asyncio.gather`, returns `{(origin, dest): [row_dicts]}`
- Both functions return rows with same 10-column shape as AllFlights output (D-04)
- Integrates `epoch_cutoff` from `time_utils` for consistent lookback computation
- 12 unit tests covering empty input, single query, deduplication, epoch_cutoff integration, row shape, tuple keys

## Verification Results

```
tests/test_time_utils.py: 12 passed
tests/test_historical_query.py: 12 passed
tests/test_filter_flights.py::test_min_duration_filter_excludes_short_flights: PASSED
tests/test_filter_flights.py::test_max_duration_filter_excludes_long_flights: PASSED
No BaseCube in backend/app/cubes/utils/: PASS
```

Full test suite: 385 passing (10 pre-existing failures in `test_area_spatial_filter.py`, `test_agent_infra.py`, `test_all_flights.py`, `test_stream_graph.py` — all pre-date this plan, confirmed via git stash verification).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all exported functions are fully implemented with real SQL queries.

## Self-Check: PASSED
