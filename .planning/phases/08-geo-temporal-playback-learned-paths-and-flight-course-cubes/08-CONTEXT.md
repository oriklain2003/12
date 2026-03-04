# Phase 8: Geo-Temporal Playback, Learned Paths & Flight Course Cubes - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Three new cubes (Geo-Temporal Playback, Get Learned Paths, Get Flight Course) plus the visualization infrastructure to support output cubes that render custom visualizations in the ResultsDrawer map panel. Global row cap bumped from 100 to 10,000.

</domain>

<decisions>
## Implementation Decisions

### Geo-Temporal Playback Cube
- Category: `output`
- Inputs: `data` (json_object, accepts_full_result), `geometry_column` (string), `timestamp_column` (string), `id_column` (string, optional), `color_by_column` (string, optional)
- Output: passthrough data — this is a visualization-only cube
- Static `widget` field on CubeDefinition: `"geo_playback"`
- Auto-assigns colors to distinct objects (by id_column); if `color_by_column` is set, objects with the same value share a color
- No labels on map objects
- No trail/ghost effects — pure data at the current time window
- Objects appear/disappear instantly as they enter/leave the time window
- All same size — no variation by recency

### Playback Timeline UI
- Two draggable handles (start and end) on the timeline bar — user controls both position and window size freely
- Data density histogram rendered behind the timeline bar (subtle, shows where data concentrates)
- Play/pause button and speed selector (1x, 2x, 5x, 10x) below the timeline
- Minimal style — no extra decorations, just the functional controls
- Same CartoDB dark tiles and pan/zoom as existing ResultsMap

### Get Learned Paths Cube
- Category: `data_source`
- Queries `public.learned_paths` table
- Inputs (all optional): `origin` (string), `destination` (string), `path_id` (string), `polygon` (json_object, widget_hint=polygon), `min_member_count` (number)
- Input param `output_geometry` (string, closed list): `"centerline"` (returns LineString) or `"corridor"` (returns buffered Polygon using width_nm)
- Input param `width_override` (number, optional): overrides DB `width_nm` when generating corridor polygon
- Outputs: `paths` (json_object — array of rows: id, origin, destination, geometry, width_nm, member_count), `path_ids` (list_of_strings)
- One row per path
- Corridor polygon generated in Python by buffering centerline points by width_nm
- Polygon intersection filter uses ray-casting on centerline points (same pattern as AllFlights)
- On the map, paths colored by origin→destination pair (same pair = same color, different pairs = different colors)

### Get Flight Course Cube
- Category: `data_source`
- Queries `research.normal_tracks` by flight_ids
- Inputs: `flight_ids` (list_of_strings, required), `output_mode` (string, required — closed list: `"points"` or `"lines"`)
- Points mode outputs: all normal_tracks columns (flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source) + `geometry` column with GeoJSON Point object — one row per track point
- Lines mode outputs: `flight_id`, `callsign`, `geometry` (GeoJSON LineString), `start_time`, `end_time`, `min_alt`, `max_alt` — one row per flight
- Points mode is designed to feed directly into Geo-Temporal Playback cube (geometry_column → geometry, timestamp_column → timestamp, id_column → flight_id)

### Visualization Cube Infrastructure
- New static `widget` field added to `CubeDefinition` (string | None, default None)
- Visualization cubes (category: `output`) replace the map panel in ResultsDrawer with their custom component
- Table panel still shows alongside the visualization (same split layout as table+map)
- Clicking a regular cube (non-output) keeps current behavior: table + auto-detected map
- Clicking an output/visualization cube: table + custom visualization in place of map
- Multiple visualization cubes supported in one workflow — clicking between them swaps the right panel
- Drawer opens at same 1/3 height as today (user can resize)

### Global Row Cap Change
- Bump `result_row_limit` from 100 to 10,000 across all cubes
- Track data (normal_tracks) can be thousands of points per flight — 100 was too limiting

### Claude's Discretion
- Corridor polygon buffering algorithm (simple perpendicular offset vs geodesic)
- Color palette for auto-assigned colors
- Density histogram visual style (opacity, color, bar width)
- Timeline tick marks or time labels if needed for readability
- How to handle edge cases (empty data, single point, no timestamps)

</decisions>

<specifics>
## Specific Ideas

- Points mode of Get Flight Course + Geo-Temporal Playback is the key pipeline: AllFlights → Get Flight Course (points) → Playback — user watches flights move in real time
- Learned paths colored by origin→destination pair so overlapping routes between same airports are visually grouped
- The playback cube is generic — any data with geo+timestamp can be animated, not just flight tracks
- Corridor generation happens in Python (the cube builds the GeoJSON Polygon), frontend just renders whatever geometry it receives

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseCube` (backend/app/cubes/base.py): Subclass pattern with class-level attributes, auto Full Result output
- `ResultsMap` (frontend/src/components/Results/ResultsMap.tsx): Leaflet + CartoDB dark tiles, GeoJSON rendering, already supports arbitrary geometries via `geoInfo.geomCol`
- `ResultsDrawer` (frontend/src/components/Results/ResultsDrawer.tsx): Split layout with resizable divider — right panel currently renders ResultsMap
- `point_in_polygon()` (backend/app/cubes/all_flights.py): Ray-casting algorithm, reusable for learned paths polygon filter
- `PolygonMapWidget` (frontend/src/components/CubeNode/PolygonMapWidget.tsx): widget_hint=polygon already wired
- `geoDetect.ts` (frontend/src/utils/geoDetect.ts): Auto-detects lat/lon columns — used by default cubes, not by playback cube

### Established Patterns
- Cubes use `engine.connect()` directly for DB access (not FastAPI DI)
- widget_hint system for custom param editors (datetime, relative_time, polygon)
- ParamType enum: string, number, boolean, list_of_strings, list_of_numbers, json_object
- Full Result port bundles all outputs into one JSON object

### Integration Points
- `CubeDefinition` in backend/app/schemas/cube.py — add `widget: str | None = None` field
- `CubeDefinition` TypeScript mirror in frontend/src/types/cube.ts — add matching field
- `ResultsDrawer.tsx` — conditional render: if selected cube has `widget`, render custom component instead of ResultsMap
- `backend/app/config.py` — bump `result_row_limit` from 100 to 10,000
- `flowStore.ts` — may need to pass cube widget info to drawer

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-geo-temporal-playback-learned-paths-and-flight-course-cubes*
*Context gathered: 2026-03-05*
