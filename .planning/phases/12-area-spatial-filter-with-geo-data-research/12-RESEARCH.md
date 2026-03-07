# Phase 12: Area Spatial Filter with Geo Data Research - Research

**Researched:** 2026-03-08
**Domain:** Spatial filtering, polygon intersection, movement classification, geo dataset loading
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Dual-Provider Support:** Single cube with a `provider` select param — closed list: `fr`, `alison`
  - FR provider: operates on `flight_ids` from AllFlights, queries `research.normal_tracks`
  - Alison provider: operates on `hex_list` from AlisonFlights, queries `public.positions`
  - Same pattern as `squawk_filter` (Phase 11)

- **Movement Classification:** Three classifications: landing, takeoff, cruise (no approach/departure)
  - Altitude threshold: 1000ft default, configurable input param
  - Alison detection (primary signals): `on_ground` boolean, `baro_rate`, `alt_baro`, `nav_modes` array
  - When `on_ground=True` has no lat/lon: use last known airborne position as landing point, first airborne as takeoff point
  - FR detection (inferred): `alt` + `vspeed` — altitude below threshold + descending = landing, below threshold + climbing = takeoff

- **Polygon Input:** Manual polygon mode only; reuse `point_in_polygon()` ray-casting from `all_flights.py`; polygon also accepted via connection from upstream cube

- **Filter Output:** Only return flights inside the polygon area (filter, not annotate-all)
  - Per-flight columns: `flight_id`/`hex`, `entry_time`, `exit_time`, `time_in_area`, `movement_classification`
  - Standard outputs: filtered `flight_ids`/`hex_list`, `count`, Full Result with per-flight details

- **Geo Data Research → Implementation:** Research AND implement geo dataset loaders (not just a markdown report)
  - FIR boundaries (Eurocontrol atlas) — for future `country_fir` mode
  - Land/water polygons (Natural Earth Data) — for future `surface_type` mode
  - Country boundaries (geo-countries GeoJSON) — for spatial country filtering
  - Deliverable: working data loader modules that future phases can import

### Claude's Discretion

- Exact vspeed thresholds for FR landing/takeoff classification (suggested: |vspeed| > 300 ft/min)
- How to handle ambiguous cases (e.g., flight touches polygon edge, or altitude data is missing)
- Geo data storage format (GeoJSON files, SQLite, or in-memory Python structures)
- Performance optimization strategy for polygon ray-casting on large position datasets

### Deferred Ideas (OUT OF SCOPE)

- `country_fir` spatial mode — research in this phase, implement in future
- `surface_type` spatial mode — research in this phase, implement in future
- Approach/departure as separate movement classifications
- `nav_modes`-based approach detection — data not reliably present
</user_constraints>

---

## Summary

Phase 12 implements the `area_spatial_filter` cube — a dual-provider spatial filter that determines whether flights (FR `flight_ids` or Alison `hex` addresses) passed through a user-drawn polygon, and classifies each flight's movement type (landing, takeoff, or cruise) within the area. The phase also produces working geo data loader modules for FIR boundaries, land/water polygons, and country boundaries, to be consumed by future phases.

The core query pattern (bbox SQL pre-filter + Python-side ray-casting) is already established in `AllFlights` and `AlisonFlights`. The key NEW challenges are: (1) retrieving ordered position sequences per flight (not just an existence check), (2) computing entry/exit timestamps and duration, and (3) classifying movement type using provider-specific signals (`on_ground` + `baro_rate` for Alison; `alt` + `vspeed` for FR). Shapely 2.1.2 is already in `pyproject.toml` and should replace the existing ray-casting for performance at scale.

The geo data deliverables are separate loader modules in `backend/app/geo/`. The recommended strategy is: bundle GeoJSON files as static data files alongside the loader code (no DB writes, no network calls at runtime), loaded once at module import and cached. Natural Earth 50m land polygons and `geo-countries` are well-established public-domain datasets with direct GeoJSON URLs. Eurocontrol FIR data requires conversion from shapefile — the `jaluebbe/FlightMapEuropeSimple` repo provides a pre-converted GeoJSON ready to use directly.

