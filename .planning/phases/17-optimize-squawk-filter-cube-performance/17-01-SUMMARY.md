---
phase: 17-optimize-squawk-filter-cube-performance
plan: "01"
subsystem: backend/cubes
tags: [performance, sql, squawk-filter, optimization]
dependency_graph:
  requires: []
  provides: [optimized-squawk-filter]
  affects: [backend/app/cubes/squawk_filter.py, backend/tests/test_squawk_filter.py]
tech_stack:
  added: []
  patterns: [sql-pushdown, set-based-accumulation, loop-hoisting]
key_files:
  created: []
  modified:
    - backend/app/cubes/squawk_filter.py
    - backend/tests/test_squawk_filter.py
decisions:
  - "SQL pushdown via squawk = ANY(:codes) eliminates network transfer of non-matching rows for FR (both modes) and Alison custom mode"
  - "Set-based accumulation (codes_seen_set, matched_codes_set, emergency_values_set) replaces list + O(N) not-in guards; sorted() at output preserves determinism"
  - "Loop-hoisted is_emergency and is_alison booleans replace per-row string comparisons"
  - "Python match check simplified to len(position_rows) > 0 for all SQL-pushdown paths (SQL guarantees only matching rows)"
  - "Alison emergency mode SQL unchanged (filters by emergency column, not squawk code)"
metrics:
  duration_seconds: 112
  completed_date: "2026-03-13"
  tasks_completed: 2
  files_changed: 2
---

# Phase 17 Plan 01: Squawk Filter Performance Optimizations Summary

**One-liner:** SQL squawk pushdown via `ANY(:codes)` + set accumulation + loop hoisting in SquawkFilterCube, cutting network transfer to only matching rows.

## What Was Built

Three performance optimizations applied to `SquawkFilterCube` in a single-pass rewrite, with 3 test mocks updated to reflect the new SQL contract:

### Optimization 1: SQL Pushdown (High Impact)

FR provider (both custom and emergency modes): replaced `AND squawk IS NOT NULL` with `AND squawk = ANY(:codes)`. Added `"codes": list(target_codes)` to the params dict.

Alison custom mode: same replacement — `AND squawk IS NOT NULL` replaced by `AND squawk = ANY(:codes)`.

Alison emergency mode: unchanged (filters by `emergency IS NOT NULL AND emergency != 'none'`; squawk filtering not applicable).

Result: only rows matching target squawk codes are transferred from the database. For high-traffic hexes with thousands of positions, this eliminates the bulk of network transfer.

### Optimization 2: Set-Based Accumulation (Medium Impact)

`codes_seen`, `matched_codes`, `emergency_values` changed from `list` + `if code not in list` (O(N) per insert) to `set` + `.add()` (O(1) per insert). Converted to `sorted()` lists at output time to preserve deterministic ordering.

### Optimization 3: Loop Hoisting (Low Impact)

`is_emergency = (mode == "emergency")` and `is_alison = (provider == "alison")` computed once before the per-flight/per-row loops. String comparisons inside the loop replaced with boolean flag references.

### Python Match Check Simplification

With SQL pushdown guaranteeing only matching rows are returned, the `any(r["squawk"] in target_codes ...)` scan is redundant. Replaced with `matched = len(position_rows) > 0` for all paths.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1: Apply optimizations | 94359df | feat(17-01): apply three performance optimizations to SquawkFilterCube |
| Task 2: Update test mocks | 27707a4 | test(17-01): update 3 test mocks to reflect SQL pushdown contract |

## Test Results

All 14 tests in `tests/test_squawk_filter.py` pass.

Three tests updated:
- `test_custom_mode_fr_provider`: removed FL002 rows (squawk "1200" excluded by SQL)
- `test_custom_mode_alison_provider`: removed DEF456 row (squawk "1200" excluded by SQL)
- `test_emergency_mode_fr`: removed FL002 row (squawk "1200" excluded by ANY(:codes) with EMERGENCY_CODES_FR)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files exist:
- FOUND: backend/app/cubes/squawk_filter.py
- FOUND: backend/tests/test_squawk_filter.py

Commits exist:
- FOUND: 94359df (feat(17-01): apply three performance optimizations)
- FOUND: 27707a4 (test(17-01): update 3 test mocks)

Verification:
- `squawk = ANY(:codes)` appears at lines 214 and 259
- `set()` for accumulation at lines 304, 305, 306
- `is_emergency` / `is_alison` hoisted at lines 286-287
- All 14 tests pass in 0.13s
