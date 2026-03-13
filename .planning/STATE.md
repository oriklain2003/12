---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Advanced Flight Analysis Cubes
status: unknown
last_updated: "2026-03-13T14:16:09.415Z"
progress:
  total_phases: 7
  completed_phases: 4
  total_plans: 19
  completed_plans: 17
---

# Project State: Project 12

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-06)

**Core value:** Users can build and run custom flight analysis pipelines visually
**Current focus:** v2.0 — Advanced Flight Analysis Cubes (6 new cubes across 4 phases)

## Current Milestone

**v2.0:** 🔲 In Progress — Advanced Flight Analysis Cubes

4 phases, 3 plans (phase 11 planned, 1 plan executed). Next action: `/gsd:execute-phase 11` plan 02

### Phase Overview

| Phase | Name | Cubes | Status |
|-------|------|-------|--------|
| 11 | Simple Filters — Squawk & Reg Country | `squawk_filter`, `registration_country_filter` | Complete (3/3 plans — awaiting human verify checkpoint) |
| 12 | Area Spatial Filter + Geo Research | `area_spatial_filter` | Complete (2/2 plans) |
| 13 | Flight Plans Source & Compliance | `flight_plans_source`, `flight_plan_compliance_analyzer` | Pending |
| 14 | Signal Health Analyzer Placeholder | `signal_health_analyzer` | Complete (3/3 plans) |

## Previous Milestones

**v1.0:** ✅ Shipped 2026-03-06
10 phases, 23 plans, 55 requirements satisfied (53 full, 2 partial).
See `.planning/MILESTONES.md` for details.

## Accumulated Context

### Tech Debt (from v1.0 audit)

- Orphaned `GET /api/workflows/{id}/run/stream` route (no frontend caller)
- `execute_graph()` dead production code in executor.py
- AllFlights/GetAnomalies SQL `LIMIT 5000` inconsistent with global 10,000 cap
- BACK-08 requirement text describes removed endpoint
- No VERIFICATION.md files for any phase (0/10)

### Key Decisions (Phase 11 / Plan 01)

- **2026-03-06:** AlisonFlightsCube uses `array_agg(DISTINCT p.flight)` so GROUP BY yields one row per hex (not per position record)
- **2026-03-06:** `ICAO24_RANGES` sorted narrowest-first so smaller address blocks (Oman 1024, Yemen 4096, Afghanistan 4096) resolve before wider overlapping ranges
- **2026-03-06:** `icao24_lookup.py` is a plain module (not a BaseCube) — it is a shared data dependency for registration_country_filter, not an executable workflow node

### Roadmap Evolution

- **2026-03-06:** v2.0 milestone created with 4 phases (11-14) covering 6 new cubes:
  - Phase 11: `squawk_filter` + `registration_country_filter` (simple filters, no external deps)
  - Phase 12: `area_spatial_filter` (polygon intersection + geo data research)
  - Phase 13: `flight_plans_source` + `flight_plan_compliance_analyzer` (FlightAware API integration)
  - Phase 14: `signal_health_analyzer` (placeholder for future classification logic)
- **2026-03-06:** Phase 11 Plan 01 executed — `AlisonFlightsCube` and `icao24_lookup` created
- **2026-03-06:** Phase 11 Plan 02 executed — `SquawkFilterCube` created (dual-provider: FR + Alison, emergency detection via positions.emergency, code-change events)
- **2026-03-06:** Phase 11 Plan 03 executed — `RegistrationCountryFilterCube` created (ICAO24 hex range + tail prefix dual-resolution, include/exclude modes, Black/Gray region groups)

### Key Decisions (Phase 11 / Plan 02)

- **2026-03-06:** String comparison for squawk codes throughout — DB type check for public.positions timed out; string comparison is safe for both VARCHAR and INTEGER storage
- **2026-03-06:** Use `to_timestamp(:cutoff)` for Alison time filter — compute epoch in Python and pass as integer param to avoid SQL injection with interval syntax
- **2026-03-06:** Store per_flight_details in return dict — BaseCube auto-includes in __full_result__ without extra configuration

### Key Decisions (Phase 11 / Plan 03)

- **2026-03-06:** Conservative unknown-aircraft rule: unknown country excluded in include mode (not assumed to match target), kept in exclude mode (not assumed to be outside target)
- **2026-03-06:** Two-pass DB query for hex_range hexes: second pass upgrades match_type to "both" when tail prefix also confirms, providing resolution confidence metadata
- **2026-03-06:** Empty countries+regions passes all hexes through (no filter) with warning — not an error; interpreted as "no country filtering requested"