**Primary recommendation:** Implement `area_spatial_filter` cube following the SquawkFilter dual-provider template. Use Shapely 2.1.2's `contains_xy()` + `prepare()` for performance on the position sequence arrays. Store geo data as static GeoJSON files in `backend/app/geo/data/` with thin Python loader modules that cache on import.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Shapely | 2.1.2 (already in pyproject.toml) | Polygon geometry + point-in-polygon tests | GEOS-backed, vectorized `contains_xy()` + `prepare()` for multi-point testing; far faster than manual ray-casting for large position sets |
| SQLAlchemy (async) | 2.0+ (already present) | Async DB queries for track positions | Established project pattern |
| json (stdlib) | stdlib | Load bundled GeoJSON files | Lightweight; no extra deps for static file loading |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas | 3.0.1+ (already present) | Optional: group/sort position rows | Can use pure Python dicts instead — no additional install needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing `point_in_polygon()` ray-casting | Shapely `contains_xy()` | Shapely is faster for large position arrays because the inner loop runs in C; ray-casting is fine for a handful of points but degrades at 10K+ positions per flight |
| In-memory GeoJSON | SQLite/SpatiaLite | SQLite adds dependency; not needed for read-only static polygons loaded at startup |
| Downloading geo data at runtime | Bundled static files | Network calls at runtime create fragility; static files are reproducible and fast |

**Installation:** No new packages needed — Shapely 2.1.2 is already in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure

```
backend/app/
├── cubes/
│   └── area_spatial_filter.py       # New cube — dual-provider, movement classification
└── geo/
    ├── __init__.py                   # Empty
    ├── loader.py                     # Shared loader: load_geojson(), get_polygon_by_property()
    ├── country_loader.py             # Country boundaries (geo-countries GeoJSON)
    ├── fir_loader.py                 # FIR boundaries (Eurocontrol/FlightMapEuropeSimple)
    ├── land_water_loader.py          # Land/ocean polygons (Natural Earth 50m)
    └── data/
        ├── countries.geojson         # From: datasets/geo-countries (public domain)
        ├── fir_uir_europe.geojson    # From: jaluebbe/FlightMapEuropeSimple (Eurocontrol)
        └── ne_50m_land.geojson       # From: naturalearthdata.com 50m land (public domain)
```

### Pattern 1: Dual-Provider Filter (from SquawkFilter template)

**What:** Single cube with `provider` param that routes to FR or Alison query logic.
**When to use:** Any cube that must work with both `research.normal_tracks` and `public.positions`.

```python
# Source: backend/app/cubes/squawk_filter.py (established pattern)
provider = str(inputs.get("provider") or "fr").lower()

full_result = inputs.get("full_result")
ids: list[str] = []
if full_result and isinstance(full_result, dict):
    if provider == "alison":
        raw = full_result.get("hex_list") or full_result.get("flight_ids") or []
    else:
        raw = full_result.get("flight_ids") or []
    ids = [str(x) for x in raw if x is not None]

# Fallback to direct inputs
if not ids:
    if provider == "alison":
        raw = inputs.get("hex_list") or []
    else:
        raw = inputs.get("flight_ids") or []
    ids = [str(x) for x in (raw or []) if x is not None]
```

### Pattern 2: Bbox Pre-filter + Shapely Point-in-Polygon

**What:** SQL bounding box reduces position rows fetched; Shapely `prepare()` + `contains_xy()` does precise polygon check in Python.
**When to use:** Any spatial filter operating on large position tables without PostGIS.

```python
# Source: Shapely 2.1.2 docs (shapely.readthedocs.io)
from shapely.geometry import Polygon
import shapely

# Build polygon once and prepare it (pre-computes internal GEOS index)
poly_shapely = Polygon([(lon, lat) for lat, lon in polygon])
shapely.prepare(poly_shapely)

# For each flight, check all bbox-filtered positions
# polygon is [[lat, lon], ...] — shapely expects (lon, lat) order
for pos_row in bbox_filtered_rows:
    lon, lat = float(pos_row["lon"]), float(pos_row["lat"])
    if shapely.contains_xy(poly_shapely, lon, lat):
        # This position is inside the polygon
        ...
```

