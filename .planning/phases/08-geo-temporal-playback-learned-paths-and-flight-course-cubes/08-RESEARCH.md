# Phase 8: Geo-Temporal Playback, Learned Paths & Flight Course Cubes - Research

**Researched:** 2026-03-05
**Domain:** Geo-temporal animation, GeoJSON geometry, new data cubes, visualization infrastructure
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Geo-Temporal Playback Cube**
- Category: `output`
- Inputs: `data` (json_object, accepts_full_result), `geometry_column` (string), `timestamp_column` (string), `id_column` (string, optional), `color_by_column` (string, optional)
- Output: passthrough data — this is a visualization-only cube
- Static `widget` field on CubeDefinition: `"geo_playback"`
- Auto-assigns colors to distinct objects (by id_column); if `color_by_column` is set, objects with the same value share a color
- No labels on map objects
- No trail/ghost effects — pure data at the current time window
- Objects appear/disappear instantly as they enter/leave the time window
- All same size — no variation by recency

**Playback Timeline UI**
- Two draggable handles (start and end) on the timeline bar — user controls both position and window size freely
- Data density histogram rendered behind the timeline bar (subtle, shows where data concentrates)
- Play/pause button and speed selector (1x, 2x, 5x, 10x) below the timeline
- Minimal style — no extra decorations, just the functional controls
- Same CartoDB dark tiles and pan/zoom as existing ResultsMap

**Get Learned Paths Cube**
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

**Get Flight Course Cube**
- Category: `data_source`
- Queries `research.normal_tracks` by flight_ids
- Inputs: `flight_ids` (list_of_strings, required), `output_mode` (string, required — closed list: `"points"` or `"lines"`)
- Points mode outputs: all normal_tracks columns (flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source) + `geometry` column with GeoJSON Point object — one row per track point
- Lines mode outputs: `flight_id`, `callsign`, `geometry` (GeoJSON LineString), `start_time`, `end_time`, `min_alt`, `max_alt` — one row per flight

**Visualization Cube Infrastructure**
- New static `widget` field added to `CubeDefinition` (string | None, default None)
- Visualization cubes (category: `output`) replace the map panel in ResultsDrawer with their custom component
- Table panel still shows alongside the visualization (same split layout as table+map)
- Clicking a regular cube (non-output) keeps current behavior: table + auto-detected map
- Clicking an output/visualization cube: table + custom visualization in place of map
- Multiple visualization cubes supported in one workflow — clicking between them swaps the right panel
- Drawer opens at same 1/3 height as today (user can resize)

**Global Row Cap Change**
- Bump `result_row_limit` from 100 to 10,000 across all cubes

### Claude's Discretion
- Corridor polygon buffering algorithm (simple perpendicular offset vs geodesic)
- Color palette for auto-assigned colors
- Density histogram visual style (opacity, color, bar width)
- Timeline tick marks or time labels if needed for readability
- How to handle edge cases (empty data, single point, no timestamps)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

## Summary

Phase 8 adds three new cubes and the visualization infrastructure that enables custom rendering widgets in the ResultsDrawer. The core technical work divides cleanly: (1) backend schema and cube implementations, (2) frontend visualization infrastructure (the `widget` dispatch system in ResultsDrawer), and (3) the GeoPlaybackWidget itself (a Leaflet map with a timeline controller).

The geo-temporal playback component is the most novel piece. The existing codebase uses react-leaflet v5 + Leaflet 1.9.4 with the exact same CartoDB dark tiles already wired. The playback animation loop can be driven entirely with `setInterval` or `requestAnimationFrame` in a `useRef`-managed loop, updating which data rows are "visible" at each tick and re-rendering the GeoJSON layer. No new mapping libraries are needed — the existing stack is sufficient.