### Key Decisions (Phase 12 / Plan 02)

- **2026-03-08:** FIR GeoJSON is in `static/` subdirectory of jaluebbe/FlightMapEuropeSimple (not repo root) — URL discovery via GitHub API contents endpoint required
- **2026-03-08:** Natural Earth primary mirror (martynafford) returned 404 — used nvkelso/natural-earth-vector as fallback mirror (same dataset, public domain)
- **2026-03-08:** `land_water_loader` uses `STRtree` for 1420 polygon bbox pre-filter; `country_loader` and `fir_loader` use linear scan (sufficient for <300 features)
- **2026-03-08:** countries.geojson property keys are `name` and `ISO3166-1-Alpha-3` (not `ADMIN`/`ISO_A3` as in other datasets like Natural Earth countries); fir_uir_europe.geojson uses `AV_AIRSPAC` and `AV_NAME`

### Roadmap Evolution (Phase 12)

- **2026-03-08:** Phase 12 Plan 01 executed — `AreaSpatialFilterCube` created (dual-provider FR+Alison, polygon-inside filter, movement classification)
- **2026-03-08:** Phase 12 Plan 02 executed — `backend/app/geo/` module created with 3 bundled GeoJSON datasets and 3 Shapely-backed loader modules

### Key Decisions (Phase 14 / Plan 01)

- **2026-03-09:** `score_event` returns augmented event dict (not tuple) — plan API spec requires scored dict for `classify_event` to consume
- **2026-03-09:** `classify_event` accepts scored event dict: transponder_off passthrough for gap_detection source events without re-scoring
- **2026-03-09:** 7-day default lookback for coverage baseline (vs 30-day in CLI script) — per RESEARCH.md recommendation for interactive cube latency
- **2026-03-09:** 1-hour TTL module-level cache for coverage baseline avoids repeated heavy queries on every workflow run

### Key Decisions (Phase 14 / Plan 02)

- **2026-03-08:** Only DB-touching functions are async in kalman.py; pure computation stays sync — no benefit to async-ifying math, simpler to test and reason about
- **2026-03-08:** `_serialize_datetimes()` helper converts datetime objects to ISO strings in classify_flight_async result — ensures JSON serializability without polluting computation functions
- **2026-03-08:** All Kalman constants preserved verbatim from detect_kalman.py (CHI2_THRESHOLD=13.82, POSITION_JUMP_KM=55.56, ALT_DIVERGENCE_FT=1000) — tuned against known spoofing test cases

### Key Decisions (Phase 14 / Plan 03)

- **2026-03-09:** `full_result` extraction checks both `hex_list` and `flight_ids` keys — AlisonFlights uses hex_list, other cubes may use flight_ids
- **2026-03-09:** "Stable" classify_mode handled separately — returns hexes with zero non-normal events (not an empty event filter result)
- **2026-03-09:** `target_phase` filtering post-hoc by entry altitude: takeoff/landing < 5000ft, cruise >= 10000ft; Kalman events always pass through (no per-event altitude in v1 unified schema)

### Roadmap Evolution (Phase 14)

- **2026-03-09:** Phase 14 Plan 01 executed — `backend/app/signal/rule_based.py` created (async integrity event detection, transponder shutdown detection, 16-point scoring, coverage baseline with TTL cache); numpy + scipy added
- **2026-03-08:** Phase 14 Plan 02 executed — `backend/app/signal/kalman.py` created (constant-velocity Kalman filter, chi-squared innovation testing, position jump detection, altitude divergence, physics cross-validation, async flight classification)
- **2026-03-09:** Phase 14 Plan 03 executed — `backend/app/cubes/signal_health_analyzer.py` created (SignalHealthAnalyzerCube orchestrating both detection layers, classify_mode filtering, unified event schema); phase 14 complete
- Phase 15 added: Cube unit tests and integration tests for current and future cubes
- Phase 16 added: Fix signal health cube bugs and performance (based on docs/signal_health_analysis.md audit)
- Phase 17 added: Optimize squawk filter cube performance

### Key Decisions (Phase 15 / Plan 01)

- **2026-03-09:** expand_regions only resolves known region tags (black/gray); country names are silently ignored -- tests reflect actual implementation
- **2026-03-09:** Full result dict test for CountByFieldCube uses realistic structure with metadata + flights array to validate first-list extraction

### Key Decisions (Phase 15 / Plan 05)

