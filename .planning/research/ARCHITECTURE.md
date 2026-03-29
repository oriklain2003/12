# Architecture Patterns

**Domain:** Flight behavioral analysis cubes — v4.0 integration into existing visual dataflow system
**Researched:** 2026-03-29
**Confidence:** HIGH (based on direct codebase inspection — all findings grounded in code, not speculation)

---

## Existing Architecture Summary

The system is a three-layer stack: React frontend → FastAPI backend → PostgreSQL (Tracer 42 RDS, read-only research schema).

### Cube Execution Model

Every cube is a Python class inheriting `BaseCube`, placed in `backend/app/cubes/`. Auto-discovery via `CubeRegistry` collects all subclasses at startup. The `WorkflowExecutor` runs cubes in topological order, resolves inputs (connection values override manual params), caps outputs at 10,000 rows, and streams per-cube status via SSE.

The contract is:

```python
class BaseCube(abc.ABC):
    cube_id: str
    name: str
    category: CubeCategory
    inputs: list[ParamDefinition]
    outputs: list[ParamDefinition]

    async def execute(self, **inputs: Any) -> dict[str, Any]: ...
```

To add a cube: drop a `.py` file in `backend/app/cubes/`. No registration step. No router changes. Auto-discovered on next restart.

### Parameter System

`ParamDefinition` fields relevant to v4.0:
- `type: ParamType` — currently STRING, NUMBER, BOOLEAN, LIST_OF_STRINGS, LIST_OF_NUMBERS, JSON_OBJECT
- `widget_hint: str | None` — drives frontend editor: `"select"`, `"tags"`, `"datetime"`, `"relative_time"`, `"polygon"`
- `options: list[str] | None` — drives select/tags widget options
- `accepts_full_result: bool` — marks params that accept the full upstream bundle
- `default: Any` — shown in editor when not connected

### Database Access Pattern

All cubes query via the shared SQLAlchemy async engine imported from `app.database`:

```python
from app.database import engine

async with engine.connect() as conn:
    result = await conn.execute(text(sql), params)
    rows = result.fetchall()
```

The engine is a module-level singleton (`pool_size=10, max_overflow=10`). No per-cube connection setup. Timestamps in `research.flight_metadata` are bigint epoch seconds. Key tables: `research.flight_metadata` (113K rows), `research.normal_tracks` (76M rows), `research.anomaly_reports` (114K rows).

---

## New Cube Integration Points

### What Does NOT Change

- `BaseCube` abstract class — no modification needed
- `CubeRegistry` auto-discovery — new cubes drop into `backend/app/cubes/` and are picked up automatically
- `WorkflowExecutor` topological sort, input resolution, SSE streaming — no changes
- `ParamType` enum — existing types cover all v4.0 needs (see datetime/lookback toggle pattern below)
- `ParamDefinition` schema — `widget_hint` and `options` already handle enum selects
- Frontend canvas, node rendering, parameter editors — no structural changes required
- `__full_result__` port — behavioral analysis cubes accept full result from AllFlights/FilterFlights using the existing `accepts_full_result=True` pattern

### What Needs to Be Added

| Component | Type | Why Needed |
|-----------|------|------------|
| `backend/app/cubes/historical_query.py` | New shared utility module | Historical lookback queries used by 3+ analysis cubes; avoids duplication |
| `backend/app/cubes/no_recorded_takeoff.py` | New cube file | Detects flights where first track point is already at altitude |
| `backend/app/cubes/unusual_takeoff_location.py` | New cube file | Compares departure lat/lon against historical baseline for same callsign |
| `backend/app/cubes/unusual_takeoff_time.py` | New cube file | Compares departure time-of-day against historical distribution for same callsign |
| `backend/app/cubes/od_verifier.py` | New cube file | Compares current O/D pair against historical route frequency; extensible |
| `backend/app/cubes/route_stats.py` | New cube file | Aggregates flights by route with avg-per-day/week statistics |
| Duration filter params on `filter_flights.py` | Param additions only — no logic restructure | `min_flight_time_minutes`, `max_flight_time_minutes` using first_seen_ts / last_seen_ts delta |