For the corridor buffering in Get Learned Paths, **Shapely** (the standard Python geometry library) provides `LineString.buffer(distance)` which returns a Polygon directly. Shapely 2.x is fast, widely deployed, and produces correct results. However, pandas is already in the backend dependencies and the project currently does no heavy geometry work — Shapely adds a native C extension but is lightweight in practice. The alternative is a pure-Python perpendicular-offset implementation, which is feasible for simple corridors but error-prone at segment joins.

**Primary recommendation:** Implement playback with a `setInterval`-based animation loop (not requestAnimationFrame — simpler to pause/resume with speed multipliers), use Shapely for corridor buffering, and use a fixed categorical color palette derived from D3's `schemeTableau10` (10 visually distinct colors hardcoded as a constant — no D3 dependency needed).

---

## Standard Stack

### Core (already installed — no new installs needed for frontend)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-leaflet | ^5.0.0 | Map rendering in React | Already in use — CartoDB tiles, GeoJSON layer |
| leaflet | ^1.9.4 | Underlying map engine | Already in use — `L.circleMarker`, `L.latLngBounds` |
| zustand | ^5.0.11 | State management | Already in use — store already handles selectedResultNodeId |
| @types/leaflet | ^1.9.21 | TypeScript types | Already installed |

### Backend Additions
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shapely | >=2.0 | LineString buffering for corridor polygons | Get Learned Paths cube only |

**Installation (backend only):**
```bash
cd backend
uv add shapely
```

**No frontend installs required.** D3 color scales are NOT needed — use a hardcoded 10-color constant array.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Shapely | Pure Python perpendicular offset | Shapely is correct at joins and caps; hand-rolled math fails at sharp corners and self-intersecting corridors |
| setInterval timer | requestAnimationFrame | rAF is smoother for visual animation but harder to pause/speed-multiply; setInterval is easier to control and sufficient for data-at-timestamp updates |
| Hardcoded palette | d3-scale-chromatic | D3 adds 30KB+ dependency; 10 hex colors as a constant works fine |

---

## Architecture Patterns

### Recommended Project Structure (new files only)

```
backend/app/
├── cubes/
│   ├── get_learned_paths.py      # GetLearnedPathsCube
│   └── get_flight_course.py      # GetFlightCourseCube
│   └── geo_temporal_playback.py  # GeoTemporalPlaybackCube (output category)

frontend/src/
├── components/
│   ├── Results/
│   │   └── ResultsDrawer.tsx     # Modified: widget dispatch
│   └── Visualization/
│       ├── GeoPlaybackWidget.tsx  # New: animated map + timeline controller
│       └── GeoPlaybackWidget.css
├── types/
│   └── cube.ts                   # Modified: add widget?: string | null to CubeDefinition
```

### Pattern 1: Widget Field on CubeDefinition

Add `widget: str | None = None` to the Pydantic model and the BaseCube `definition` property. Cubes that need custom visualization set this as a class attribute.

**Backend (cube.py):**
```python
class CubeDefinition(BaseModel):
    cube_id: str
    name: str
    description: str = ""
    category: CubeCategory
    inputs: list[ParamDefinition] = []
    outputs: list[ParamDefinition] = []
    widget: str | None = None   # NEW
```

**Backend (base.py)** — `definition` property must pass `widget` through:
```python
@property
def definition(self) -> CubeDefinition:
    full_result = ParamDefinition(...)
    return CubeDefinition(
        cube_id=self.cube_id,
        name=self.name,
        description=self.description,
        category=self.category,
        inputs=list(self.inputs),
        outputs=list(self.outputs) + [full_result],
        widget=getattr(self, 'widget', None),   # NEW
    )
```

**Backend (geo_temporal_playback.py):**
```python
class GeoTemporalPlaybackCube(BaseCube):
    cube_id = "geo_temporal_playback"
    widget = "geo_playback"          # NEW class attribute
    category = CubeCategory.OUTPUT
    ...
```

**Frontend (cube.ts):**
```typescript
export interface CubeDefinition {
  cube_id: string;
  name: string;
  description: string;
  category: CubeCategory;
  inputs: ParamDefinition[];
  outputs: ParamDefinition[];
  widget?: string | null;    // NEW
}
```

