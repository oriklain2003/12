---
phase: 16-fix-signal-health-cube-bugs-and-performance
plan: "02"
subsystem: signal-health-cube
tags: [performance, batch-queries, kalman, signal-health, refactor]
dependency_graph:
  requires: ["16-01"]
  provides: ["signal-health-batch-executor"]
  affects: ["backend/app/cubes/signal_health_analyzer.py", "backend/tests/test_signal_health_analyzer.py"]
tech_stack:
  added: []
  patterns: ["batch-async-gather", "in-memory-fan-out", "pre-fetched-positions"]
key_files:
  created: []
  modified:
    - backend/app/cubes/signal_health_analyzer.py
    - backend/tests/test_signal_health_analyzer.py
decisions:
  - "Pre-fetched positions passed to classify_flight_async via positions= param — skips per-hex DB fetch entirely"
  - "Kalman skipped for hexes with empty positions in batch result — avoids empty-set Kalman runs"
  - "Test file fully rewritten to mock batch APIs (detect_integrity_events_batch_async, detect_shutdowns_batch_async, fetch_positions_batch_async)"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-13"
  tasks_completed: 1
  files_modified: 2
---

# Phase 16 Plan 02: Restructure SignalHealthAnalyzerCube with Batch Architecture Summary

One-liner: Replaced 4*N per-hex DB queries with 3 concurrent batch queries using asyncio.gather, removing _analyze_hex and Semaphore, and added n_severe_alt_div to Kalman event output.

## What Was Built

`SignalHealthAnalyzerCube.execute()` was restructured from a per-hex semaphore-bounded loop (4*N DB queries for N hexes) to a batch architecture with exactly 3 DB queries total regardless of hex count.

**Key changes to `signal_health_analyzer.py`:**

1. **Imports updated** — removed `fetch_time_range_async`, `detect_integrity_events_async`, `detect_transponder_shutdowns_async`; added `detect_integrity_events_batch_async`, `detect_shutdowns_batch_async`, `fetch_positions_batch_async`, `datetime/timedelta/timezone`

2. **Time range computation** — `end_ts = datetime.now(timezone.utc)` and `start_ts = end_ts - timedelta(hours=lookback_hours)` in Python (previously fetched per-hex from DB via `fetch_time_range_async`)

3. **Batch gather** — `asyncio.gather(detect_integrity_events_batch_async(...), detect_shutdowns_batch_async(...), fetch_positions_batch_async(...))` replaces the semaphore-bounded `asyncio.gather(*[_run_hex(h) for h in hex_list])`

4. **Per-hex loop** — in-memory dict lookups via `.get(hx, [])` on the three batch result dicts; Kalman skipped when positions dict has no entry for that hex

5. **`_analyze_hex` removed** — per-hex method deleted entirely

6. **`asyncio.Semaphore` removed** — not needed with constant-connection batch queries

7. **`n_severe_alt_div` added** to `kalman_event_from_result()` — counts `a.get("severe")` across `alt_divergence` list

**Test file rewritten** — 18 tests using new batch mock pattern; added tests for `n_severe_alt_div` in kalman events, Kalman-skip-when-no-positions behavior, and per-hex error handling.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Updated test file to match new batch API**
- **Found during:** Task 1
- **Issue:** Existing tests patched `_analyze_hex`, `detect_integrity_events_async`, `detect_transponder_shutdowns_async`, and `fetch_time_range_async` — all removed by the restructure. Tests would fail at import or patch resolution.
- **Fix:** Fully rewrote test file to mock `detect_integrity_events_batch_async`, `detect_shutdowns_batch_async`, `fetch_positions_batch_async` at the import location. Added new tests for `n_severe_alt_div`, Kalman skip behavior, and error handling. 18 tests, all passing.
- **Files modified:** `backend/tests/test_signal_health_analyzer.py`
- **Commit:** 5e0e02c

## Verification Results

```
18 passed in 0.20s  (test_signal_health_analyzer.py)
```

Plan verification commands:
```
restructure OK
Cube restructured successfully
```

Pre-existing failures (out of scope, not caused by this plan):
- `test_area_spatial_filter.py`: 9 failures (bbox phase-1 narrowing to 0 — pre-existing)
- `test_stream_graph.py::test_stream_graph_row_limiting`: 1 failure (pre-existing)

## Self-Check: PASSED

- `backend/app/cubes/signal_health_analyzer.py` — exists, no `_analyze_hex`, no `Semaphore`, `n_severe_alt_div` present
- `backend/tests/test_signal_health_analyzer.py` — exists, 18 tests pass
- Commit `5e0e02c` — verified in git log
