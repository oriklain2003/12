# Phase 12: Area Spatial Filter with Geo Data Research - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement `area_spatial_filter` FILTER cube with manual polygon mode and movement trigger classification. Research and implement geo datasets (FIR boundaries, land/water polygons, country boundaries) for future spatial modes. `country_fir` mode is OUT OF SCOPE (no FIR data yet — research only).

</domain>

<decisions>
## Implementation Decisions

### Dual-Provider Support
- Single cube with a `provider` select param — closed list: `fr`, `alison`
- FR provider: operates on `flight_ids` from AllFlights, queries `research.normal_tracks`
- Alison provider: operates on `hex_list` from AlisonFlights, queries `public.positions`
- Same pattern as `squawk_filter` (Phase 11)

### Movement Classification
- Three classifications: **landing**, **takeoff**, **cruise** (no approach/departure for now)
- Altitude threshold: **1000ft default, configurable input param**
- **Alison detection (primary signals):**
  - `on_ground` boolean — direct landing/takeoff detection via false→true / true→false transitions
  - `baro_rate` — vertical speed for supplementary classification
  - `alt_baro` — altitude check against threshold
  - `nav_modes` array — supplementary data only (autopilot, vnav, lnav, tcas observed; `approach` mode exists in spec but is not reliably present in data)
  - When `on_ground=True` has no lat/lon (common): use last known airborne position as landing point, first airborne position as takeoff point
- **FR detection (inferred — no `on_ground` column):**
  - `alt` + `vspeed` — altitude below threshold + descending = landing, below threshold + climbing = takeoff
  - `alt` above threshold + stable vspeed = cruise/transit

### Polygon Input
- Manual polygon mode only (user draws on PolygonMapWidget)
- Reuse `point_in_polygon()` ray-casting from `all_flights.py`
- Polygon also accepted via connection from upstream cube (JSON_OBJECT param with widget_hint=polygon)

### Filter Output
- **Only return flights that are inside the polygon area** (filter, not annotate-all)
- Per-flight output columns:
  - `flight_id` (FR) or `hex` (Alison) — always present as a column
  - `entry_time` — first timestamp inside polygon
  - `exit_time` — last timestamp inside polygon
  - `time_in_area` — duration (exit - entry)
  - `movement_classification` — landing / takeoff / cruise
- Standard outputs: filtered `flight_ids`/`hex_list`, `count`, Full Result with per-flight details

### Geo Data Research → Implementation
- Research AND implement geo dataset loaders (not just a markdown report)
- Evaluate and build loaders for:
  - FIR boundaries (Eurocontrol atlas) — for future `country_fir` mode
  - Land/water polygons (Natural Earth Data) — for future `surface_type` mode
  - Country boundaries (geo-countries GeoJSON) — for spatial country filtering
- Deliverable: working data loader modules that future phases can import

### Claude's Discretion
- Exact vspeed thresholds for FR landing/takeoff classification (suggested: |vspeed| > 300 ft/min)
- How to handle ambiguous cases (e.g., flight touches polygon edge, or altitude data is missing)
- Geo data storage format (GeoJSON files, SQLite, or in-memory Python structures)
- Performance optimization strategy for polygon ray-casting on large position datasets

</decisions>

<specifics>
## Specific Ideas

- Alison `nav_modes` array contains `['autopilot', 'vnav', 'lnav', 'tcas']` — autopilot disengages progressively during landing (observed: all 4 modes at 4700ft → vnav only at 925ft → lnav only at 175ft → empty at ground level). Could be useful metadata in Full Result.
- When `on_ground=True` in Alison data, lat/lon often become `None` — the transition boundary (last airborne point) is the reliable position for landing detection inside a polygon.
- FR `research.normal_tracks` has `vspeed` (ft/min) but no `on_ground` flag — classification must be inferred from altitude + vertical speed patterns.
- Both providers have bounding-box pre-filter pattern established (bbox from polygon → SQL WHERE → Python ray-casting for precise check).

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `point_in_polygon()` in `all_flights.py`: Ray-casting algorithm, already imported by `alison_flights.py`, `filter_flights.py`, `get_learned_paths.py` — reuse directly
- `PolygonMapWidget` (`frontend/src/components/CubeNode/PolygonMapWidget.tsx`): Already draws polygons on map, connected to `widget_hint="polygon"` params
- `SquawkFilterCube`: Template for dual-provider filter pattern with `provider` select param
- `FilterFlightsCube`: Template for filter cube accepting `flight_ids`/`full_result` inputs

### Established Patterns
- Bbox pre-filter → Python ray-casting: Used by AllFlights, AlisonFlights, FilterFlights, GetLearnedPaths
- Async SQLAlchemy with `text()` for raw SQL + parameterized queries
- Provider-aware queries: FR uses `research.normal_tracks` (flight_id, bigint timestamp), Alison uses `public.positions` (hex, timestamptz)
- Safety caps: LIMIT on SQL queries before Python post-processing

### Integration Points
- New cube auto-discovered by CubeRegistry — place in `backend/app/cubes/`
- Accepts `flight_ids` or `hex_list` + `full_result` from upstream data source cubes
- Geo data loader modules go in `backend/app/` (e.g., `geo/` subdirectory) for import by future cubes
- Frontend catalog auto-updates from `GET /api/cubes/catalog`

</code_context>

<deferred>
## Deferred Ideas

- `country_fir` spatial mode — depends on FIR boundary data (research in this phase, implement in future)
- `surface_type` spatial mode — depends on land/water polygon data (research in this phase, implement in future)
- Approach/departure as separate movement classifications — user decided cruise/landing/takeoff only for now
- `nav_modes`-based approach detection — data not reliably present, revisit when more coverage

</deferred>

---

*Phase: 12-area-spatial-filter-with-geo-data-research*
*Context gathered: 2026-03-08*