### Pattern 2: Widget Dispatch in ResultsDrawer

ResultsDrawer currently renders `ResultsMap` when `geoInfo` is detected. New logic: if the selected cube has `widget`, render the matching custom component instead.

```typescript
// Inside ResultsDrawer — derive widget type from selected cube
const cubeWidget = useFlowStore((s) => {
  const node = s.nodes.find((n) => n.id === s.selectedResultNodeId);
  return node?.data.cubeDef.widget ?? null;
});

// In JSX — right panel decision:
{cubeWidget === 'geo_playback' ? (
  <GeoPlaybackWidget rows={results.rows} cubeDef={selectedCubeDef} />
) : geoInfo ? (
  <ResultsMap rows={results.rows} geoInfo={geoInfo} ... />
) : null}
```

The table panel always renders regardless of widget type (same split layout).

### Pattern 3: GeoPlaybackWidget Animation Loop

The playback widget manages its own local state. The animation loop uses `setInterval` stored in a `useRef` to avoid React re-render overhead:

```typescript
// Source: pattern from cherniavskii.com + Leaflet React useRef/useEffect guide
const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
const [playing, setPlaying] = useState(false);
const [windowStart, setWindowStart] = useState<number>(0);
const [windowEnd, setWindowEnd] = useState<number>(0);
const speedRef = useRef<number>(1);

// Animation tick: advance windowStart/windowEnd by (intervalMs * speed * dataRange)
// Filter rows: rows where timestamp >= windowStart && timestamp <= windowEnd
// Update GeoJSON layer via key={JSON.stringify} or direct Leaflet layer ref

useEffect(() => {
  if (!playing) {
    if (timerRef.current) clearInterval(timerRef.current);
    return;
  }
  timerRef.current = setInterval(() => {
    setWindowStart(prev => prev + TICK_STEP_MS * speedRef.current);
    setWindowEnd(prev => prev + TICK_STEP_MS * speedRef.current);
  }, 100); // 10fps tick — sufficient for data playback
  return () => { if (timerRef.current) clearInterval(timerRef.current); };
}, [playing]);
```

**Key insight:** The window position advances by a fixed real-time-to-data-time ratio. Speed multipliers (1x, 2x, 5x, 10x) scale the step size, not the interval frequency.

### Pattern 4: Dual-Handle Timeline Slider

Two overlapping `<input type="range">` elements, both absolutely positioned over the same track. The left thumb controls `windowStart`, the right thumb controls `windowEnd`. Z-index management ensures the closer handle stays on top when they overlap.

```typescript
// Both inputs share the same min/max (full data time range)
// Left thumb: value = windowStart; onChange -> setWindowStart
// Right thumb: value = windowEnd; onChange -> setWindowEnd
// CSS: position absolute, same dimensions, pointer-events none on track; only thumb clickable
```

This avoids any third-party range slider library. The pattern is well-documented (dev.to/sandra_lewis multi-range-slider article).

### Pattern 5: Corridor Buffering with Shapely

```python
# Source: Shapely 2.x documentation
from shapely.geometry import LineString, mapping

def build_corridor_polygon(coords: list[list[float]], width_nm: float) -> dict:
    """Buffer a centerline by width_nm nautical miles, return GeoJSON Polygon dict.

    coords: list of [lat, lon] pairs
    width_nm: half-width in nautical miles (1 NM = ~0.01453 degrees at 35N)
    """
    # GeoJSON uses [lon, lat]; Shapely uses (x=lon, y=lat)
    line = LineString([(lon, lat) for lat, lon in coords])
    # Convert NM to degrees: 1 NM ≈ 1/60 degree latitude
    buffer_degrees = width_nm / 60.0
    polygon = line.buffer(buffer_degrees, cap_style='flat', join_style='round')
    return mapping(polygon)  # Returns GeoJSON-compatible dict
```