No new `ParamType` values needed. No new routers. No schema migrations. No frontend structural changes.

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `historical_query.py` | Shared async functions for querying historical flight data by callsign, origin, destination, and time window | Imported directly by analysis cubes: no_recorded_takeoff (not needed), unusual_takeoff_location, unusual_takeoff_time, od_verifier |
| `no_recorded_takeoff.py` | Detect flights where first track point altitude exceeds a threshold (flight was never observed on ground or in initial climb) | Receives flight_ids from AllFlights/FilterFlights; queries research.normal_tracks |
| `unusual_takeoff_location.py` | Compare departure lat/lon against historical centroid for same callsign; score distance as deviation | Calls historical_query; receives current flight metadata via full_result |
| `unusual_takeoff_time.py` | Compare departure timestamp (hour-of-day) against historical distribution for same callsign; detect off-schedule departures | Calls historical_query; receives current flight metadata via full_result |
| `od_verifier.py` | Compare current origin/destination pair against historical route frequency for same callsign; extensible internal check registry | Calls historical_query; receives flight_ids or full_result |
| `route_stats.py` | Aggregate input flights by route (origin/destination pair) with avg per day and per day-of-week statistics | Receives flights JSON from AllFlights or FilterFlights; pure Python aggregation |
| `filter_flights.py` (modified) | Duration filter using first_seen_ts / last_seen_ts delta from flight metadata | Existing cube — param additions only, no logic restructure |

---

## Shared Historical Query Utility

**Decision: shared utility module, not per-cube inline queries.**

Three of the four new analysis cubes need the same operation: given a callsign, fetch all historical flights for that callsign from `research.flight_metadata` within a lookback window and return aggregated statistics. Duplicating this across cubes creates three divergent SQL queries that will drift. A single `historical_query.py` module with one SQL query serves all callers.

### Location

`backend/app/cubes/historical_query.py`

This is a utility module in the cubes package, not an engine concern. Cube authors import it directly:

```python
from app.cubes.historical_query import get_callsign_history, get_route_history
```

### Interface

```python
async def get_callsign_history(
    callsign: str,
    lookback_days: int = 90,
    max_rows: int = 500,
) -> list[dict]:
    """Fetch historical flight_metadata rows for a callsign.

    Returns rows from research.flight_metadata ordered by first_seen_ts DESC.
    Timestamps are bigint epoch seconds. Fields include: flight_id, callsign,
    first_seen_ts, start_lat, start_lon, origin_airport, destination_airport.
    """
    ...

async def get_route_history(
    origin: str,
    destination: str,
    lookback_days: int = 90,
    max_rows: int = 500,
) -> list[dict]:
    """Fetch historical metadata for a specific origin-destination route."""
    ...
```

Both functions use the shared `engine` from `app.database`. They return plain `list[dict]` — no framework types — keeping them easy to test in isolation.

---

## Data Flow: Current Flight + Historical Context

The typical v4.0 analysis workflow:

```
AllFlights (callsign filter)
    │ flight_ids (LIST_OF_STRINGS), flights (JSON_OBJECT)
    ▼
[Optional: FilterFlights — with new duration params]
    │ filtered_flight_ids, filtered_flights
    ▼
NoRecordedTakeoff / UnusualTakeoffLocation / UnusualTakeoffTime / ODVerifier
    │  receives:  current flight metadata (start_lat, start_lon, first_seen_ts,
    │             callsign, origin_airport, destination_airport)
    │  queries:   historical baseline via historical_query module
    │             (separate async DB call inside execute())
    │  computes:  deviation from baseline (pure Python statistics)
    ▼
    anomaly_flights (JSON_OBJECT), flight_ids (LIST_OF_STRINGS), count (NUMBER)
    ▼
[Optional: Count By Field, Get Anomalies, or output cubes]
```

