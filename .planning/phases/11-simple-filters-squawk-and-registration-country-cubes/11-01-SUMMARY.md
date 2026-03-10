---
phase: 11-simple-filters-squawk-and-registration-country-cubes
plan: "01"
subsystem: api
tags: [sqlalchemy, fastapi, icao24, adsb, aircraft, cubes, postgres]

requires: []

provides:
  - "AlisonFlightsCube data source cube querying public.aircraft + public.positions"
  - "ICAO24 hex-to-country lookup module with Black/Gray/worldwide ranges"
  - "hex_list output for downstream squawk_filter and registration_country_filter cubes"

affects:
  - 11-simple-filters-squawk-and-registration-country-cubes

tech-stack:
  added: []
  patterns:
    - "Cube outputs hex_list (LIST_OF_STRINGS) for chaining to filter cubes"
    - "Pure-Python ray-casting polygon filter (point_in_polygon reuse from all_flights)"
    - "ICAO24 range table sorted narrowest-first for correct overlap resolution"
    - "Longest-prefix-first registration matching for TAIL_PREFIXES lookup"

key-files:
  created:
    - backend/app/cubes/alison_flights.py
    - backend/app/cubes/icao24_lookup.py
  modified: []

key-decisions:
  - "Used array_agg(DISTINCT p.flight) to collapse multiple positions rows into one aircraft row per hex"
  - "Sorted ICAO24_RANGES by range width narrowest-first so smaller ranges (e.g. Oman 1024 addrs) match before overlapping larger ones"
  - "icao24_lookup is a plain module, not a BaseCube — it's a shared dependency, not an executable cube"
  - "Polygon filter uses same two-step approach as AllFlights: SQL bbox pre-filter + Python ray-casting post-filter"

patterns-established:
  - "Pattern: alison_flights -> hex_list output -> downstream filter cubes accept hex_filter input"

requirements-completed: []

duration: 3min
completed: "2026-03-06"
---

# Phase 11 Plan 01: Alison Flights Data Source + ICAO24 Lookup Summary

**Alison data source cube querying public.aircraft + public.positions with hex_list output and ICAO24 hex-to-country lookup tables for Black/Gray country classification**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-06T12:40:04Z
- **Completed:** 2026-03-06T12:42:35Z
- **Tasks:** 2
- **Files modified:** 2 created

## Accomplishments

- Created `icao24_lookup.py` with 27 ICAO24 hex ranges (10 black, 7 gray, 10 worldwide), REGION_GROUPS dict, 29 TAIL_PREFIXES, and four helper functions
- Created `AlisonFlightsCube` targeting `public.aircraft` + `public.positions` with 13 inputs and hex_list/flights outputs
- Both files auto-discovered by CubeRegistry on startup

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ICAO24 lookup module** - `dfc2620` (feat)
2. **Task 2: Create Alison data source cube** - `b0a4bc9` (feat)

## Files Created/Modified

- `backend/app/cubes/icao24_lookup.py` - Static ICAO24 hex ranges, region groups, tail prefixes, and resolve helpers
- `backend/app/cubes/alison_flights.py` - AlisonFlightsCube: queries public schema, outputs hex_list for downstream filters

## Decisions Made

- Used `array_agg(DISTINCT p.flight)` for callsigns so GROUP BY produces one row per hex address, not one row per position record
- ICAO24_RANGES sorted narrowest-first (by high-low delta) so smaller allocations (Oman: 1024, Yemen: 4096, Afghanistan: 4096) match before wider overlapping blocks
- `icao24_lookup` is a plain Python module — no BaseCube subclass — because it's a shared data dependency, not an executable workflow node
- Polygon filter reuses `point_in_polygon` imported from `app.cubes.all_flights` (Rule 2: avoiding duplicate code for correctness)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `hex_list` output is wired and ready for Plan 02 (`squawk_filter`) and Plan 03 (`registration_country_filter`) to consume via `hex_filter` input
- `ICAO24_RANGES`, `TAIL_PREFIXES`, `REGION_GROUPS`, and helpers exported from `icao24_lookup` — Plan 03 can import and use immediately
- Both cubes auto-register in CubeRegistry; no additional wiring needed

## Self-Check: PASSED

- FOUND: backend/app/cubes/icao24_lookup.py
- FOUND: backend/app/cubes/alison_flights.py
- FOUND: .planning/phases/11-simple-filters-squawk-and-registration-country-cubes/11-01-SUMMARY.md
- FOUND: commit dfc2620 (Task 1 — ICAO24 lookup module)
- FOUND: commit b0a4bc9 (Task 2 — AlisonFlightsCube)

---
*Phase: 11-simple-filters-squawk-and-registration-country-cubes*
*Completed: 2026-03-06*
