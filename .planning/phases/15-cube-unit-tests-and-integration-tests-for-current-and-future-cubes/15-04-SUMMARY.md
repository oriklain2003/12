---
phase: 15-cube-unit-tests-and-integration-tests-for-current-and-future-cubes
plan: 04
subsystem: backend/tests
tags: [testing, filters, squawk, registration-country, area-spatial]
dependency_graph:
  requires: [11-01, 11-02, 11-03, 12-01]
  provides: [filter-cube-test-coverage]
  affects: []
tech_stack:
  added: []
  patterns: [engine-mock-pattern, multi-call-side-effect]
key_files:
  created:
    - backend/tests/test_squawk_filter.py
    - backend/tests/test_registration_country_filter.py
    - backend/tests/test_area_spatial_filter.py
  modified: []
decisions: []
metrics:
  duration: "3m"
  completed: "2026-03-09"
---

# Phase 15 Plan 04: Filter Cube Unit Tests Summary

Unit tests for SquawkFilterCube, RegistrationCountryFilterCube, and AreaSpatialFilterCube covering dual-provider paths, filter modes, spatial containment, and movement classification.

## What Was Done

### Task 1: SquawkFilterCube Tests (14 tests)

Created `backend/tests/test_squawk_filter.py` with 14 tests covering:
- Cube metadata (id, category, inputs, outputs, accepts_full_result)
- Empty input guard (no DB call when no identifiers)
- Custom mode with FR provider (squawk code matching)
- Custom mode with Alison provider (squawk code matching)
- Custom mode with empty squawk_codes (early return)
- Emergency mode with FR provider (7500/7600/7700 codes)
- Emergency mode with Alison provider (emergency column pre-filtered by SQL)
- Code-change detection (squawk transitions between consecutive positions)
- Full result extraction for both flight_ids and hex_list keys
- Emergency values included in Alison per_flight_details

### Task 2: RegistrationCountryFilterCube Tests (13 tests) + AreaSpatialFilterCube Tests (15 tests)

Created `backend/tests/test_registration_country_filter.py` with 13 tests covering:
- Cube metadata (id, category, inputs, outputs)
- Empty hex_list guard
- Include mode (only matching countries pass)
- Exclude mode (matching countries removed)
- Region expansion (black group expands to all black-list countries)
- Unknown hex excluded in include mode (conservative rule)
- Unknown hex kept in exclude mode (conservative rule)
- Tail prefix fallback via public.aircraft DB query
- Empty countries+regions passthrough (no filter, all hexes pass with metadata)
- Full result hex_list extraction
- Both match type upgrade (hex_range + tail confirmation)

Created `backend/tests/test_area_spatial_filter.py` with 15 tests covering:
- Cube metadata (id, category, inputs, outputs)
- Empty input guard (no identifiers)
- No polygon guard (missing polygon)
- Insufficient polygon vertices (< 3 points)
- FR provider polygon containment
- Alison provider polygon containment
- Movement classification: landing (Alison on_ground False->True)
- Movement classification: takeoff (Alison on_ground True->False)
- Movement classification: cruise (FR high altitude, no significant vspeed)
- FR landing classification via altitude + vspeed
- FR takeoff classification via altitude + vspeed
- Per-flight details structure validation
- Polygon coordinate swap verification (lat/lon input -> lon/lat for Shapely)

## Test Results

All 42 tests pass across the 3 test files.

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 70ef500 | SquawkFilterCube unit tests (14 tests) |
| 2 | ac2e172 | RegistrationCountryFilterCube + AreaSpatialFilterCube tests (28 tests) |

## Self-Check: PASSED

- [x] backend/tests/test_squawk_filter.py exists (405 lines)
- [x] backend/tests/test_registration_country_filter.py exists (339 lines)
- [x] backend/tests/test_area_spatial_filter.py exists (369 lines)
- [x] Commit 70ef500 exists
- [x] Commit ac2e172 exists