Each analysis cube is responsible for fetching its own historical baseline. The cube receives current flights via `full_result` or direct `flight_ids`, extracts metadata fields, calls `historical_query`, then computes comparison in Python after closing the DB connection.

**Why the historical query is inside the analysis cube, not a separate upstream cube:**
The historical baseline is specific to the analysis being performed. The `unusual_takeoff_location` cube needs departure lat/lon statistics; the `unusual_takeoff_time` cube needs time-of-day statistics. Making "fetch historical baseline" a separate cube would require the user to wire complex intermediate cubes and would expose internal statistical intermediate results as connection points. The analysis cubes are atomic units of behavioral reasoning — they take current flights and return anomaly findings.

---

## Parameter Pattern: Datetime / Lookback Toggle

The v4.0 cubes need a toggle between "last N days" (relative) and "specific date range" (absolute). The existing `all_flights.py` already implements this exact pattern: `time_range_seconds` (relative) + `start_time` / `end_time` (absolute). No new parameter types are needed.

For behavioral analysis cubes with a historical lookback concept, use this pattern:

```python
inputs = [
    ParamDefinition(
        name="time_mode",
        type=ParamType.STRING,
        required=False,
        default="relative",
        description='Time range mode: "relative" (last N days) or "absolute" (specific dates).',
        widget_hint="select",
        options=["relative", "absolute"],
    ),
    ParamDefinition(
        name="lookback_days",
        type=ParamType.NUMBER,
        required=False,
        default=90,
        description="Days of history to use as baseline (used when time_mode=relative).",
    ),
    ParamDefinition(
        name="baseline_start",
        type=ParamType.STRING,
        required=False,
        description="Baseline window start as epoch seconds string (used when time_mode=absolute).",
        widget_hint="datetime",
    ),
    ParamDefinition(
        name="baseline_end",
        type=ParamType.STRING,
        required=False,
        description="Baseline window end as epoch seconds string (used when time_mode=absolute).",
        widget_hint="datetime",
    ),
]
```

In `execute()`:

```python
time_mode = inputs.get("time_mode") or "relative"
if time_mode == "absolute" and inputs.get("baseline_start") and inputs.get("baseline_end"):
    start_epoch = int(float(inputs["baseline_start"]))
    end_epoch = int(float(inputs["baseline_end"]))
else:
    lookback_days = int(inputs.get("lookback_days") or 90)
    end_epoch = int(time.time())
    start_epoch = end_epoch - (lookback_days * 86400)
```

This is the same pattern `all_flights.py` uses. Frontend already handles `widget_hint="select"` and `widget_hint="datetime"`. No frontend changes needed for this pattern.

**The `time_mode` param acts as the toggle.** The other three params are conditionally relevant based on its value. The frontend editor shows all four params but only the relevant ones have effect. This is already how `all_flights.py` works — users either fill in `start_time`+`end_time` or leave them blank and use `time_range_seconds`.

---

## Extensibility Pattern: O/D Verification Cube

The `od_verifier` cube must be designed so future checks (e.g., "first time this callsign flew to this destination," "destination not in callsign's normal region," "unusual stop count") can be added without changing the cube's input/output interface.

**Pattern: internal check registry as a module-level list of async functions**

