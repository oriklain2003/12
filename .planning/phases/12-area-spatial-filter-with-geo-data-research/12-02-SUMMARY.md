---
phase: 12-area-spatial-filter-with-geo-data-research
plan: "02"
subsystem: api
tags: [shapely, geojson, spatial, geography, polygon, land-water, countries, fir, natural-earth]

# Dependency graph
requires: []
provides:
  - "backend/app/geo/ module with shared loader.py and three domain-specific geo loaders"
  - "countries.geojson (258 countries, ISO 3166) bundled as static data"
  - "fir_uir_europe.geojson (78 European FIR/UIR boundaries) bundled as static data"
  - "ne_50m_land.geojson (1420 Natural Earth 50m land polygons) bundled as static data"
  - "country_loader.classify_point(lat, lon) -> {country, iso3} or None"
  - "fir_loader.classify_point(lat, lon) -> {fir, name} or None"
  - "land_water_loader.is_land(lat, lon) -> bool, classify_point() -> 'land'|'water'"
affects:
  - "phase 12 plan 01 — area_spatial_filter cube can import these loaders for spatial modes"
  - "phase 13 — flight plan compliance checks may use country boundaries"
  - "any future cube needing country/FIR/land classification"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Static GeoJSON data bundled in backend/app/geo/data/ — no runtime network calls"
    - "Module-level cache: prepared Shapely geometries loaded once at import time"
    - "STRtree spatial index for land/water (1420 polygons) — O(log n) bbox pre-filter + contains_xy"
    - "Linear scan for countries/FIRs (78-258 features) — acceptable without spatial index"

key-files:
  created:
    - backend/app/geo/__init__.py
    - backend/app/geo/loader.py
    - backend/app/geo/country_loader.py
    - backend/app/geo/fir_loader.py
    - backend/app/geo/land_water_loader.py
    - backend/app/geo/data/countries.geojson
    - backend/app/geo/data/fir_uir_europe.geojson
    - backend/app/geo/data/ne_50m_land.geojson
  modified: []

key-decisions:
  - "FIR GeoJSON URL was not at root of jaluebbe/FlightMapEuropeSimple — file is in static/ subdirectory (flightmap_europe_fir_uir_ec_only.json)"
  - "Natural Earth primary URL (martynafford mirror) returned 404 — used nvkelso/natural-earth-vector mirror instead"
  - "FIR property keys are AV_AIRSPAC (designator) and AV_NAME (full name) — not 'id' or 'designator' as initially expected"
  - "countries.geojson uses 'name' and 'ISO3166-1-Alpha-3' as property keys (not ADMIN or ISO_A3)"
  - "land_water_loader uses STRtree for 1420 polygon pre-filtering; country/FIR loaders use linear scan (sufficient for <300 features)"
  - "Graceful degradation: all loaders wrap module-level load in try/except and return None/False if data files are missing"

patterns-established:
  - "Geo loader pattern: load_geojson() + module-level prepared geometry cache at import time"
  - "Coordinate swap at PIP boundary: callers pass (lat, lon), loaders call shapely.contains_xy(geom, lon, lat)"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-03-08
---

# Phase 12 Plan 02: Geo Data Loaders Summary

**Shapely-backed geo infrastructure: 3 bundled GeoJSON datasets (countries, European FIRs, land/water) with Python loader modules for lat/lon point classification**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-08T01:53:00Z
- **Completed:** 2026-03-08T01:56:05Z
- **Tasks:** 2
- **Files modified:** 8 created (5 Python + 3 GeoJSON data files)

## Accomplishments

- Downloaded and bundled three GeoJSON datasets as static data: countries (258, 14MB), European FIR/UIR (78, 265KB), Natural Earth 50m land (1420, 1.6MB)
- Implemented `loader.py` with shared `load_geojson()` and `build_polygon_index()` utilities using `shapely.geometry.shape()` + `shapely.prepare()`
- Implemented `country_loader.py` — classifies lat/lon to `{country, iso3}` using linear scan of 258 prepared country geometries
- Implemented `fir_loader.py` — identifies European FIR/UIR by designator (`AV_AIRSPAC`) for 78 boundaries
- Implemented `land_water_loader.py` — classifies land vs water using STRtree pre-filter over 1420 Natural Earth polygons
- All loaders: graceful degradation with logged warnings if data files are missing

