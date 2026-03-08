# Phase 14: Signal Health Analyzer - Research

**Researched:** 2026-03-08
**Domain:** GPS anomaly detection cube — porting proven detection scripts (psycopg/sync) to async SQLAlchemy backend module
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Two detection layers**, both required:
  1. Rule-based (from `detect_rule_based.py`): `detect_integrity_events()`, `detect_transponder_shutdowns()`, `score_event()`, `classify_event()`, `build_coverage_baseline()`
  2. Kalman (from `detect_kalman.py`): `kalman_filter()`, `detect_position_jumps()`, `detect_altitude_divergence()`, `physics_cross_validation()`, `classify_flight()`
- **Alison provider only** — queries `public.positions` with all listed columns
- **Read-only** — no writes to any DB tables
- Detection logic copied faithfully from `scripts/` — same constants, thresholds, and scoring logic
- Results returned in-memory as cube outputs
- Coverage baseline query runs against `public.positions`
- Cube inputs: `hex_list`, `full_result`, `target_phase`, `classify_mode`
- Cube outputs: `flight_ids`, `count`, `events`, `stats_summary`, plus auto Full Result
- Architecture: detection modules go in `backend/app/signal/`, cube goes in `backend/app/cubes/`
- New dependencies: numpy, scipy (for Kalman filter)

### Claude's Discretion

- Exact module structure within `backend/app/signal/`
- How to handle coverage baseline caching (build once per execution vs per hex)
- `target_phase` filtering implementation (altitude-based flight phase segmentation)
- Performance: whether to batch hexes or process one at a time
- How to handle `classify_mode=["all"]` vs specific category filters

### Deferred Ideas (OUT OF SCOPE)

- FR provider support (research.normal_tracks)
- Writing detection results to DB tables (rule_based_events, kalman_events)
- Scheduled/batch detection runs
- Additional classification categories or scoring adjustments
</user_constraints>

---

## Summary

Phase 14 ports two proven GPS anomaly detection modules from `scripts/` into the backend's async architecture and wraps them in a `SignalHealthAnalyzerCube`. The scripts use synchronous `psycopg` connections; the backend uses `asyncpg` via SQLAlchemy async engine. The core detection logic (constants, thresholds, scoring algorithms, Kalman math) is copied verbatim — only the DB access layer changes from sync `psycopg.connection.cursor()` to async `engine.connect()` with `text()` queries.

The main complexity in this phase is the impedance mismatch between the sync scripts and the async backend: the Kalman filter and rule-based functions are CPU-bound pure Python (they receive already-fetched data), so they need no async changes — only the SQL fetch functions need to be adapted to async SQLAlchemy. The cube must orchestrate: build coverage baseline once, then for each hex run rule-based detection and Kalman analysis in sequence (or batched), merge events, apply `classify_mode` filtering, and return structured outputs.

The coverage baseline (`build_coverage_baseline`) is the single most expensive operation (~30s on 30 days of data). The recommended approach is to build it once per cube execution (not per hex) and cache the result in a module-level variable with a TTL, avoiding repeated multi-second queries when multiple cubes or repeated executions are involved.

**Primary recommendation:** Port scripts faithfully with minimal changes. The only mandatory transformation is sync psycopg cursor API → async SQLAlchemy `text()` + `conn.execute()`. Keep all detection logic, constants, and thresholds identical to scripts.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | (new dep) | Array ops for Kalman filter (latlon_to_enu, matrix ops) | Required by detect_kalman.py |
| scipy | (new dep) | `scipy.linalg.inv` for Kalman innovation matrix inversion | Required by detect_kalman.py |
| sqlalchemy[asyncio] | >=2.0 (already in pyproject.toml) | Async DB access pattern already established | All cubes use this |
| asyncpg | >=0.30 (already in pyproject.toml) | Async PostgreSQL driver | All cubes use this |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| math | stdlib | haversine distance in detect_kalman.py | Already used in scripts |
| collections.Counter | stdlib | Event category tallying for stats_summary | Simple category counting |
| asyncio | stdlib | `asyncio.to_thread()` for CPU-bound Kalman/numpy if needed | If blocking becomes an issue |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| scipy.linalg.inv | numpy.linalg.inv | scipy.linalg.inv is what the script already uses; no reason to change |
| module-level TTL cache | per-request baseline | Per-request is 30s overhead; TTL cache amortizes cost |
| asyncio.to_thread for CPU | direct await | Kalman is fast (<1s per flight); no need for thread offload unless hex_list > ~100 |