```python
# od_verifier.py

async def _check_new_destination(flight: dict, history: list[dict]) -> dict | None:
    """Return a finding dict if destination has never appeared in historical O/D pairs, else None."""
    seen_destinations = {r.get("destination_airport") for r in history if r.get("destination_airport")}
    dest = flight.get("destination_airport")
    if dest and dest not in seen_destinations and len(seen_destinations) >= 3:
        return {
            "check": "new_destination",
            "deviation_score": 0.9,
            "details": {"destination": dest, "historical_destinations": list(seen_destinations)},
        }
    return None

async def _check_unusual_origin(flight: dict, history: list[dict]) -> dict | None:
    """Return a finding if origin airport was never used historically for this callsign."""
    ...

_CHECKS = [
    _check_new_destination,
    _check_unusual_origin,
    # future checks appended here — no interface change required
]

class ODVerifierCube(BaseCube):
    async def execute(self, **inputs: Any) -> dict[str, Any]:
        # ... extract flights and callsigns ...
        for callsign, flights_for_callsign in flights_by_callsign.items():
            history = await get_callsign_history(callsign, lookback_days)
            for flight in flights_for_callsign:
                for check_fn in _CHECKS:
                    result = await check_fn(flight, history)
                    if result:
                        findings.append({**result, "flight_id": flight["flight_id"]})
        return {"findings": findings, "flight_ids": [...], "count": len(findings)}
```

Each check function: signature `(flight: dict, history: list[dict]) -> dict | None`. Adding a check in a future phase means appending one function to `_CHECKS` and writing its unit test. The cube's input/output interface stays unchanged. This is the simplest extensibility pattern that does not require a plugin system.

---

## Patterns to Follow

### Pattern 1: Full Result Input Acceptance

All v4.0 analysis cubes should accept full result from upstream so users can chain them directly without explicit parameter wiring:

```python
ParamDefinition(
    name="full_result",
    type=ParamType.JSON_OBJECT,
    required=False,
    accepts_full_result=True,
    description="Full result from AllFlights or FilterFlights. Extracts 'flights' and 'flight_ids'.",
),
```

In `execute()`:

```python
full_result = inputs.get("full_result")
direct_ids = inputs.get("flight_ids")

if full_result and isinstance(full_result, dict):
    flights = full_result.get("flights") or full_result.get("filtered_flights") or []
    flight_ids = full_result.get("flight_ids") or full_result.get("filtered_flight_ids") or []
elif direct_ids:
    flight_ids = list(direct_ids)
    flights = []
else:
    return {"anomaly_flights": [], "flight_ids": [], "count": 0}
```

This matches the pattern used by `FilterFlightsCube` and `DarkFlightDetectorCube`.

### Pattern 2: Early Empty-List Guard

Every analysis cube that receives a flight list must guard against empty input before executing any DB queries:

```python
if not flight_ids:
    logger.info("CubeName: no flight_ids — returning empty result")
    return {"anomaly_flights": [], "flight_ids": [], "count": 0}
```

The executor calls `execute(**inputs)` with no type coercion — an unconnected input param arrives as `None`. Guard against both `None` and `[]`.

### Pattern 3: Statistical Comparison Output Schema

Behavioral analysis cubes that compare against historical baselines should output a consistent finding schema so downstream cubes and the results interpreter can work uniformly across all behavioral analysis outputs:

```python
{
    "flight_id": "...",
    "callsign": "...",
    "deviation_type": "unusual_takeoff_location",  # or: no_recorded_takeoff, unusual_takeoff_time, new_od_pair
    "deviation_score": 0.85,   # 0.0-1.0, higher = more anomalous
    "details": {               # deviation-specific fields
        "actual_lat": 32.01,
        "actual_lon": 34.87,
        "historical_centroid_lat": 31.99,
        "historical_centroid_lon": 34.85,
        "distance_km": 2.5,
    },
    "historical_sample_size": 47,  # how many historical flights informed the baseline
}
```

Each cube outputs a list of these finding objects plus `flight_ids` (LIST_OF_STRINGS) and `count` (NUMBER).

### Pattern 4: Batch History Fetch Per Unique Callsign

When processing multiple input flights, extract the unique callsigns first, fetch history once per callsign, build a lookup dict, then loop over flights using that dict. Never fetch history inside a per-flight loop.