## Task Commits

Each task was committed atomically:

1. **Task 1: Download GeoJSON data files and create shared loader module** — `aaab6e9` (feat)
2. **Task 2: Implement country, FIR, and land/water loader modules** — `1a83131` (feat)

## Files Created/Modified

- `backend/app/geo/__init__.py` — Empty module marker
- `backend/app/geo/loader.py` — Shared `load_geojson()` and `build_polygon_index()` utilities
- `backend/app/geo/country_loader.py` — Country boundary lookup; `classify_point(lat, lon)` returns `{country, iso3}` or None
- `backend/app/geo/fir_loader.py` — European FIR lookup; `classify_point(lat, lon)` returns `{fir, name}` or None
- `backend/app/geo/land_water_loader.py` — Land/water classification; `is_land(lat, lon)` and `classify_point()` returning "land"/"water"
- `backend/app/geo/data/countries.geojson` — 258 country boundaries (14MB, public domain, from datasets/geo-countries)
- `backend/app/geo/data/fir_uir_europe.geojson` — 78 European FIR/UIR features (265KB, from jaluebbe/FlightMapEuropeSimple/static/)
- `backend/app/geo/data/ne_50m_land.geojson` — 1420 land polygons (1.6MB, Natural Earth 50m, public domain, from nvkelso/natural-earth-vector)

## Decisions Made

- Used `STRtree` spatial index for land/water loader (1420 large polygons benefit from bbox pre-filtering) but linear scan for countries and FIRs (258/78 features — fast enough without an index)
- FIR GeoJSON property keys discovered by inspection: `AV_AIRSPAC` (designator) and `AV_NAME` (name) — the PLAN.md predicted `id`/`designator` but actual data differs
- Country property keys: `name` (not `ADMIN`) and `ISO3166-1-Alpha-3` (not `ISO_A3`) — discovered by inspecting actual file
- All loaders follow the same pattern: prepare at module load time, linear scan / STRtree query at classify time, graceful degrade if files missing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] FIR GeoJSON URL was incorrect**
- **Found during:** Task 1 (download FIR boundaries)
- **Issue:** Plan URL `https://raw.githubusercontent.com/jaluebbe/FlightMapEuropeSimple/master/flightmap_europe_fir_uir_ec_only.json` returned 404 — file is in `static/` subdirectory
- **Fix:** Fetched GitHub API to list repo contents, found file at `static/flightmap_europe_fir_uir_ec_only.json`, downloaded from correct URL
- **Verification:** File downloaded (265KB), 78 features parse correctly
- **Committed in:** aaab6e9 (Task 1 commit)

**2. [Rule 3 - Blocking] Natural Earth primary mirror URL was incorrect**
- **Found during:** Task 1 (download land polygons)
- **Issue:** Plan's primary URL `martynafford/natural-earth-geojson` returned 404 for 50m land file
- **Fix:** Used plan's alternative URL `nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson` which succeeded
- **Verification:** File downloaded (1.6MB), 1420 features parse correctly
- **Committed in:** aaab6e9 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 — URL corrections for data downloads)
**Impact on plan:** Minor — both were URL discovery issues, no architecture change. All data files downloaded and identical in content to what the plan intended.

## Issues Encountered

- FIR GeoJSON property keys (`AV_AIRSPAC`, `AV_NAME`) differ from the expected `id`/`designator` naming — discovered by inspecting the first feature before writing loader code. No impact on functionality.

## User Setup Required

None — no external service configuration required. All geo data files are bundled as static assets.

## Next Phase Readiness

- `backend/app/geo/` module is ready for import by `area_spatial_filter.py` (Phase 12 Plan 01) if future spatial modes (country_fir, surface_type) are added
- Country classification available for Phase 13 flight plan compliance checks
- All loaders verified: London=United Kingdom/GBR, London FIR=EGTT UIR, London=land, Mid-Atlantic=water

---
*Phase: 12-area-spatial-filter-with-geo-data-research*
*Completed: 2026-03-08*
