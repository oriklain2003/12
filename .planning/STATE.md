---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Advanced Flight Analysis Cubes
status: in_progress
last_updated: "2026-03-08T00:00:00.000Z"
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 5
  completed_plans: 5
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
| 14 | Signal Health Analyzer Placeholder | `signal_health_analyzer` | Pending |

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

---
*Last session: 2026-03-08 — Phase 12 Plan 02 complete (geo data loader modules — country, FIR, land/water)*