```python
# Extract unique callsigns from input flights
unique_callsigns = {f.get("callsign") for f in flights if f.get("callsign")}

# Fetch history for all callsigns concurrently
histories = await asyncio.gather(*[
    get_callsign_history(cs, lookback_days) for cs in unique_callsigns
])
history_by_callsign = dict(zip(unique_callsigns, histories))

# Now process each flight using pre-fetched history
for flight in flights:
    cs = flight.get("callsign")
    history = history_by_callsign.get(cs, [])
    # ... compute deviation ...
```

This mirrors the batch-query pattern used in `SignalHealthAnalyzerCube` which uses `asyncio.gather()` for its batch detection queries.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Per-Cube Historical Query Duplication

**What:** Each analysis cube has its own inline SQL query for fetching historical flights by callsign.

**Why bad:** The same callsign-history query duplicated in four cubes will drift. Bug fixes apply to one cube. SQL changes (e.g., adjusting date arithmetic or adding a callsign normalization step) require four separate edits.

**Instead:** Use the `historical_query.py` shared module. Each cube calls `await get_callsign_history(callsign, lookback_days)`.

### Anti-Pattern 2: Holding DB Connection Open During Statistics Computation

**What:** Fetching historical flights and computing statistics (mean, stddev, centroid) while still inside the `async with engine.connect()` block.

**Why bad:** Blocks a connection pool slot during CPU-bound statistics work. The pool has 10 connections; if 10 cubes execute concurrently and each holds a connection while computing in Python, new connections queue.

**Instead:** Fetch data (await, collect rows), let the `async with` block close the connection, then compute statistics in pure Python on the collected list.

### Anti-Pattern 3: New ParamType for Toggle State

**What:** Adding `ParamType.ENUM` or `ParamType.TOGGLE` to handle the time_mode / lookback toggle.

**Why bad:** Requires changes to `ParamType` enum (schema change), `ParamDefinition` serialization, frontend editor dispatch, and agent skill files. Cascading change across 5 files for something `ParamType.STRING` + `widget_hint="select"` + `options=["relative","absolute"]` already handles correctly.

**Instead:** Use `ParamType.STRING` with `widget_hint="select"` and `options`. Existing frontend widget handles it today.

### Anti-Pattern 4: Recomputing Baseline Per Flight in a Loop

**What:** The `od_verifier` or `unusual_takeoff_location` cube calls `await get_callsign_history(callsign, ...)` inside a `for flight in flights` loop.

**Why bad:** If the input is 50 flights, all for callsign "ELY317", this runs 50 identical DB queries. With 90-day lookback on a 113K-row table, each query is non-trivial.

**Instead:** Extract unique callsigns first, batch-fetch with `asyncio.gather()`, build a lookup dict, then loop over flights with O(1) baseline access. See Pattern 4 above.

### Anti-Pattern 5: Assuming flight_metadata Columns Are Always Populated

**What:** Behavioral cubes that assume `start_lat`, `start_lon`, `callsign`, `origin_airport`, `destination_airport` are always present.

**Why bad:** `research.flight_metadata` has 113K rows from varied sources; field population varies. Cubes that crash on NULL values will be unreliable in production.

**Instead:** Guard all field extractions with `.get()` and `None` checks. When a required field (e.g., `callsign`) is missing, skip that flight with a log entry rather than crashing the entire cube. Return findings for the flights that had sufficient data.

### Anti-Pattern 6: Making Historical Query a Separate Upstream Cube

**What:** Exposing "Get Historical Baseline" as a user-facing cube that feeds analysis cubes via connections.

**Why bad:** Forces users to wire an additional intermediate cube in every behavioral analysis workflow. The baseline is always parameterized by the current flight being analyzed (same callsign, same route) — it is not a reusable standalone operation. It would also expose intermediate statistical data as connection points, cluttering the canvas.

**Instead:** Historical query is an internal implementation detail of each analysis cube. Users see: AllFlights → UnusualTakeoffLocation. They do not wire a separate baseline cube.

---

## Build Order for v4.0

This order respects dependencies between components and allows each step to be tested before the next builds on it.