Note: The existing `point_in_polygon()` uses `[lat, lon]` order. Shapely uses `(x=lon, y=lat)`. Be explicit about coordinate order when converting.

### Pattern 3: Position Sequence Processing for Movement Classification

**What:** Fetch ordered positions for each flight, find polygon-inside subsequence, classify movement from position signals.
**When to use:** `area_spatial_filter` — must compute entry/exit times and movement type.

```python
# FR provider: research.normal_tracks
# Columns available: flight_id, timestamp (bigint epoch), lat, lon, alt (ft), vspeed (ft/min)
sql_fr = """
    SELECT flight_id, timestamp, lat, lon, alt, vspeed
    FROM research.normal_tracks
    WHERE flight_id = ANY(:ids)
      AND lat BETWEEN :bbox_min_lat AND :bbox_max_lat
      AND lon BETWEEN :bbox_min_lon AND :bbox_max_lon
    ORDER BY flight_id, timestamp
"""

# Alison provider: public.positions
# Columns available: hex, ts (timestamptz), lat, lon, alt_baro (ft), baro_rate (ft/min), on_ground (bool)
sql_alison = """
    SELECT hex, ts, lat, lon, alt_baro, baro_rate, on_ground
    FROM public.positions
    WHERE hex = ANY(:ids)
      AND ts >= to_timestamp(:cutoff)
      AND lat BETWEEN :bbox_min_lat AND :bbox_max_lat
      AND lon BETWEEN :bbox_min_lon AND :bbox_max_lon
    ORDER BY hex, ts
"""
```

**Movement classification logic (Alison):**

```python
def classify_movement_alison(positions_in_area: list[dict]) -> str:
    """Classify movement from Alison position sequence within polygon.

    Priority: on_ground transitions > baro_rate > altitude threshold.
    """
    ALTITUDE_THRESHOLD_FT = 1000  # configurable input param

    # Check on_ground transitions (most reliable signal)
    on_ground_values = [p["on_ground"] for p in positions_in_area if p.get("on_ground") is not None]
    if on_ground_values:
        # true->false transition in ordered sequence = takeoff
        # false->true transition = landing
        for i in range(1, len(positions_in_area)):
            prev_g = positions_in_area[i-1].get("on_ground")
            curr_g = positions_in_area[i].get("on_ground")
            if prev_g is True and curr_g is False:
                return "takeoff"
            if prev_g is False and curr_g is True:
                return "landing"

    # Fall back to altitude + baro_rate
    alts = [p["alt_baro"] for p in positions_in_area if p.get("alt_baro") is not None]
    rates = [p["baro_rate"] for p in positions_in_area if p.get("baro_rate") is not None]

    if alts and max(alts) < ALTITUDE_THRESHOLD_FT:
        avg_rate = sum(rates) / len(rates) if rates else 0
        if avg_rate < -300:
            return "landing"
        if avg_rate > 300:
            return "takeoff"

    return "cruise"
```

**Movement classification logic (FR):**

```python
def classify_movement_fr(positions_in_area: list[dict], altitude_threshold_ft: float) -> str:
    """Classify movement from FR track sequence within polygon.

    No on_ground column — infer from alt + vspeed.
    """
    VSPEED_THRESHOLD = 300  # ft/min — at Claude's discretion

    alts = [p["alt"] for p in positions_in_area if p.get("alt") is not None]
    vspeeds = [p["vspeed"] for p in positions_in_area if p.get("vspeed") is not None]

    if not alts:
        return "cruise"  # no altitude data — ambiguous

    avg_alt = sum(alts) / len(alts)
    avg_vspeed = sum(vspeeds) / len(vspeeds) if vspeeds else 0

    if avg_alt < altitude_threshold_ft:
        if avg_vspeed < -VSPEED_THRESHOLD:
            return "landing"
        if avg_vspeed > VSPEED_THRESHOLD:
            return "takeoff"

    return "cruise"
```

### Pattern 4: Geo Data Loader Module

**What:** Static GeoJSON files bundled with backend code, loaded once at module import, cached as Shapely Polygon objects.
**When to use:** All three geo loader modules (countries, FIR, land/water).