- **2026-03-09:** countries.geojson uses "-99" for some ISO3 codes (e.g. France) -- tests check key existence not standard codes
- **2026-03-09:** NYC at 50m Natural Earth resolution falls on water boundary -- used Denver as inland US test point

### Key Decisions (Phase 15 / Plan 02)

- **2026-03-09:** DB mocking via patch at import location (app.cubes.xxx.engine) with AsyncMock context managers
- **2026-03-09:** Polygon tests use side_effect on engine.connect for sequential DB calls (metadata then tracks)
- **2026-03-09:** Empty flight_ids guard verified as no-filter behavior (not early return) matching GetAnomaliesCube implementation

### Roadmap Evolution (Phase 15)

- **2026-03-09:** Phase 15 Plan 01 executed -- conftest.py + 55 unit tests for 4 pure-logic cubes and icao24_lookup module, all passing
- **2026-03-09:** Phase 15 Plan 02 executed -- 29 unit tests for data-source cubes (AllFlights 9, AlisonFlights 10, GetAnomalies 10), all passing
- **2026-03-09:** Phase 15 Plan 05 executed -- 26 unit tests for geo loaders (country_loader, fir_loader, land_water_loader), all passing
- **2026-03-09:** Phase 15 Plan 04 executed -- 42 unit tests for filter cubes (SquawkFilter 14, RegistrationCountryFilter 13, AreaSpatialFilter 15), all passing
- **2026-03-09:** Phase 15 Plan 07 executed -- 21 tests: 13 SignalHealthAnalyzerCube unit tests + 8 integration pipeline tests through WorkflowExecutor; phase 15 complete (236 total tests, all passing)

### Key Decisions (Phase 16 / Plan 01)

- **2026-03-13:** Batch ANY(:hex_list) detection functions replace per-hex loops — reduces 4*N queries to 3 total for Plan 02 consumption
- **2026-03-13:** Coverage baseline simplified: startup-only with 48-hour lookback via lifespan hook, no TTL invalidation
- **2026-03-13:** Kalman/physics CPU work wrapped in run_in_executor — classify_flight_async now non-blocking
- **2026-03-13:** _serialize_datetimes removed; start/end serialized inline in classify_flight_async return dict
- **2026-03-13:** classify_flight_async requires timestamps (no None defaults); accepts optional pre-fetched positions argument

### Key Decisions (Phase 16 / Plan 02)

- **2026-03-13:** Pre-fetched positions passed to classify_flight_async via positions= param — skips per-hex DB fetch entirely
- **2026-03-13:** Kalman skipped for hexes with empty positions in batch result — avoids empty-set Kalman runs
- **2026-03-13:** Test file fully rewritten to mock batch APIs (detect_integrity_events_batch_async, detect_shutdowns_batch_async, fetch_positions_batch_async)

### Roadmap Evolution (Phase 16)

- **2026-03-13:** Phase 16 Plan 01 executed — batch detection functions added to rule_based.py and kalman.py, coverage baseline simplified to startup-only, lifespan hook added to main.py, Kalman/physics wrapped in run_in_executor
- **2026-03-13:** Phase 16 Plan 02 executed — SignalHealthAnalyzerCube.execute() restructured with batch architecture (3 queries total vs 4*N), _analyze_hex removed, Semaphore removed, n_severe_alt_div added to Kalman events; 18 tests passing

### Key Decisions (Phase 17 / Plan 01)

- **2026-03-13:** SQL pushdown via `squawk = ANY(:codes)` for FR (both custom and emergency modes) and Alison custom mode eliminates network transfer of non-matching rows
- **2026-03-13:** Set-based accumulation (codes_seen_set, matched_codes_set, emergency_values_set) with `sorted()` at output replaces O(N) list membership guards — O(N²) → O(N) per flight
- **2026-03-13:** Loop-hoisted `is_emergency` and `is_alison` booleans replace per-row string comparisons; Python match check simplified to `len(position_rows) > 0` for all SQL-pushdown paths
- **2026-03-13:** Alison emergency mode SQL unchanged — filters by `emergency IS NOT NULL AND emergency != 'none'`; `squawk = ANY(:codes)` not applicable

### Roadmap Evolution (Phase 17)

- **2026-03-13:** Phase 17 Plan 01 executed — SquawkFilterCube optimized with SQL pushdown, set accumulation, and loop hoisting; 3 test mocks updated to reflect new SQL contract; all 14 tests pass

---
*Last session: 2026-03-13 — Phase 17 Plan 01 complete (SQL pushdown + set accumulation + loop hoisting for SquawkFilterCube)*