### Phase 1: Shared Utility + Duration Filter (no dependencies on new cubes)

1. `historical_query.py` — shared module that all statistical analysis cubes depend on
2. Duration filter params on `filter_flights.py` — isolated param additions (`min_flight_time_minutes`, `max_flight_time_minutes`), no logic restructure

**Why first:** The three statistical behavioral cubes in later phases all import from `historical_query`. Getting this right first means the analysis cubes can be written and tested cleanly. FilterFlights duration params are self-contained and have no dependencies.

### Phase 2: Simple Behavioral Analysis Cube (validates cube structure without needing historical query)

3. `no_recorded_takeoff.py` — no historical baseline needed; purely checks whether first track point altitude exceeds a threshold. Validates the output schema and full_result input pattern for behavioral cubes.

**Why before statistical cubes:** Establishes the behavioral cube pattern (finding schema, full_result acceptance, empty guard) on the simplest possible case.

### Phase 3: Statistical Behavioral Analysis Cubes (depend on Phase 1 historical_query)

4. `unusual_takeoff_location.py` — uses `get_callsign_history`, compares `start_lat`/`start_lon` against historical centroid using haversine distance
5. `unusual_takeoff_time.py` — uses `get_callsign_history`, compares `first_seen_ts` hour against historical time-of-day distribution (mean, stddev)

**Why in this order:** Both depend on `historical_query`; location check is simpler (distance comparison) than time-of-day check (circular statistics). Build and test location first.

### Phase 4: Multi-Factor and Aggregation Cubes

6. `od_verifier.py` — uses `get_route_history` and `get_callsign_history`, implements internal check registry extensibility pattern
7. `route_stats.py` — pure Python aggregation over input flights; no DB query needed beyond what AllFlights already fetched

**Why last:** `od_verifier` uses the internal check registry extensibility pattern — doing it after simpler cubes validates the pattern. `route_stats` has no dependencies and can be built at any point; last simply because it has lower analytical priority than the detection cubes.

---

## Scalability Considerations

| Concern | At Current Scale (113K flights) | At 10x Scale (1M+ flights) |
|---------|----------------------------------|-----------------------------|
| Historical query per callsign | Single parameterized query with `ILIKE callsign AND first_seen_ts >= :cutoff LIMIT 500` — fast on indexed columns | Add covering index on `(callsign, first_seen_ts)` if not present; LIMIT 500 keeps result set bounded |
| Multiple analysis cubes in one workflow | Each runs sequentially in topological order via `asyncio.gather` within the cube | No structural change; the 10-connection pool handles concurrent cubes in separate workflow runs |
| Baseline computation in Python | List statistics (mean, stddev, centroid) over 500 rows — sub-millisecond | Still in-memory; no change needed up to ~50K historical rows per callsign |
| `route_stats` aggregation | Python-side `groupby` over the `flights` list from AllFlights | Delegate to SQL `GROUP BY` if AllFlights output approaches 10K rows |
| Callsign batch-fetch in a single cube | `asyncio.gather()` over unique callsigns in the input flight set | For very large input sets (1K+ flights, 500+ unique callsigns), cap concurrency with a semaphore |

---

## Sources

- Direct codebase inspection (HIGH confidence): `backend/app/cubes/base.py`, `engine/executor.py`, `engine/registry.py`, `schemas/cube.py`, `database.py`
- Existing cube implementations reviewed (HIGH confidence): `all_flights.py`, `filter_flights.py`, `dark_flight_detector.py`, `signal_health_analyzer.py`, `get_flight_course.py`, `get_anomalies.py`
- Planning documents (HIGH confidence): `.planning/PROJECT.md`, `.planning/new-cubes/02-behavioral-analysis.md`, `.planning/new-cubes/00-INDEX.md`

---

*Architecture research for: v4.0 Flight Behavioral Analysis Cubes — integration into 12-flow*
*Researched: 2026-03-29*