**Installation:**
```bash
cd backend && uv add numpy scipy
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/app/
├── cubes/
│   └── signal_health_analyzer.py   # SignalHealthAnalyzerCube
├── signal/
│   ├── __init__.py                  # package marker
│   ├── rule_based.py               # ported from scripts/detect_rule_based.py
│   └── kalman.py                   # ported from scripts/detect_kalman.py
```

The `signal/` module mirrors the `geo/` module pattern established in Phase 12: domain logic lives outside `cubes/`, the cube just orchestrates.

### Pattern 1: Async DB Fetch Replacing Sync psycopg

**What:** Every function that calls `conn.cursor().execute(...)` and `cur.fetchall()` must be replaced with async SQLAlchemy `engine.connect()` and `text()`.

**When to use:** All DB-touching functions in `rule_based.py` and `kalman.py`. The pure-computation functions (kalman_filter, detect_position_jumps, detect_altitude_divergence, physics_cross_validation, score_event, classify_event, classify_flight) need NO changes since they receive already-fetched Python dicts.

**Example — sync psycopg (scripts):**
```python
# Source: scripts/detect_kalman.py lines 82-102
def fetch_positions(conn: psycopg.Connection, hex_code: str,
                    start_ts: datetime, end_ts: datetime) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT ts, lat, lon, alt_baro, alt_geom, gs, tas, track, true_heading,
               nac_p, nic, baro_rate, geom_rate, on_ground
        FROM positions
        WHERE hex = %(hex)s
          AND source_type = 'adsb_icao'
          AND on_ground = false
          AND lat IS NOT NULL
          AND ts >= %(start)s AND ts <= %(end)s
        ORDER BY ts
    """, {"hex": hex_code, "start": start_ts, "end": end_ts})
    cols = [d[0] for d in cur.description]
    rows = []
    for row in cur.fetchall():
        rows.append(dict(zip(cols, row)))
    return rows
```

**Example — async SQLAlchemy (target pattern):**
```python
# Source: Pattern from backend/app/cubes/alison_flights.py lines 218-221
from sqlalchemy import text
from app.database import engine

async def fetch_positions(hex_code: str,
                          start_ts: datetime, end_ts: datetime) -> list[dict]:
    sql = text("""
        SELECT ts, lat, lon, alt_baro, alt_geom, gs, tas, track, true_heading,
               nac_p, nic, baro_rate, geom_rate, on_ground
        FROM positions
        WHERE hex = :hex
          AND source_type = 'adsb_icao'
          AND on_ground = false
          AND lat IS NOT NULL
          AND ts >= :start AND ts <= :end
        ORDER BY ts
    """)
    async with engine.connect() as conn:
        result = await conn.execute(sql, {"hex": hex_code, "start": start_ts, "end": end_ts})
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]
```

Key differences:
- `%(hex)s` → `:hex` (SQLAlchemy named params vs psycopg format)
- `conn.cursor().execute(...)` → `await conn.execute(text(...))`
- `async with engine.connect() as conn:` — no connection argument passed in
- No cursor needed — `result.keys()` gives column names directly

### Pattern 2: Coverage Baseline Caching

**What:** Build coverage baseline once per module lifetime (or with TTL), not once per hex.

**When to use:** `build_coverage_baseline()` is the only function that aggregates 30 days of global position data (~30s query). All other queries are scoped to a specific hex and a narrow time window.

**Example:**
```python
# Source: Pattern from backend/app/geo/ module (Phase 12 precedent)
import time
from typing import Any

_baseline_cache: dict[tuple[float, float], dict[str, Any]] | None = None
_baseline_ts: float = 0.0
_BASELINE_TTL = 3600.0  # 1 hour in seconds

async def get_coverage_baseline() -> dict[tuple[float, float], dict[str, Any]]:
    global _baseline_cache, _baseline_ts
    now = time.monotonic()
    if _baseline_cache is None or (now - _baseline_ts) > _BASELINE_TTL:
        _baseline_cache = await build_coverage_baseline()
        _baseline_ts = now
    return _baseline_cache
```