**Note on coordinate system:** The simple degree approximation (1 NM = 1/60 degree) is acceptable for corridors — the error is <2% within ±60 degrees latitude. This is the "Claude's Discretion" area; the simple approach is sufficient for this application.

### Pattern 6: Density Histogram Behind Timeline

Compute a bucket count array in `useMemo` (one pass over timestamp data, N=100 buckets). Render as a CSS/SVG bar chart absolutely positioned behind the range slider. Subtle opacity (0.25-0.35) so it reads as background texture.

```typescript
const histogram = useMemo(() => {
  const N = 100;
  const buckets = new Array(N).fill(0);
  rows.forEach(row => {
    const ts = Number(row[timestampCol]);
    const idx = Math.floor((ts - tsMin) / (tsMax - tsMin) * (N - 1));
    if (idx >= 0 && idx < N) buckets[idx]++;
  });
  const max = Math.max(...buckets, 1);
  return buckets.map(v => v / max); // normalized 0-1
}, [rows, timestampCol, tsMin, tsMax]);
```

Render as `<svg>` or a series of `<div>` bars with `height: calc(30px * value)` from the bottom of the timeline container.

### Pattern 7: Color Assignment

No external library. A fixed 10-color categorical palette hardcoded in a constant. Colors are assigned from this palette in round-robin order keyed by `id_column` or `color_by_column` value.

```typescript
// Adapted from D3 Tableau10 — used by millions of data viz apps
const CATEGORICAL_COLORS = [
  '#4e79a7', '#f28e2b', '#e15759', '#76b7b2',
  '#59a14f', '#edc948', '#b07aa1', '#ff9da7',
  '#9c755f', '#bab0ac',
];

function getColor(key: string, colorMap: Map<string, string>): string {
  if (!colorMap.has(key)) {
    colorMap.set(key, CATEGORICAL_COLORS[colorMap.size % CATEGORICAL_COLORS.length]);
  }
  return colorMap.get(key)!;
}
```

Build the `colorMap` in `useMemo` on data load. Pass color per-feature into GeoJSON `pointToLayer` / `style` callbacks.

### Anti-Patterns to Avoid

- **Putting animation clock in Zustand:** The playback state (windowStart/End, playing, speed) is local to GeoPlaybackWidget, not global store state. It is ephemeral view state per the project's established pattern (see Phase 06-02 decision about selectedRowIndex).
- **Keying MapContainer on data change:** The existing codebase already documents this pitfall — do NOT put `key` on MapContainer. Key the GeoJSON layer (`key={JSON.stringify}`) to force re-mount on data change.
- **Re-creating Leaflet layer on every tick:** Use `key` on the `<GeoJSON>` component (forces re-mount) to update which features are visible. This is simpler than imperative layer management. With 10,000 rows and 100-row windows, this is fast enough.
- **Using setLatLng for marker updates:** setLatLng on individual marker refs is the "smooth animation" path for cinematic tracking. For this cube's "appear/disappear instantly" requirement, GeoJSON layer re-mount is cleaner and correct.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LineString buffering | Custom perpendicular offset math | `shapely.LineString.buffer()` | Correct at joins, segment caps; handles self-intersecting paths |
| GeoJSON serialization from Shapely | Manual dict construction | `shapely.geometry.mapping(polygon)` | Returns valid GeoJSON-compatible dict directly |
| Map tiles | Custom tile server | CartoDB dark tiles (already in use) | Consistent with existing ResultsMap; no infrastructure |
| Color palette math | HSL wheel calculation | Hardcoded Tableau10 array | 10 perceptually distinct colors, no computation |

**Key insight:** The buffering problem is the only "don't hand-roll" item that requires a new dependency. Everything else reuses the existing Leaflet/react-leaflet stack.

---

## Common Pitfalls