```python
# Source: Pattern derived from icao24_lookup.py (existing static data module)
# backend/app/geo/loader.py
import json
import pathlib
from shapely.geometry import shape
import shapely

_DATA_DIR = pathlib.Path(__file__).parent / "data"

def load_geojson(filename: str) -> list[dict]:
    """Load a GeoJSON FeatureCollection from the data/ directory."""
    path = _DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        fc = json.load(f)
    return fc["features"]


def build_polygon_index(features: list[dict], name_property: str) -> dict[str, object]:
    """Build a dict of name -> prepared Shapely Polygon from GeoJSON features.

    Preparing polygons at load time amortizes cost across all future PIP queries.
    """
    index = {}
    for feature in features:
        name = feature["properties"].get(name_property)
        if name is None:
            continue
        geom = shape(feature["geometry"])  # converts GeoJSON geometry to Shapely
        shapely.prepare(geom)              # prepare for fast repeated PIP queries
        index[name] = geom
    return index
```

### Anti-Patterns to Avoid

- **Querying positions without a time bound for Alison:** `public.positions` has 46M+ rows. Always add `AND ts >= to_timestamp(:cutoff)` with a lookback window (same as SquawkFilter's `lookback_hours` param).
- **Using `point_in_polygon()` for geo dataset membership tests:** The existing ray-casting is fine for user-drawn polygons (small vertex count). For complex country/FIR boundary polygons with hundreds of vertices, use Shapely's prepared geometry — it's orders of magnitude faster.
- **Assuming `on_ground=True` positions have valid lat/lon:** When `on_ground=True`, lat/lon are commonly `None` in Alison data. Use last known airborne position for the spatial check.
- **Returning all positions, not just those inside polygon:** The cube is a filter — only return flights confirmed to be inside the polygon. Entry/exit times come from the subsequence of positions that pass `contains_xy()`.
- **Omitting bbox pre-filter from SQL:** Without the bbox clause, the positions query does a full scan. Always derive bbox from polygon before querying.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Complex polygon geometry ops | Manual winding number or ray-casting for complex polygons | `shapely.contains_xy()` + `shapely.prepare()` | GEOS-backed, handles edge cases (self-intersecting rings, antimeridian), runs in C |
| GeoJSON geometry parsing | Manual `feature["geometry"]["coordinates"]` traversal | `shapely.geometry.shape(feature["geometry"])` | Handles all GeoJSON geometry types (Polygon, MultiPolygon) without custom code |
| Country polygon lookup | Build own ISO code database | `geo-countries` GeoJSON (public domain, 255 features, ISO 3166 properties) | Maintained dataset, correct polygons, ready to use |
| Land/water classification | Build custom coastline data | Natural Earth 50m land GeoJSON (public domain) | Standard cartographic dataset, appropriate resolution for aviation use |

**Key insight:** The `shapely` package is already installed. The project has been using manual ray-casting for bbox-filtered candidate positions, which works but misses the performance and correctness benefits of Shapely's GEOS-backed operations for complex geo dataset polygons.

---

## Common Pitfalls

### Pitfall 1: Coordinate Order Confusion (lon, lat vs lat, lon)

**What goes wrong:** Shapely and GeoJSON use `(lon, lat)` (i.e., `(x, y)`). The existing `point_in_polygon()` and polygon widget use `[lat, lon]`. Mixing these silently produces wrong intersection results — points appear outside polygons they are inside.

**Why it happens:** The aviation/mapping world uses lat/lon, but GeoJSON spec uses lon/lat (x/y). Shapely follows GeoJSON.

**How to avoid:** Convert at the boundary — when constructing a Shapely Polygon from the user's `[[lat, lon], ...]` array, explicitly swap: `Polygon([(lon, lat) for lat, lon in polygon])`. Document this conversion in code comments.

**Warning signs:** Zero polygon hits on flights that visually overlap the drawn area.

### Pitfall 2: `on_ground=True` Positions Have No Coordinates

**What goes wrong:** When classifying landing/takeoff for Alison, the key transitions happen when `on_ground` flips. But these rows often have `lat=None, lon=None`. If you only look at positions with valid coordinates, you miss the transition event entirely.

**Why it happens:** Alison data omits GPS coordinates when the aircraft is on the ground (likely to save bandwidth or because GPS is not locked).

**How to avoid:** Process all positions in temporal order regardless of null lat/lon. For spatial containment (is the flight inside the polygon?), use only positions with valid coordinates. For movement classification, include the `on_ground` boolean from all rows in the sequence. The last airborne position before `on_ground=True` is the spatial landing point.

**Warning signs:** All area events classified as "cruise" even for known landing operations.

### Pitfall 3: Alison Positions Table Full Scan

**What goes wrong:** Querying `public.positions` with only `hex = ANY(:ids)` (no time filter) on the 46M-row table times out or runs for minutes.

**Why it happens:** Without a time predicate on the `ts` column, PostgreSQL cannot use the time-based index and performs a full table scan.

**How to avoid:** Always include `AND ts >= to_timestamp(:cutoff)` with a configurable `lookback_hours` parameter (default 24h, same as SquawkFilter). Compute the cutoff epoch in Python: `cutoff = int(time.time() - lookback_hours * 3600)`.

**Warning signs:** Query takes longer than 10 seconds; Alison results show old flights that the upstream AlisonFlights cube would not have returned.

### Pitfall 4: Empty Positions for a Flight Inside the Polygon

**What goes wrong:** A flight is returned by AllFlights/AlisonFlights but zero positions fall in the bbox query, so it is absent from the spatial filter output. This can happen if the flight's metadata (start_lat/start_lon in `flight_metadata`) falls inside the polygon but the actual track points do not.

**Why it happens:** `flight_metadata.start_lat/start_lon` is the first point of the flight (takeoff origin), not necessarily a position in the area of interest.

**How to avoid:** The filter cube should only output flights confirmed to have a position inside the polygon. Flights with zero track positions inside the polygon are simply not in the output — this is correct behavior, not a bug. Log a DEBUG message for any flight that had positions fetched but none passed the PIP check.

### Pitfall 5: FR `timestamp` is Bigint Epoch, Alison `ts` is Timestamptz

**What goes wrong:** Comparing or formatting entry/exit times inconsistently between providers — one returns Unix integers, the other returns datetime objects.

**Why it happens:** `research.normal_tracks.timestamp` is stored as bigint (Unix epoch seconds). `public.positions.ts` is stored as `timestamptz` and comes back from asyncpg as a Python `datetime` object.

**How to avoid:** Normalize to ISO 8601 strings in the output. For FR: `datetime.utcfromtimestamp(row["timestamp"]).isoformat() + "Z"`. For Alison: `row["ts"].isoformat()` (asyncpg returns timezone-aware datetime).

---

## Code Examples

Verified patterns from existing code and official sources:

### Shapely Prepare + contains_xy for Multi-Point Check

```python
# Source: Shapely 2.1.2 docs (shapely.readthedocs.io/en/stable)
from shapely.geometry import Polygon
import shapely

# User polygon: [[lat, lon], [lat, lon], ...] — convert to Shapely (lon, lat) order
poly = Polygon([(pt[1], pt[0]) for pt in polygon_input])  # swap lat/lon → lon/lat
shapely.prepare(poly)  # one-time cost; amortized over all PIP checks below

for row in bbox_filtered_positions:
    lat, lon = row["lat"], row["lon"]
    if lat is None or lon is None:
        continue
    if shapely.contains_xy(poly, float(lon), float(lat)):
        # Position confirmed inside polygon
        ...
```

### shape() for GeoJSON Feature Geometry

```python
# Source: Shapely docs — shapely.geometry.shape()
from shapely.geometry import shape
import shapely

geom = shape(feature["geometry"])  # works for Polygon and MultiPolygon
shapely.prepare(geom)              # prepare for repeated PIP queries
```

### Bbox Derivation from Polygon

```python
# Source: established pattern from all_flights.py and alison_flights.py
poly_lats = [pt[0] for pt in polygon]
poly_lons = [pt[1] for pt in polygon]
bbox = {
    "min_lat": min(poly_lats), "max_lat": max(poly_lats),
    "min_lon": min(poly_lons), "max_lon": max(poly_lons),
}
```

### FR Positions Query (ordered sequence for classification)

```python
# Pattern based on get_flight_course.py
sql_fr = """
    SELECT flight_id, timestamp, lat, lon, alt, vspeed
    FROM research.normal_tracks
    WHERE flight_id = ANY(:ids)
      AND lat IS NOT NULL AND lon IS NOT NULL
      AND lat BETWEEN :min_lat AND :max_lat
      AND lon BETWEEN :min_lon AND :max_lon
    ORDER BY flight_id, timestamp
    LIMIT 200000
"""
```

### Alison Positions Query (ordered sequence for classification)

```python
sql_alison = """
    SELECT hex, ts, lat, lon, alt_baro, baro_rate, on_ground
    FROM public.positions
    WHERE hex = ANY(:ids)
      AND ts >= to_timestamp(:cutoff)
      AND lat BETWEEN :min_lat AND :max_lat
      AND lon BETWEEN :min_lon AND :max_lon
    ORDER BY hex, ts
    LIMIT 200000
"""
# Note: on_ground=True rows may have lat=None, lon=None — handled in Python
```

---

## Geo Data Research

### FIR Boundaries

**Source:** `jaluebbe/FlightMapEuropeSimple` — `flightmap_europe_fir_uir_ec_only.json`
**URL:** https://github.com/jaluebbe/FlightMapEuropeSimple
**Data provenance:** Converted from Eurocontrol `euctrl-pru/eurocontrol-atlas` shapefiles (`FirUir_NM.zip`) using ogr2ogr. Pre-converted GeoJSON is directly usable.
**Coverage:** All Eurocontrol member states (European FIRs/UIRs only — NOT global)
**Format:** GeoJSON FeatureCollection; properties include FIR designator, name, type (FIR/UIR)
**License:** Derived from Eurocontrol public data; free for non-commercial use
**Confidence:** MEDIUM — suitable for research/prototype; production use should verify AIRAC currency with Eurocontrol directly
**Phase 12 scope:** Research + loader module only; actual `country_fir` spatial mode is DEFERRED

### Land/Water Polygons

**Source:** Natural Earth Data — 1:50m Land physical vectors
**URL:** https://www.naturalearthdata.com/downloads/50m-physical-vectors/50m-land/
**GeoJSON mirror:** https://github.com/martynafford/natural-earth-geojson (pre-converted)
**Coverage:** Global land polygons including major islands
**Format:** GeoJSON FeatureCollection (can be large — 50m scale is a good balance of accuracy vs. file size for aviation use)
**License:** Public domain
**Recommendation:** Use 1:50m scale (not 1:10m which is very large). For aviation surface type determination, 50m accuracy (~1km) is sufficient to classify takeoff/landing surfaces.
**Confidence:** HIGH — well-established dataset used widely in geo applications

### Country Boundaries

**Source:** `datasets/geo-countries` — `countries.geojson`
**URL:** https://github.com/datasets/geo-countries
**Coverage:** 255 country features, global
**Format:** GeoJSON FeatureCollection; properties: `name`, `ISO3166-1-Alpha-2`, `ISO3166-1-Alpha-3`
**License:** Public Domain (Open Data Commons PDDL)
**File size:** ~20-25 MB (suitable for bundling; loads in <1s)
**Confidence:** HIGH — widely used, well-maintained, ISO-coded

### Recommended Storage Strategy

**Format:** GeoJSON files bundled in `backend/app/geo/data/` — no database required.
**Loading:** Module-level cache — load and prepare Shapely geometries once at import time. This avoids repeated file I/O and amortizes `shapely.prepare()` cost.
**Why not SQLite:** No runtime writes needed; static files are simpler, reproducible, and faster to load for read-only polygon data.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Shapely 1.x OOP-only API | Shapely 2.x vectorized ufuncs + `prepare()` | Shapely 2.0 (2022) | `contains_xy()` runs inner loop in C; no Python overhead per point |
| Manual ray-casting in Python | Shapely `contains_xy()` | Shapely 2.0+ | Correctness (handles edge cases) + 10-100x speed for large point sets |
| Downloading geo data at runtime | Bundle static GeoJSON files | Established best practice | Reproducibility; no network failures; fast startup |

---

## Open Questions

1. **Alison `on_ground` column availability**
   - What we know: CONTEXT.md describes `on_ground` boolean as present in `public.positions`; `alison_flights.py` references `alt_baro` but not `on_ground`
   - What's unclear: Whether `on_ground` is actually present in the current DB schema or was observed in raw data but not stored
   - Recommendation: The first task of Plan 01 should verify `\d public.positions` to confirm column names; add a fallback to altitude-only classification if `on_ground` is absent

2. **Alison `baro_rate` column availability**
   - What we know: Described in CONTEXT.md as available in Alison data; not referenced in any existing query
   - What's unclear: Column name in DB (`baro_rate`? `vertical_rate`?); nullable percentage
   - Recommendation: Verify in Plan 01 DB schema check; treat as supplementary signal only

3. **Position volume for FR flights in polygon**
   - What we know: `research.normal_tracks` can have many track points per flight; `get_flight_course.py` fetches all without a limit (just time-ordered)
   - What's unclear: Typical position count per flight (hundreds? thousands?); whether LIMIT 200000 is sufficient for a large polygon
   - Recommendation: Use LIMIT 200000 initially; log position counts; add warning if limit is hit

4. **FIR GeoJSON file size**
   - What we know: `jaluebbe/FlightMapEuropeSimple` repo has a pre-converted `flightmap_europe_fir_uir_ec_only.json`
   - What's unclear: Exact file size and whether it is the right granularity (FIR vs. UIR)
   - Recommendation: Download and inspect before bundling; if too large, use 110m-simplified version

---

## Implementation Plan Outline (for planner)

Phase 12 naturally splits into two parallel tracks:

**Track A: `area_spatial_filter` cube**
1. Plan 01 — Schema verification + cube skeleton
   - Verify `public.positions` columns (`on_ground`, `baro_rate`, column types)
   - Scaffold `AreaSpatialFilterCube` with provider param, polygon input, outputs
   - FR provider: bbox SQL → Shapely PIP → entry/exit time computation → movement classification
   - Alison provider: same flow with `on_ground` + `baro_rate` signals

**Track B: Geo data loader modules**
2. Plan 02 — Geo loaders
   - Download and bundle `countries.geojson`, `ne_50m_land.geojson`, `fir_uir_europe.geojson`
   - Implement `backend/app/geo/loader.py` (shared base)
   - Implement `country_loader.py`, `fir_loader.py`, `land_water_loader.py`
   - Each loader: load JSON, build name→prepared_Shapely_polygon index, expose `get_polygon(name)` and `classify_point(lat, lon)` functions

---

## Sources

### Primary (HIGH confidence)
- Existing project code (`all_flights.py`, `alison_flights.py`, `squawk_filter.py`, `registration_country_filter.py`) — established patterns for dual-provider, polygon filtering, bbox pre-filter
- `backend/pyproject.toml` — confirms Shapely 2.1.2 is already installed
- Shapely 2.1.2 official docs (shapely.readthedocs.io) — `contains_xy()`, `prepare()`, `STRtree`, `shape()`

### Secondary (MEDIUM confidence)
- `datasets/geo-countries` GitHub (github.com/datasets/geo-countries) — GeoJSON structure, property names, license
- Natural Earth Data (naturalearthdata.com) — land polygon availability, 50m scale, public domain
- `jaluebbe/FlightMapEuropeSimple` GitHub — pre-converted FIR GeoJSON from Eurocontrol shapefiles

### Tertiary (LOW confidence — needs runtime verification)
- Alison DB schema details (`on_ground`, `baro_rate` column existence) — referenced in CONTEXT.md but not verified against live DB schema
- FIR GeoJSON file size and coverage completeness — not downloaded; needs inspection before bundling

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Shapely already installed; SQLAlchemy pattern established; no new dependencies needed
- Architecture: HIGH — directly follows SquawkFilter and icao24_lookup templates already in codebase
- Geo datasets: MEDIUM — sources identified and well-documented; actual files not yet inspected
- Movement classification logic: MEDIUM — signals described in CONTEXT.md are not yet schema-verified against live DB

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable domain — Shapely API, geo datasets, DB schema unlikely to change)