### Pattern 3: Cube Orchestration — Per-Hex Analysis

**What:** The cube's `execute()` method iterates `hex_list`, runs both detection layers per hex, merges events, filters by `classify_mode`.

**When to use:** Phase 14 is on-demand/interactive (not batch), so per-hex is fine. For large hex_list (>50), batch fetching positions in one query (like `detect_batch.py`'s `fetch_positions_batch`) would be more efficient.

**Example:**
```python
# Source: Pattern from scripts/detect_batch.py lines 521-550 (get_kalman_candidates)
async def execute(self, **inputs: Any) -> dict[str, Any]:
    hex_list = inputs.get("hex_list") or []
    classify_mode = inputs.get("classify_mode") or ["all"]

    # Build coverage baseline once (cached)
    coverage = await get_coverage_baseline()

    all_events = []
    for hex_code in hex_list:
        # Rule-based: transponder shutdowns + integrity events
        rule_events = await analyze_flight_rule_based(hex_code, coverage)
        # Kalman: position jumps, alt divergence, physics
        kalman_result = await analyze_flight_kalman(hex_code)
        # Merge
        all_events.extend(rule_events)
        if kalman_result["classification"] != "normal":
            all_events.append(kalman_event_from_result(hex_code, kalman_result))

    # Filter by classify_mode
    filtered = filter_by_classify_mode(all_events, classify_mode)

    # Build outputs
    ...
```

### Pattern 4: classify_mode Filtering

**What:** User selects human-facing labels; cube maps them to internal categories.

**When to use:** Always applied after merging all events. `["all"]` returns all non-normal events without filtering.

**Example:**
```python
# Source: CONTEXT.md — Classification Mapping section
CLASSIFY_MODE_MAP = {
    "Stable":         set(),  # normal — no non-normal events
    "Jamming":        {"gps_jamming", "probable_jamming"},
    "Spoofing":       {"gps_spoofing"},
    "Dark Target":    {"transponder_off"},
    "Technical Gaps": {"coverage_hole", "ambiguous"},
}

def filter_by_classify_mode(
    events: list[dict],
    classify_mode: list[str],
) -> list[dict]:
    if "all" in classify_mode:
        return events  # no filtering
    wanted: set[str] = set()
    for label in classify_mode:
        wanted.update(CLASSIFY_MODE_MAP.get(label, set()))
    return [ev for ev in events if ev.get("category") in wanted
            or ev.get("classification") in wanted]
```

### Pattern 5: Kalman Event Shape for Cube Output

**What:** Kalman analysis returns a per-flight classification dict; the cube must translate it to the unified event schema alongside rule-based events.

**When to use:** Only when Kalman classification is non-normal (anomalous or gps_spoofing).

**Example:**
```python
# Source: detect_batch.py lines 620-644 (run_kalman_batch event construction)
def kalman_event_from_result(hex_code: str, result: dict) -> dict:
    """Convert Kalman analysis result to unified event schema."""
    kr = result["kalman_results"]
    n_flagged = sum(1 for r in kr if r["flagged"])
    n_kalman = len(kr)
    flag_pct = (n_flagged / n_kalman * 100) if n_kalman else 0.0
    alt_div = result["alt_divergence"]
    positions = result.get("positions", [])
    return {
        "hex": hex_code,
        "category": result["classification"],       # gps_spoofing or anomalous
        "classification": result["classification"],  # Kalman-specific field
        "start_ts": result["start"].isoformat() if result.get("start") else None,
        "end_ts": result["end"].isoformat() if result.get("end") else None,
        "duration_s": (result["end"] - result["start"]).total_seconds()
                       if result.get("start") and result.get("end") else None,
        "entry_lat": positions[0]["lat"] if positions else None,
        "entry_lon": positions[0]["lon"] if positions else None,
        "exit_lat": positions[-1]["lat"] if positions else None,
        "exit_lon": positions[-1]["lon"] if positions else None,
        # Kalman-specific metrics
        "n_flagged": n_flagged,
        "flag_pct": round(flag_pct, 2),
        "n_jumps": len(result["jumps"]),
        "n_alt_divergence": len(alt_div),
        "physics_confidence": result["physics"].get("confidence", 0.0),
        # Rule-based fields (null for Kalman events)
        "jamming_score": None,
        "spoofing_score": None,
        "coverage_score": None,
        "evidence": None,
    }
```

### Anti-Patterns to Avoid

- **Passing conn as argument:** Async SQLAlchemy engine connections are acquired inside each function with `async with engine.connect()`. Do not try to pass a single connection across functions — each async function opens its own connection from the pool.
- **Using psycopg param syntax:** `%(hex)s` is psycopg format. SQLAlchemy `text()` uses `:hex` named params. Using psycopg syntax with SQLAlchemy will silently fail or raise.
- **Building coverage baseline per-hex:** A 30-day global aggregate query run for each of 50+ hexes would be catastrophically slow. Build once and cache.
- **Running Kalman on all hexes:** Follow the `get_kalman_candidates()` pattern from detect_batch.py — only run Kalman on hexes that had rule-based events or NACp=0. This is a performance optimization that can be applied even for interactive use.
- **Using `run_in_executor` for Kalman math:** The numpy/scipy Kalman computation is fast (<<1s per flight). Do not over-engineer with thread pools unless profiling shows otherwise.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GPS spoofing detection algorithm | Custom chi-squared filter | `kalman_filter()` from `scripts/detect_kalman.py` | Proven, tested against known spoofing cases (717ce7, 151d8a) |
| Integrity event detection | Custom NACp/NIC parser | `detect_integrity_events()` from `scripts/detect_rule_based.py` | Version-aware (V0/V1/V2) with correct field weights |
| Event scoring | Custom scoring system | `score_event()` + `classify_event()` | 16-point evidence system tuned against real data |
| Coverage hole baseline | Custom grid builder | `build_coverage_baseline()` | 0.5-degree grid with median RSSI, reports/hour, temporal coverage |
| Matrix inversion | Custom inverse | `scipy.linalg.inv` | Numerically stable for 2x2 innovation matrices |
| Coordinate conversion | Custom haversine | `latlon_to_enu()` + `haversine_km()` | Already correct in scripts |

**Key insight:** All detection logic is proven against a known test suite (7 test cases in both detect_rule_based.py and detect_kalman.py covering spoofing, jamming, normal, transponder-off). Port faithfully — do not reimplement.

---

## Common Pitfalls

### Pitfall 1: psycopg param syntax vs SQLAlchemy text() syntax

**What goes wrong:** Copied SQL from scripts uses `%(hex)s` (psycopg format) but SQLAlchemy `text()` requires `:hex` (named params). This causes `ProgrammingError` or silent empty results.

**Why it happens:** The scripts and backend use different DB drivers.

**How to avoid:** Do a global search-replace `%(` → `:` and `)s` → `` in every SQL string during porting. Then test each query.

**Warning signs:** `sqlalchemy.exc.ProgrammingError` mentioning `%` syntax, or empty results when data should exist.

### Pitfall 2: Sync cursor API vs async result API

**What goes wrong:** `cur.description` (psycopg) → use `result.keys()` (SQLAlchemy). Calling `.fetchall()` after await on a `CursorResult` works, but calling `.description` will fail (attribute doesn't exist on async result).

**Why it happens:** Different result object APIs.

**How to avoid:** Use `result.keys()` for column names and `result.fetchall()` for rows. This is the established pattern in all existing cubes.

**Warning signs:** `AttributeError: 'CursorResult' object has no attribute 'description'`

### Pitfall 3: datetime timezone handling

**What goes wrong:** `positions[i]["ts"]` from asyncpg returns timezone-aware datetimes. The Kalman filter uses `.total_seconds()` on datetime differences — this works correctly only if both timestamps have the same timezone. If one is naive and one is aware, Python raises `TypeError`.

**Why it happens:** asyncpg returns timezone-aware datetimes; psycopg3 also does, but the scripts were tested with psycopg3. The behavior should be consistent, but type annotations differ.

**How to avoid:** Ensure all `ts` values from `result.fetchall()` are consistently timezone-aware. Do not strip timezone in the fetch function.

**Warning signs:** `TypeError: can't subtract offset-naive and offset-aware datetimes` inside `kalman_filter()`.

### Pitfall 4: Coverage baseline performance in interactive context

**What goes wrong:** `build_coverage_baseline(lookback_days=30)` takes ~30 seconds. If called once per hex, a 10-hex analysis takes 5 minutes.

**Why it happens:** The query aggregates 30 days of global position data — billions of rows. Intended for batch scripts, not interactive per-request use.

**How to avoid:** Build once per cube execution (the `execute()` method), or use a module-level TTL cache (recommended). Consider reducing `lookback_days` to 7 for interactive use if 30s is still too slow.

**Warning signs:** Cube execution timing out after 30+ seconds.

### Pitfall 5: numpy/scipy not in Docker image

**What goes wrong:** `import numpy` fails at startup in the Docker container because numpy/scipy are not in pyproject.toml.

**Why it happens:** These are new dependencies that the backend doesn't currently use.

**How to avoid:** Add `numpy` and `scipy` to `backend/pyproject.toml` dependencies and run `uv sync`. Also update `uv.lock` and rebuild the Docker image.

**Warning signs:** `ModuleNotFoundError: No module named 'numpy'` in container logs at startup, or CubeRegistry silently skipping the cube (it catches exceptions in the `load()` method).

### Pitfall 6: CubeRegistry silently swallows import errors

**What goes wrong:** If the signal module fails to import (e.g., numpy not installed), the registry's `load()` catches the exception silently (`except Exception: pass`) and the cube just disappears from the catalog.

**Why it happens:** Registry design prioritizes resilience over visibility.

**How to avoid:** Always test that the cube appears in `/api/cubes/catalog` after adding it. Check backend logs for any import errors.

**Warning signs:** `signal_health_analyzer` not appearing in cube catalog with no error message.

### Pitfall 7: JSON serialization of datetime objects

**What goes wrong:** `events` output contains `start_ts`, `end_ts` as Python `datetime` objects. FastAPI/Pydantic serializes these fine for direct API responses, but the WorkflowExecutor stores results and may fail if datetime objects appear in the events list.

**Why it happens:** The scripts store datetimes as Python objects; the cube needs to serialize them.

**How to avoid:** Convert all datetimes to ISO 8601 strings (`ts.isoformat()`) before returning from `execute()`. Check how other cubes handle this — existing cubes typically return strings not datetime objects.

**Warning signs:** `TypeError: Object of type datetime is not JSON serializable` in executor or SSE stream.

---

## Code Examples

Verified patterns from existing cubes and scripts:

### Cube Skeleton

```python
# Source: Pattern from backend/app/cubes/alison_flights.py + base.py
from typing import Any
from app.cubes.base import BaseCube
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType

class SignalHealthAnalyzerCube(BaseCube):
    cube_id = "signal_health_analyzer"
    name = "Signal Health Analyzer"
    description = "GPS anomaly detection — rule-based + Kalman filter analysis for individual flights"
    category = CubeCategory.ANALYSIS

    inputs = [
        ParamDefinition(
            name="hex_list",
            type=ParamType.LIST_OF_STRINGS,
            required=True,
            description="ICAO24 hex identifiers to analyze",
        ),
        ParamDefinition(
            name="full_result",
            type=ParamType.JSON_OBJECT,
            required=False,
            accepts_full_result=True,
            description="Full Result from upstream cube (extracts hex_list if connected)",
        ),
        ParamDefinition(
            name="target_phase",
            type=ParamType.STRING,
            required=False,
            default="any",
            description="Flight phase to analyze: takeoff / cruise / landing / any",
            widget_hint="select",
        ),
        ParamDefinition(
            name="classify_mode",
            type=ParamType.LIST_OF_STRINGS,
            required=False,
            default=["all"],
            description="Filter output by classification: Stable, Jamming, Spoofing, Dark Target, Technical Gaps",
            widget_hint="tags",
        ),
    ]

    outputs = [
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Hex IDs of flights with non-normal events matching classify_mode",
        ),
        ParamDefinition(
            name="count",
            type=ParamType.NUMBER,
            description="Count of matching flights",
        ),
        ParamDefinition(
            name="events",
            type=ParamType.JSON_OBJECT,
            description="Array of all non-normal events with detection fields",
        ),
        ParamDefinition(
            name="stats_summary",
            type=ParamType.JSON_OBJECT,
            description="Count of events per category across all analyzed flights",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        ...
```

### Async Fetch — Positions for Kalman

```python
# Source: Adapted from scripts/detect_kalman.py lines 82-102
# using pattern from backend/app/cubes/alison_flights.py lines 218-221
from sqlalchemy import text
from app.database import engine

async def fetch_positions_async(
    hex_code: str,
    start_ts: datetime,
    end_ts: datetime,
) -> list[dict]:
    sql = text("""
        SELECT ts, lat, lon, alt_baro, alt_geom, gs, tas, track, true_heading,
               nac_p, nic, baro_rate, geom_rate, on_ground
        FROM positions
        WHERE hex = :hex
          AND source_type = 'adsb_icao'
          AND on_ground = false
          AND lat IS NOT NULL
          AND ts >= :start AND ts <= :end
        ORDER BY ts
    """)
    async with engine.connect() as conn:
        result = await conn.execute(sql, {"hex": hex_code, "start": start_ts, "end": end_ts})
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]
```

### Async Fetch — Integrity Events

```python
# Source: Adapted from scripts/detect_rule_based.py lines 266-325
# Key change: %(hex)s → :hex, %(start)s → :start
async def detect_integrity_events_async(
    hex_code: str,
    start_ts: datetime,
    end_ts: datetime,
) -> list[dict]:
    sql = text("""
        WITH degraded AS (
            SELECT ts, hex, lat, lon, nac_p, nic, version, sil, gva, nac_v,
                   alt_baro, alt_geom, gs, region,
                   rssi, seen_pos, messages,
                   gps_ok_before, gps_ok_lat, gps_ok_lon,
                   CASE WHEN LAG(ts) OVER (PARTITION BY hex ORDER BY ts) IS NULL THEN 1
                        WHEN EXTRACT(EPOCH FROM ts - LAG(ts) OVER (PARTITION BY hex ORDER BY ts)) > 30 THEN 1
                        ELSE 0 END AS event_start
            FROM positions
            WHERE source_type = 'adsb_icao'
              AND on_ground = false
              AND lat IS NOT NULL
              AND hex = :hex
              AND ts >= :start AND ts <= :end
              AND (
                  (version = 2 AND (nac_p = 0 OR nic < 7))
                  OR (version = 1 AND nac_p = 0 AND (nic = 0 OR gps_ok_before IS NOT NULL))
                  OR ((version = 0 OR version IS NULL) AND gps_ok_before IS NOT NULL)
              )
        ),
        events AS (
            SELECT *, SUM(event_start) OVER (PARTITION BY hex ORDER BY ts) AS event_id
            FROM degraded
        )
        SELECT
            hex, event_id,
            min(ts) AS start_ts,
            max(ts) AS end_ts,
            ...
        FROM events
        GROUP BY hex, event_id
        HAVING max(ts) - min(ts) >= INTERVAL '30 seconds'
        ORDER BY min(ts)
    """)
    async with engine.connect() as conn:
        result = await conn.execute(sql, {"hex": hex_code, "start": start_ts, "end": end_ts})
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    # Cast Decimal types to float (same as original script)
    for row in rows:
        for field in ("median_rssi", "mean_seen_pos", "msg_rate",
                      "mean_alt_divergence_ft", "max_alt_divergence_ft", "duration_s"):
            if row.get(field) is not None:
                row[field] = float(row[field])
    return rows
```

### stats_summary Construction

```python
# Source: Pattern from detect_rule_based.py lines 618-625 (Counter pattern)
from collections import Counter

def build_stats_summary(events: list[dict]) -> dict[str, int]:
    cats = Counter()
    for ev in events:
        cat = ev.get("category") or ev.get("classification") or "unknown"
        cats[cat] += 1
    return dict(cats)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| psycopg2 sync connections | psycopg3 + asyncpg via SQLAlchemy async | Phase 1 of this project | All cube DB access is async |
| Direct cursor fetchall | SQLAlchemy `text()` + `result.fetchall()` | Established in Phase 1 | All existing cubes use this; ported code must match |
| numpy + scipy in scripts only | Add numpy + scipy to pyproject.toml | This phase (new) | Docker image gets larger; first scientific dependencies |

**Deprecated/outdated:**
- psycopg param syntax `%(key)s`: Does not work with SQLAlchemy `text()`. Always use `:key`.

---

## Open Questions

1. **Time window for cube invocation**
   - What we know: The Alison flights cube filters by time window (last N seconds or absolute start/end). The signal analyzer needs a time window to bound its queries.
   - What's unclear: Does `hex_list` carry implicit time window from upstream, or must the cube accept explicit start_time/end_time inputs?
   - Recommendation: Add optional `start_time` and `end_time` inputs (same pattern as AlisonFlightsCube). If not provided, use the full time range available for each hex from `public.positions`. The scripts support auto-detect mode (`SELECT min(ts), max(ts)` per hex).

2. **Coverage baseline lookback window**
   - What we know: The script default is 30 days (~30s query). This is too slow for interactive use.
   - What's unclear: What lookback is acceptable for interactive use given DB size?
   - Recommendation: Default to 7 days for interactive cube (vs 30 days for batch). Make it configurable via an optional input or constant. Flag this in the plan as a tunable.

3. **target_phase filtering implementation**
   - What we know: Script detection runs on a time window; `target_phase` is a new concept for this cube not in the scripts.
   - What's unclear: Which altitude thresholds define takeoff/cruise/landing phases?
   - Recommendation: Define altitude-based thresholds (takeoff: alt_baro < 5000ft ascending; cruise: alt_baro > 10000ft; landing: alt_baro < 5000ft descending). Filter fetched positions before passing to detection functions. Document thresholds as constants.

4. **Kalman candidate selection strategy**
   - What we know: `detect_batch.py` uses `get_kalman_candidates()` to limit Kalman to hexes with rule-based events or NACp=0.
   - What's unclear: For the interactive cube, should Kalman run on ALL hex_list entries or only candidates?
   - Recommendation: Run Kalman on all hex_list entries for the interactive cube (user has already filtered to a small list). For hex_list > 50, apply the candidate filter to bound execution time.

---

## Sources

### Primary (HIGH confidence)

- `scripts/detect_rule_based.py` — Full source, 850 lines, all detection functions verified by direct read
- `scripts/detect_kalman.py` — Full source, 703 lines, Kalman implementation verified by direct read
- `scripts/detect_batch.py` — Full source, 767 lines, batch orchestration pattern verified
- `backend/app/cubes/alison_flights.py` — Async SQLAlchemy pattern (engine.connect, text(), fetchall)
- `backend/app/cubes/base.py` — BaseCube interface, auto-registration, Full Result behavior
- `backend/app/schemas/cube.py` — ParamType, CubeCategory, ParamDefinition fields
- `backend/app/engine/registry.py` — Auto-discovery mechanism (pkgutil.iter_modules + __subclasses__)
- `backend/app/database.py` — engine import, async connection pattern
- `backend/pyproject.toml` — Current dependencies (numpy/scipy not present)

### Secondary (MEDIUM confidence)

- `backend/Dockerfile` — Multi-stage build pattern; adding numpy/scipy will increase image build time but uses standard python:3.12-slim base which supports binary wheels
- `.planning/STATE.md` — Key decisions from previous phases (geo module pattern from Phase 12)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — direct code inspection of all relevant files
- Architecture: HIGH — based on direct reading of scripts + existing cube patterns; no guessing
- Pitfalls: HIGH — pitfalls identified from concrete API differences (psycopg vs SQLAlchemy) and known project history
- Performance: MEDIUM — coverage baseline timing (~30s) mentioned in CONTEXT.md; not independently benchmarked

**Research date:** 2026-03-08
**Valid until:** 2026-06-08 (stable — no external APIs or rapidly-changing libraries involved; all local code)