### Pitfall 1: Coordinate Order Confusion (lat/lon vs lon/lat)
**What goes wrong:** GeoJSON spec uses `[longitude, latitude]` order. Python code uses `[lat, lon]` lists. Shapely uses `(x=lon, y=lat)`. Mixing these produces geometries that appear in the ocean instead of the correct location.
**Why it happens:** The existing codebase (all_flights.py, PolygonMapWidget) consistently uses `[lat, lon]` format internally, then converts to `[lon, lat]` only when producing GeoJSON output. The pattern is correct but must be followed precisely.
**How to avoid:** Always convert: `LineString([(lon, lat) for lat, lon in coords])`. Document the convention at the top of each cube file.
**Warning signs:** Results appear at mirrored or rotated locations on the map.

### Pitfall 2: Shapely's `mapping()` Returns Nested Tuples, Not Lists
**What goes wrong:** `shapely.geometry.mapping()` returns geometry coordinates as tuples, e.g., `((lon, lat), ...)`. JSON serialization converts these correctly, but comparing with Python list expectations fails.
**How to avoid:** Call `json.loads(json.dumps(mapping(polygon)))` if downstream code assumes pure lists, or accept tuples as valid (JSON doesn't distinguish).

### Pitfall 3: Empty/Single-Row Data Edge Cases for Playback
**What goes wrong:** If all rows have the same timestamp, `tsMin === tsMax` causing division by zero in histogram and slider. If data has no timestamp column (wrong column name), all rows are silently dropped.
**How to avoid:**
- Guard: `if (tsMin === tsMax) { tsMax = tsMin + 1; }` before any range math
- Validate timestamp column name at component init; show error message if column not found
- Show "no data in window" state gracefully (empty map, not broken map)

### Pitfall 4: GeoJSON Layer key={JSON.stringify} with 10,000 Rows
**What goes wrong:** Stringifying 10,000-row filtered dataset on every tick creates a noticeable pause (could be 5-20ms per tick for large data).
**How to avoid:** Key the layer by a lightweight fingerprint, not the full data. Options:
- `key={`${windowStart}-${windowEnd}`}` — fast, forces re-mount only when window moves
- This is the preferred approach: react-leaflet GeoJSON layer keyed on the time window bounds

### Pitfall 5: result_row_limit Still Applies During Execution
**What goes wrong:** Bumping `result_row_limit` in config.py doesn't automatically work unless the executor actually uses that limit. The AllFlights cube has a hard-coded `LIMIT 5000` in its SQL, separate from the config limit.
**How to avoid:** The executor's row capping (`result_row_limit`) is enforced in `stream_graph`/`execute_graph` after cube execution. The config bump covers that path. But cubes with their own SQL LIMIT clauses must also be updated to pass through the full row set for large-data cubes. For `GetFlightCourse`, no internal limit — rely entirely on config limit.
**Warning signs:** Results truncated flag appears even after bumping the config.

### Pitfall 6: `public.learned_paths` Schema Unknown
**What goes wrong:** The exact column names in `public.learned_paths` are inferred from context but not verified against the live database. Columns like `width_nm`, `member_count`, `origin`, `destination` may have different actual names.
**How to avoid:** Add a schema inspection step during implementation (query `information_schema.columns` or run a `SELECT *` LIMIT 1). Document actual column names in the cube file.

---

## Code Examples

### Get Flight Course — Points Mode
```python
# Source: established pattern from AllFlights cube (backend/app/cubes/all_flights.py)
async with engine.connect() as conn:
    result = await conn.execute(
        text("""
            SELECT flight_id, timestamp, lat, lon, alt, gspeed, vspeed,
                   track, squawk, callsign, source
            FROM research.normal_tracks
            WHERE flight_id = ANY(:flight_ids)
            ORDER BY flight_id, timestamp
        """),
        {"flight_ids": list(flight_ids)}
    )
    columns = list(result.keys())
    rows = [dict(zip(columns, row)) for row in result.fetchall()]

# Add GeoJSON Point geometry per row
for row in rows:
    if row.get("lat") and row.get("lon"):
        row["geometry"] = {
            "type": "Point",
            "coordinates": [row["lon"], row["lat"]]  # GeoJSON: [lon, lat]
        }
```

### Get Flight Course — Lines Mode
```python
# Group by flight_id, build LineString from ordered track points
from collections import defaultdict

tracks: dict[str, list] = defaultdict(list)
for row in rows:
    tracks[row["flight_id"]].append(row)

lines = []
for flight_id, pts in tracks.items():
    pts.sort(key=lambda r: r["timestamp"])
    coords = [[p["lon"], p["lat"]] for p in pts if p.get("lat") and p.get("lon")]
    if len(coords) < 2:
        continue
    lines.append({
        "flight_id": flight_id,
        "callsign": pts[0].get("callsign"),
        "geometry": {"type": "LineString", "coordinates": coords},
        "start_time": pts[0]["timestamp"],
        "end_time": pts[-1]["timestamp"],
        "min_alt": min(p["alt"] for p in pts if p.get("alt") is not None),
        "max_alt": max(p["alt"] for p in pts if p.get("alt") is not None),
    })
```

### Get Learned Paths — Corridor Buffering
```python
# Source: Shapely 2.x documentation — shapely.readthedocs.io/en/stable/manual.html
from shapely.geometry import LineString, mapping

def centerline_to_corridor(coords: list[list[float]], width_nm: float) -> dict:
    """Convert [lat, lon] centerline to GeoJSON corridor polygon."""
    # Shapely: (x=lon, y=lat)
    line = LineString([(lon, lat) for lat, lon in coords])
    # 1 nautical mile ≈ 1/60 degree; half-width buffer
    buffer_deg = (width_nm / 2.0) / 60.0
    polygon = line.buffer(buffer_deg, cap_style='flat', join_style='round')
    geojson = mapping(polygon)
    return dict(geojson)  # Convert from Shapely's dict-like to plain dict
```

### GeoPlaybackWidget — Filtered Row Computation
```typescript
// Filter rows that fall within [windowStart, windowEnd]
const visibleRows = useMemo(() => {
  if (!timestampCol) return [];
  return rows.filter(row => {
    const ts = Number((row as Record<string, unknown>)[timestampCol]);
    return isFinite(ts) && ts >= windowStart && ts <= windowEnd;
  });
}, [rows, timestampCol, windowStart, windowEnd]);

// Build GeoJSON from visible rows using geometry column
const geojson = useMemo(() => buildPlaybackGeoJSON(visibleRows, geometryCol), [visibleRows, geometryCol]);
```

### ResultsDrawer — Widget Dispatch
```typescript
// Inside ResultsDrawer component
const cubeWidget = useFlowStore((s) => {
  const node = s.nodes.find((n) => n.id === s.selectedResultNodeId);
  return node?.data.cubeDef.widget ?? null;
});

// Right panel render decision:
const rightPanel = cubeWidget === 'geo_playback'
  ? <GeoPlaybackWidget rows={results.rows} cubeDef={selectedCubeDef} />
  : geoInfo
  ? <ResultsMap rows={results.rows} geoInfo={geoInfo} selectedRowIndex={selectedRowIndex} onMarkerClick={setSelectedRowIndex} />
  : null;
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| result_row_limit: 100 | result_row_limit: 10,000 | Phase 8 | Track data (thousands of points per flight) can now flow through the system |
| ResultsMap always in right panel | Widget dispatch: custom component or ResultsMap | Phase 8 | Extensible visualization system; future cubes can add new widget types |
| No output-category cubes | GeoTemporalPlayback as output cube | Phase 8 | Cubes can now own their visualization layer, not just their data |

**New in Phase 8:**
- `widget` field on CubeDefinition — the first use of cube-owned visualization
- `output` category cubes become meaningful (previously the category existed but no cube used it)
- Shapely added to backend dependencies for geometry operations

---

## Open Questions

1. **`public.learned_paths` actual schema**
   - What we know: columns inferred from CONTEXT.md: id, origin, destination, geometry (centerline as array of lat/lon), width_nm, member_count
   - What's unclear: exact column names, geometry storage format (WKT? array of floats? JSONB?), whether there's a `path_id` string or just a numeric id
   - Recommendation: During Wave 0 / task 1, run `SELECT column_name, data_type FROM information_schema.columns WHERE table_name='learned_paths' AND table_schema='public'` and adjust cube accordingly

2. **`research.normal_tracks` timestamp format**
   - What we know: AllFlights uses epoch seconds for `first_seen_ts`/`last_seen_ts`; normal_tracks has a `timestamp` column
   - What's unclear: Is normal_tracks.timestamp epoch seconds (bigint), or a PostgreSQL timestamptz?
   - Recommendation: Run `SELECT pg_typeof(timestamp) FROM research.normal_tracks LIMIT 1` during implementation; adjust frontend parsing if needed (if timestamptz, convert to epoch via `EXTRACT(EPOCH FROM timestamp)`)

3. **GeoJSON layer update strategy for 10k rows**
   - What we know: `key={windowStart}-{windowEnd}` forces GeoJSON layer re-mount on every tick; this is simpler but may flicker
   - What's unclear: At 10 FPS with sparse data, flickering may be imperceptible. With dense data (hundreds of simultaneous objects), re-mounting may lag.
   - Recommendation: Start with `key={windowStart}-{windowEnd}`. If lag is observed, switch to imperative Leaflet layer management via `useRef` on the L.GeoJSON layer instance and call `layer.clearLayers().addData(geojson)`.

---

## Validation Architecture

> `workflow.nyquist_validation` is false in `.planning/config.json` — this section is skipped.

---

## Sources

### Primary (HIGH confidence)
- Existing codebase: `backend/app/cubes/all_flights.py` — established patterns for SQL queries, ray-casting, engine.connect() usage
- Existing codebase: `frontend/src/components/Results/ResultsDrawer.tsx` — current split-panel layout to be extended
- Existing codebase: `frontend/src/components/Results/ResultsMap.tsx` — GeoJSON layer, CartoDB tiles, key-based re-mount pattern
- Existing codebase: `backend/app/schemas/cube.py` + `frontend/src/types/cube.ts` — CubeDefinition to be extended with `widget` field
- Existing codebase: `backend/app/cubes/base.py` — `definition` property to be updated to pass `widget` through
- [Shapely 2.x documentation](https://shapely.readthedocs.io/en/stable/manual.html) — LineString.buffer(), mapping() API
- `backend/pyproject.toml` — current dependencies (pandas present, shapely absent)
- `frontend/package.json` — react-leaflet 5.0.0, leaflet 1.9.4, zustand 5, no d3

### Secondary (MEDIUM confidence)
- [React Leaflet child components API](https://react-leaflet.js.org/docs/api-components/) — useRef/useEffect marker update patterns
- [Leaflet Playback GitHub](https://github.com/hallahan/LeafletPlayback) — reference for data-synchronized playback concept (not used as library)
- [DEV: Building a Multi-Range Slider in React From Scratch](https://dev.to/sandra_lewis/building-a-multi-range-slider-in-react-from-scratch-4dl1) — dual-handle implementation pattern
- [D3 Scale Chromatic — Categorical](https://d3js.org/d3-scale-chromatic/categorical) — Tableau10 color values (hardcoded, no d3 import)

### Tertiary (LOW confidence)
- WebSearch findings on requestAnimationFrame vs setInterval — setInterval preference for speed-multiplied playback is a judgment call, not authoritative

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — existing stack fully sufficient; only Shapely is new
- Architecture: HIGH — widget dispatch pattern is a clean extension of existing ResultsDrawer; cubes follow established BaseCube pattern
- Pitfalls: MEDIUM — coordinate order, Shapely output format, and row-limit interactions are known gotchas; learned_paths schema is genuinely unknown until runtime
- Animation approach: MEDIUM — setInterval with data-at-timestamp filtering is simple and correct; GeoJSON layer re-mount strategy may need revision based on observed performance

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable ecosystem — react-leaflet, shapely are mature)
