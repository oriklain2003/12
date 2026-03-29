---
phase: 23-shared-utility-foundation-duration-filter
plan: "02"
subsystem: backend/cubes
tags: [validation, datetime, cubes, tdd]
dependency_graph:
  requires: []
  provides: [partial-datetime-validation-all-flights, partial-datetime-validation-alison-flights]
  affects: [backend/app/cubes/all_flights.py, backend/app/cubes/alison_flights.py]
tech_stack:
  added: [backend/app/cubes/utils/time_utils.py, backend/app/cubes/utils/__init__.py]
  patterns: [validate-then-return-error-dict, tdd-red-green]
key_files:
  created:
    - backend/app/cubes/utils/__init__.py
    - backend/app/cubes/utils/time_utils.py
  modified:
    - backend/app/cubes/all_flights.py
    - backend/app/cubes/alison_flights.py
    - backend/tests/test_all_flights.py
    - backend/tests/test_alison_flights.py
decisions:
  - "Created utils package inline (Plan 01 parallel) — utils/__init__.py + time_utils.py bootstrapped by Plan 02 to unblock parallel execution"
  - "Pre-existing test_cube_inputs failure (missing airport param) is out of scope — logged as deviation, not fixed"
metrics:
  duration: 8m
  completed_date: "2026-03-29"
  tasks_completed: 2
  files_modified: 6
---

# Phase 23 Plan 02: Retrofit Partial Datetime Validation Summary

**One-liner:** Added `validate_datetime_pair` guard to AllFlights and AlisonFlights execute() so partial datetime inputs return a descriptive error dict instead of silently falling back to relative time mode.

## What Was Built

Both `AllFlights` and `AlisonFlights` cubes now call `validate_datetime_pair(start_time, end_time)` at the top of `execute()` before any SQL construction. Providing only `start_time` or only `end_time` returns an error dict immediately without touching the database. The `utils` package (`backend/app/cubes/utils/`) was bootstrapped inline since Plan 01 ran in parallel.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add partial datetime validation to AllFlights | 2b591a5 | all_flights.py, test_all_flights.py, utils/__init__.py, utils/time_utils.py |
| 2 | Add partial datetime validation to AlisonFlights | 5d4cfcf | alison_flights.py, test_alison_flights.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created utils package inline**
- **Found during:** Task 1 start
- **Issue:** `backend/app/cubes/utils/` did not exist (Plan 01 runs in parallel in same wave)
- **Fix:** Created `utils/__init__.py` and `utils/time_utils.py` with the exact `validate_datetime_pair` signature specified in the plan's `<important_note>`
- **Files modified:** backend/app/cubes/utils/__init__.py, backend/app/cubes/utils/time_utils.py
- **Commit:** 2b591a5

### Out-of-Scope Pre-existing Issue (Deferred)

`test_all_flights.py::test_cube_inputs` was already failing before this plan — it asserts an `airport` input parameter that does not exist on `AllFlightsCube`. This is a pre-existing test/implementation mismatch unrelated to datetime validation. Logged to deferred-items; not fixed.

## Known Stubs

None — all new error paths return populated error messages. No placeholder data.

## Verification Results

```
22 passed, 1 deselected (pre-existing test_cube_inputs)
```

- AllFlights: 10/11 tests pass (1 pre-existing failure excluded)
- AlisonFlights: 12/12 tests pass
- Import chain verified: `from app.cubes.utils.time_utils import validate_datetime_pair` — OK
