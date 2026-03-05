# Phase 9: Filter Flights Cube (Gap Closure) - Research

**Researched:** 2026-03-05
**Domain:** Python cube implementation — behavioral flight filtering against PostgreSQL track data
**Confidence:** HIGH

## Summary

Phase 9 closes the last two open v1 requirements (DATA-02, DATA-05) by implementing a Filter Flights cube that sits between AllFlights and GetAnomalies in the 4-cube reference pipeline. The implementation is well-scoped: it follows an identical structural pattern to the existing AllFlights cube, uses the already-present `point_in_polygon` helper, and adds no new infrastructure.

The entire implementation is a single new file (`backend/app/cubes/filter_flights.py`) plus any output adjustments to `all_flights.py` that prove necessary. A two-tier query strategy (cheap metadata duration check first, expensive normal_tracks aggregate query only for survivors) keeps the cube fast at scale. All design decisions were locked in CONTEXT.md during discussion, so no alternative research is needed.

**Primary recommendation:** Implement FilterFlightsCube in `backend/app/cubes/filter_flights.py`, import `point_in_polygon` from `all_flights.py` (or extract to a shared `utils.py`), and use a single aggregation SQL query (GROUP BY + MIN/MAX) for Tier 2 rather than fetching raw track points.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Filter logic**
- AND logic — every active threshold must pass for a flight to be included
- Flights with no track data in normal_tracks are excluded (no data = can't verify = skip)
- All threshold params are optional — only active ones are evaluated

**Input design**
- Accepts `full_result` from AllFlights (accepts_full_result: true) — gets the flights array + flight_ids
- Also accepts individual filter params: max_altitude_ft, min_speed_knots, max_speed_knots, min_duration_minutes, max_duration_minutes
- Polygon input (JSON_OBJECT, widget_hint: polygon) for geofence — same pattern as AllFlights

**Performance strategy — two-tier filtering**
- Tier 1 (cheap — flight_metadata via full_result): Duration filtering uses first_seen_ts/last_seen_ts from the AllFlights full_result data. Filter out flights by duration BEFORE querying normal_tracks.
- Tier 2 (expensive — normal_tracks query): Only query track data for flights that survived Tier 1. Use SQL-level GROUP BY aggregation (MIN/MAX alt, MIN/MAX gspeed) rather than fetching all points to Python. Polygon check requires per-point evaluation — use bounding box SQL pre-filter + Python ray-casting (same pattern as AllFlights).

**Polygon filtering**
- Same approach as AllFlights: bounding box SQL pre-filter on lat/lon, then Python-side ray-casting per track point
- A flight passes if ANY of its track points falls inside the polygon (flight traversed the area)
- Reuse the existing `point_in_polygon` function from all_flights.py (or extract to shared util)

**Output shape**
- `filtered_flight_ids`: LIST_OF_STRINGS — flight_ids that passed all filters
- `filtered_flights`: JSON_OBJECT — the full flight metadata rows from the input full_result, filtered down to passing flights (preserves all columns from AllFlights output)
- No new columns added — the output is a subset of the input data

**Duration source**
- Duration computed from flight_metadata first_seen_ts/last_seen_ts (available in AllFlights full_result)
- Verified: timestamps match normal_tracks MIN/MAX to within 0.0 minutes on live data
- No need to query normal_tracks for duration — saves a round trip

**Track data units**
- alt column: feet (verified: max ~38,000 for commercial flights)
- gspeed column: knots (verified: max ~555 for jets)
- These match the param names (max_altitude_ft, min_speed_knots, max_speed_knots)

### Claude's Discretion

None stated explicitly — all key decisions were locked in discussion.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-02 | Filter Flights cube accepts flight_ids, queries research.normal_tracks to evaluate behavioral criteria (max_altitude_ft, min_speed_knots, max_speed_knots, min_duration_minutes, max_duration_minutes), excludes flights whose track data violates thresholds; outputs filtered_flight_ids and filtered_flights metadata | Two-tier query pattern documented below. SQL GROUP BY aggregate handles altitude/speed. Duration from flight_metadata Tier 1. |
| DATA-05 | End-to-end pipeline: Get Flights → Filter Flights → Get Anomalies + Count By Field produces real results from live database | Pipeline compatibility verified: AllFlights outputs flight_ids (LIST_OF_STRINGS) and flights (JSON_OBJECT) via __full_result__; GetAnomalies accepts flight_ids (LIST_OF_STRINGS); CountByField accepts any data via full_result. No integration gaps. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy (asyncpg) | Already installed | Async database access | Used by every existing cube |
| BaseCube | In-project | Cube contract + auto full_result output | Required for auto-discovery and catalog |
| ParamType / CubeCategory | In-project schemas | Type-safe parameter definitions | Used by all cubes |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python stdlib typing | stdlib | Type hints | Always |
| logging | stdlib | Structured debug logging | AllFlights pattern — log full SQL before execution |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQL GROUP BY aggregate | Fetch all rows to Python + groupby | SQL aggregate is 10-100x faster; don't hand-roll aggregation for track data |
| Python ray-casting for polygon | PostGIS ST_Contains | PostGIS not on Tracer 42 RDS — ray-casting is the only option |
| Import point_in_polygon from all_flights | Copy-paste the function | Import is cleaner; if refactoring is needed, extract to shared utils.py |

**Installation:** No new packages required. All dependencies are already present.

## Architecture Patterns

### Recommended Project Structure
```
backend/app/cubes/
├── base.py               # BaseCube abstract class (unchanged)
├── all_flights.py        # May expose point_in_polygon for import
├── filter_flights.py     # NEW — FilterFlightsCube
├── get_anomalies.py      # Downstream consumer (unchanged)
├── count_by_field.py     # Downstream consumer (unchanged)
└── ...
```

### Pattern 1: Two-Tier Execute Flow

**What:** Separate filtering into cheap metadata-only pass (Tier 1) and expensive DB query pass (Tier 2).

**When to use:** Whenever a cube has multiple filter criteria with very different costs.

**Example:**
```python
async def execute(self, **inputs: Any) -> dict[str, Any]:
    full_result = inputs.get("full_result_param_name")  # receives AllFlights __full_result__

    # ── Extract flights + flight_ids from full_result ──────────────────────────
    all_flight_rows: list[dict] = []
    if isinstance(full_result, dict):
        all_flight_rows = full_result.get("flights") or full_result.get("flight_ids") or []
        flight_ids = full_result.get("flight_ids") or []
    else:
        # Fallback: direct flight_ids input
        flight_ids = list(inputs.get("flight_ids") or [])
        all_flight_rows = []  # no metadata available

    # ── Tier 1: Duration filter (free — from metadata) ────────────────────────
    min_dur = inputs.get("min_duration_minutes")
    max_dur = inputs.get("max_duration_minutes")
    tier1_ids = set(flight_ids)
    if (min_dur is not None or max_dur is not None) and all_flight_rows:
        surviving = []
        for row in all_flight_rows:
            first_ts = row.get("first_seen_ts")
            last_ts = row.get("last_seen_ts")
            if first_ts is None or last_ts is None:
                continue  # exclude flights with no timestamp data
            duration_min = (last_ts - first_ts) / 60.0
            if min_dur is not None and duration_min < min_dur:
                continue
            if max_dur is not None and duration_min > max_dur:
                continue
            surviving.append(row["flight_id"])
        tier1_ids = set(surviving)

    if not tier1_ids:
        return {"filtered_flight_ids": [], "filtered_flights": []}

    # ── Tier 2: Track data filter (expensive — SQL aggregate) ─────────────────
    # ... (see Pattern 2 below)
```

### Pattern 2: SQL GROUP BY Aggregate for Track Stats

**What:** Pull MIN/MAX altitude and speed per flight in one SQL query. One row per flight, not one row per track point.

**When to use:** Any cube that needs per-flight statistics from normal_tracks without needing the individual points.

**Example:**
```python
# Source: existing codebase pattern — engine.connect() direct usage
async with engine.connect() as conn:
    result = await conn.execute(
        text("""
            SELECT flight_id,
                   MIN(alt)    AS min_alt,
                   MAX(alt)    AS max_alt,
                   MIN(gspeed) AS min_speed,
                   MAX(gspeed) AS max_speed
            FROM research.normal_tracks
            WHERE flight_id = ANY(:flight_ids)
            GROUP BY flight_id
        """),
        {"flight_ids": list(tier1_ids)},
    )
    track_stats = {row[0]: dict(zip(result.keys(), row)) for row in result.fetchall()}

# Flights absent from track_stats have no track data → exclude them
passing_ids: set[str] = set()
for fid in tier1_ids:
    stats = track_stats.get(fid)
    if stats is None:
        continue  # no track data → exclude
    max_alt_ft = inputs.get("max_altitude_ft")
    min_spd = inputs.get("min_speed_knots")
    max_spd = inputs.get("max_speed_knots")
    if max_alt_ft is not None and (stats["max_alt"] or 0) > max_alt_ft:
        continue
    if min_spd is not None and (stats["max_speed"] or 0) < min_spd:
        continue
    if max_spd is not None and (stats["min_speed"] or 0) > max_spd:
        continue
    passing_ids.add(fid)
```

### Pattern 3: Polygon Filtering (Reused from AllFlights)

**What:** Bounding box SQL pre-filter on lat/lon, then Python-side ray-casting per track point. Early-exit per flight once confirmed inside polygon.

**When to use:** Geofence filtering when PostGIS is unavailable.

**Example:**
```python
# Source: all_flights.py lines 282–324 — proven production pattern
from app.cubes.all_flights import point_in_polygon  # or extract to utils.py

polygon = inputs.get("polygon")
if polygon and len(polygon) >= 3 and passing_ids:
    poly_lats = [p[0] for p in polygon]
    poly_lons = [p[1] for p in polygon]
    async with engine.connect() as conn:
        track_result = await conn.execute(
            text(
                "SELECT flight_id, lat, lon "
                "FROM research.normal_tracks "
                "WHERE flight_id = ANY(:ids) "
                "AND lat BETWEEN :bbox_min_lat AND :bbox_max_lat "
                "AND lon BETWEEN :bbox_min_lon AND :bbox_max_lon"
            ),
            {
                "ids": list(passing_ids),
                "bbox_min_lat": min(poly_lats),
                "bbox_max_lat": max(poly_lats),
                "bbox_min_lon": min(poly_lons),
                "bbox_max_lon": max(poly_lons),
            },
        )
        track_rows = track_result.fetchall()

    flights_in_polygon: set[str] = set()
    for fid, lat, lon in track_rows:
        if fid in flights_in_polygon:
            continue
        if lat is not None and lon is not None:
            if point_in_polygon(float(lat), float(lon), polygon):
                flights_in_polygon.add(fid)

    passing_ids = passing_ids & flights_in_polygon
```

### Pattern 4: full_result Input Extraction

**What:** When a cube declares an input with `accepts_full_result: True`, the executor passes the entire output dict of the upstream cube as the param value.

**How the executor delivers it:** `resolve_inputs` in executor.py line 79 bundles all source outputs into a single dict when `sourceHandle == "__full_result__"`. So if AllFlights outputs `{flights: [...], flight_ids: [...]}`, the receiving param gets exactly that dict.

**Example input param definition:**
```python
ParamDefinition(
    name="full_result",          # arbitrary name — matches what the cube reads from inputs
    type=ParamType.JSON_OBJECT,
    description="Full result from AllFlights — provides flights array and flight_ids.",
    required=False,
    accepts_full_result=True,
),
```

**Extraction in execute():**
```python
full_result = inputs.get("full_result")  # dict: {"flights": [...], "flight_ids": [...]}
if isinstance(full_result, dict):
    all_flight_rows = full_result.get("flights", [])
    flight_ids = full_result.get("flight_ids", [])
```

### Pattern 5: Empty Input Guard

**What:** Guard against empty flight_ids before any SQL query. PostgreSQL `ANY()` with empty array can cause type errors.

**Example (from get_anomalies.py):**
```python
flight_ids = inputs.get("flight_ids") or []
# ... resolve from full_result ...
if not flight_ids:
    return {"filtered_flight_ids": [], "filtered_flights": []}
```

### Anti-Patterns to Avoid

- **Fetching all track points for altitude/speed stats:** Brings thousands of rows to Python per flight. Use SQL GROUP BY instead.
- **Querying normal_tracks before Tier 1 duration filter:** Defeats the performance purpose. Always filter by metadata first.
- **Missing empty-flight-ids guard:** Causes PostgreSQL type error with `ANY()` on empty array — seen and fixed in GetAnomalies.
- **Hardcoding LIMIT on the track aggregate query:** The aggregate query returns one row per flight, not per point — no LIMIT needed on the GROUP BY query itself. The outer result is bounded by the input flight_ids count.
- **Using `pip` or `poetry`:** Project uses `uv` only.
- **Assuming PostGIS availability:** Tracer 42 RDS does not have PostGIS — must use Python ray-casting.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Point-in-polygon test | Custom geometric logic | `point_in_polygon()` from all_flights.py | Already tested in production; ray-casting is correct for planar coordinates |
| Per-flight track aggregation | Loop + Python min/max | SQL `GROUP BY flight_id` + `MIN/MAX` | 10-100x faster; avoids fetching all track points to Python |
| Cube registration | Manual registry entries | BaseCube auto-discovery (subclasses) | CubeRegistry uses `__subclasses__()` — just import the module |
| Duration calculation | Query normal_tracks timestamps | first_seen_ts/last_seen_ts from AllFlights full_result | Already verified accurate; saves a DB round trip |

**Key insight:** This cube is intentionally a filter, not a data fetcher. Its job is to narrow down flight_ids using existing data, not to enrich or transform. Keep the output shape simple — a subset of the input.

## Common Pitfalls

### Pitfall 1: Speed Filter Semantics
**What goes wrong:** Applying `min_speed_knots` check against `MIN(gspeed)` instead of `MAX(gspeed)`. A flight "goes fast enough" if its maximum speed exceeds the threshold, not its minimum.
**Why it happens:** Naming ambiguity — "min speed" could be read as the floor the flight must reach, or the minimum observed speed.
**How to avoid:**
- `min_speed_knots`: flight must have at least one point at or above this speed → check `MAX(gspeed) >= min_speed_knots`
- `max_speed_knots`: flight must never exceed this speed → check `MAX(gspeed) <= max_speed_knots` (or `MIN(gspeed)` — depends on intent; using MAX is conservative)
**Warning signs:** Tests pass numerically but reject flights that visually appear to meet criteria.

### Pitfall 2: full_result Shape Dependency
**What goes wrong:** Hardcoding key names when extracting from full_result. If AllFlights output names ever change, silent empty results.
**Why it happens:** Trusting implicit contracts.
**How to avoid:** Add debug logging when full_result is received but yields empty flights. Document that this cube expects `flights` and `flight_ids` keys from AllFlights specifically.

### Pitfall 3: None gspeed/alt Values
**What goes wrong:** Track rows may have NULL values for alt or gspeed (sparse data, ADS-B gaps). Comparing None to a threshold raises TypeError.
**Why it happens:** PostgreSQL NULL becomes Python None. SQLAlchemy does not coerce NULLs automatically.
**How to avoid:** Use `(stats["max_alt"] or 0)` coercion for NULL-safe comparisons. Or use `COALESCE(MAX(alt), 0)` in the SQL aggregate.

### Pitfall 4: Polygon with No Tier-2 Survivors
**What goes wrong:** Running the polygon track query against an empty set after Tier-2 aggregate filtering eliminates all flights.
**Why it happens:** Not checking if `passing_ids` is empty before the polygon query.
**How to avoid:** Guard `if polygon and len(polygon) >= 3 and passing_ids:` before the polygon SQL call — same pattern used in allFlights.

### Pitfall 5: allFlights Output Compatibility
**What goes wrong:** AllFlights uses `full_result` via `__full_result__` bundle — the receiving param must use the exact key name `full_result` (or whatever name the planner chooses) AND declare `accepts_full_result: True`. If `accepts_full_result` is False, the executor validation may warn or block the connection.
**Why it happens:** The executor validates full_result connections (BACK-09).
**How to avoid:** Declare the AllFlights-receiving param with `accepts_full_result=True`. Verify in catalog that it appears correctly.

## Code Examples

Verified patterns from official sources:

### Complete ParamDefinition Block for FilterFlightsCube

```python
# Source: schemas/cube.py + established patterns from all_flights.py and get_anomalies.py
inputs = [
    ParamDefinition(
        name="full_result",
        type=ParamType.JSON_OBJECT,
        description="Full result from AllFlights — provides flights array and flight_ids.",
        required=False,
        accepts_full_result=True,
    ),
    ParamDefinition(
        name="flight_ids",
        type=ParamType.LIST_OF_STRINGS,
        description="Direct flight_ids input (alternative to full_result connection).",
        required=False,
    ),
    ParamDefinition(
        name="max_altitude_ft",
        type=ParamType.NUMBER,
        description="Maximum altitude in feet. Flights with any track point above this are excluded.",
        required=False,
    ),
    ParamDefinition(
        name="min_speed_knots",
        type=ParamType.NUMBER,
        description="Minimum speed in knots. Flights that never reach this speed are excluded.",
        required=False,
    ),
    ParamDefinition(
        name="max_speed_knots",
        type=ParamType.NUMBER,
        description="Maximum speed in knots. Flights that exceed this speed are excluded.",
        required=False,
    ),
    ParamDefinition(
        name="min_duration_minutes",
        type=ParamType.NUMBER,
        description="Minimum flight duration in minutes. Flights shorter than this are excluded.",
        required=False,
    ),
    ParamDefinition(
        name="max_duration_minutes",
        type=ParamType.NUMBER,
        description="Maximum flight duration in minutes. Flights longer than this are excluded.",
        required=False,
    ),
    ParamDefinition(
        name="polygon",
        type=ParamType.JSON_OBJECT,
        description="Array of [lat, lon] coordinate pairs defining a geofence. Only flights with track points inside are kept.",
        required=False,
        widget_hint="polygon",
    ),
]

outputs = [
    ParamDefinition(
        name="filtered_flight_ids",
        type=ParamType.LIST_OF_STRINGS,
        description="Flight IDs that passed all active filters.",
    ),
    ParamDefinition(
        name="filtered_flights",
        type=ParamType.JSON_OBJECT,
        description="Full metadata rows for passing flights (subset of AllFlights output).",
    ),
]
```

### Duration Calculation (Tier 1)

```python
# Source: CONTEXT.md verified live data — first_seen_ts/last_seen_ts are epoch seconds integers
duration_min = (last_ts - first_ts) / 60.0  # seconds → minutes
```

### Tier 2 SQL Aggregate Query

```python
# Source: research.normal_tracks schema documented in CONTEXT.md
# alt = feet, gspeed = knots
sql = """
    SELECT flight_id,
           MIN(alt)    AS min_alt_ft,
           MAX(alt)    AS max_alt_ft,
           MIN(gspeed) AS min_speed_kt,
           MAX(gspeed) AS max_speed_kt
    FROM research.normal_tracks
    WHERE flight_id = ANY(:flight_ids)
    GROUP BY flight_id
"""
```

### Auto-Discovery Registration

```python
# Source: engine/registry.py pattern — no manual registration needed
# Just ensure the module is importable. CubeRegistry uses BaseCube.__subclasses__() after import.
# The cubes/__init__.py must import filter_flights:
from app.cubes import filter_flights  # triggers subclass registration
```

Check `backend/app/cubes/__init__.py` to confirm it auto-imports all modules. If not, add the import there.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fetch all track points for stats | SQL GROUP BY aggregate | This phase (new) | Avoids N×1500-2000 rows in Python memory per flight |
| PostGIS for polygon | Python ray-casting | Phase 2 decision | Permanent — PostGIS not on RDS |
| Manual cube registration | BaseCube.__subclasses__() | Phase 2 | Zero-registration — add file, add import, done |

**No deprecated patterns apply to this phase.**

## Open Questions

1. **`point_in_polygon` import vs. shared util**
   - What we know: Function lives in `all_flights.py`. Can be imported directly.
   - What's unclear: Whether the team prefers a `utils.py` extraction for cleanliness.
   - Recommendation: Import directly from `all_flights.py` for Phase 9. Extraction to `utils.py` is a future refactor if more cubes need it — not required for correctness now.

2. **AllFlights output key for polygon-filtered flights**
   - What we know: AllFlights outputs `flights` and `flight_ids`. The `full_result` input on FilterFlights receives the entire output dict.
   - What's unclear: Whether AllFlights needs any output adjustments (e.g., exposing bounding box data to FilterFlights).
   - Recommendation: No adjustments needed. AllFlights output already contains `first_seen_ts`, `last_seen_ts` in the flights rows — sufficient for Tier 1.

3. **cubes/__init__.py auto-import**
   - What we know: CubeRegistry uses `__subclasses__()` after pkgutil import cycle.
   - What's unclear: Whether adding `filter_flights.py` alone is sufficient or requires explicit `__init__.py` import.
   - Recommendation: Check the existing `__init__.py` before implementing. Add import if needed.

## Sources

### Primary (HIGH confidence)
- In-codebase: `backend/app/cubes/all_flights.py` — polygon pattern, point_in_polygon, SQL style
- In-codebase: `backend/app/cubes/get_anomalies.py` — empty guard pattern, flight_ids query
- In-codebase: `backend/app/engine/executor.py` — full_result resolution (lines 79–83)
- In-codebase: `backend/app/schemas/cube.py` — ParamType, CubeCategory, ParamDefinition, accepts_full_result
- In-codebase: `backend/app/cubes/base.py` — BaseCube contract, full_result auto-append
- `.planning/phases/09-filter-flights-cube/09-CONTEXT.md` — locked decisions from user discussion

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` — DATA-02, DATA-05 requirement text
- `.planning/STATE.md` — Phase 02 decisions: engine.connect() pattern, polygon ray-casting decision

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — identical to existing cubes, no new libraries
- Architecture: HIGH — two-tier pattern derived from CONTEXT.md + existing code review
- Pitfalls: HIGH — identified from code inspection (NULL handling, speed semantics) and existing codebase bugs fixed in prior phases (empty flight_ids guard)

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable — no external dependencies, all internal)
