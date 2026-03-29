# Technology Stack — v4.0 Flight Behavioral Analysis Cubes

**Project:** 12-flow
**Milestone:** v4.0 — Behavioral Analysis and Anomaly Detection Cubes
**Researched:** 2026-03-29
**Confidence:** HIGH

> Scope: NEW additions and SQL patterns only. The existing validated stack (FastAPI,
> SQLAlchemy async, asyncpg, pandas 3.0.1, numpy 2.4.2, scipy 1.17.1, React 18,
> @xyflow/react, Zustand 5, google-genai, sse-starlette) is unchanged and not
> re-researched here.

---

## Executive Finding

**No new Python libraries are needed.** pandas, numpy, scipy, and Python's `statistics`
stdlib are already in `pyproject.toml` and cover every computation this milestone
requires. The work is in SQL query design and cube implementation patterns, not
new dependencies.

---

## SQL Query Patterns for Historical Lookbacks

### The Core Problem

The behavioral analysis cubes need to answer: "Is this flight's departure location /
departure time / route unusual compared to historical flights on the same route?"

This requires two query tiers per cube execution:

1. **Subject query** — Fetch the specific flights under analysis (already provided
   via `flight_ids` input from AllFlights or FilterFlights upstream).
2. **Baseline query** — Fetch historical aggregate statistics for those same routes
   from `research.flight_metadata` over a configurable lookback window.

**Do not query `research.normal_tracks` (76M rows) for baseline computation.** All
behavioral baseline data (departure location, departure time, route statistics) is
derivable from `research.flight_metadata` alone using `start_lat`, `start_lon`,
`first_seen_ts`, `origin_airport`, `destination_airport`. The 76M-row normal_tracks
table is for track-point geometry only; querying it per-flight for statistical
baselines would be prohibitively slow without PostGIS spatial indexes (which are
not available in this read-only schema).

### Historical Lookback Baseline Query

```sql
-- Historical baseline for a specific route (origin → destination)
-- Returns statistical distribution of departure lat/lon and departure time
SELECT
    COUNT(*)                                          AS historical_count,
    AVG(start_lat)                                    AS avg_dep_lat,
    AVG(start_lon)                                    AS avg_dep_lon,
    STDDEV(start_lat)                                 AS stddev_dep_lat,
    STDDEV(start_lon)                                 AS stddev_dep_lon,
    AVG(EXTRACT(EPOCH FROM
        to_timestamp(first_seen_ts) AT TIME ZONE 'UTC')::bigint
        % 86400)                                      AS avg_dep_time_of_day_sec,
    STDDEV(EXTRACT(EPOCH FROM
        to_timestamp(first_seen_ts) AT TIME ZONE 'UTC')::bigint
        % 86400)                                      AS stddev_dep_time_of_day_sec,
    -- Callsign-level route frequency by day-of-week
    EXTRACT(dow FROM to_timestamp(first_seen_ts))     AS dow,
    COUNT(*) FILTER (
        WHERE callsign = :callsign
    )                                                 AS callsign_flight_count
FROM research.flight_metadata
WHERE
    origin_airport = :origin
    AND destination_airport = :destination
    AND first_seen_ts >= :lookback_start_epoch
    AND first_seen_ts <= :lookback_end_epoch
GROUP BY EXTRACT(dow FROM to_timestamp(first_seen_ts))
ORDER BY dow;
```

**Key conversion pattern for bigint epoch timestamps:**

```sql
-- Convert bigint epoch column to timestamp for date functions
to_timestamp(first_seen_ts)                  -- returns timestamptz from bigint epoch

-- Extract day-of-week (0=Sunday, 6=Saturday)
EXTRACT(dow FROM to_timestamp(first_seen_ts))::int

-- Extract time-of-day in seconds since midnight
(first_seen_ts % 86400)                      -- pure arithmetic, no function call needed
-- This works because epochs are UTC seconds; midnight UTC offset if needed:
((first_seen_ts + :utc_offset_seconds) % 86400)
```

### Lookback Window Computation (Python-side)

Compute lookback boundaries in Python, pass as epoch integers — consistent with
the existing pattern in `AllFlightsCube` and `SignalHealthAnalyzerCube`:

```python
import time

def compute_lookback_window(lookback_days: int) -> tuple[int, int]:
    """Return (start_epoch, end_epoch) as bigint seconds."""
    end_epoch = int(time.time())
    start_epoch = end_epoch - (lookback_days * 86400)
    return start_epoch, end_epoch
```

Default lookback for behavioral baselines: **90 days** (provides statistically
meaningful sample size for Middle East airspace traffic patterns). Configurable
per-cube via `lookback_days` parameter with `default=90`.

### No-Recorded-Takeoff Detection Query

```sql
-- Find flights whose earliest track point is already at cruise altitude
-- (no low-altitude departure points in normal_tracks)
SELECT
    flight_id,
    MIN(alt)  AS min_recorded_alt,
    MIN(timestamp) AS first_track_ts
FROM research.normal_tracks
WHERE flight_id = ANY(:flight_ids)
GROUP BY flight_id
HAVING MIN(alt) > :takeoff_alt_threshold_ft   -- e.g. 5000
ORDER BY flight_id;
```

This is the **one legitimate use** of `normal_tracks` in behavioral analysis — checking
whether a flight has any low-altitude track points. It queries only the specific
`flight_ids` under analysis (not historical population), so the 76M row count does
not create a full-table scan.

### O/D Verification Baseline Query

```sql
-- Historical O/D frequency: how often does this callsign operate this route?
SELECT
    callsign,
    origin_airport,
    destination_airport,
    COUNT(*) AS route_flight_count,
    -- Average flights per day-of-week
    COUNT(*) / NULLIF(
        (EXTRACT(EPOCH FROM (MAX(to_timestamp(first_seen_ts)) - MIN(to_timestamp(first_seen_ts)))) / 86400 / 7)::numeric,
        0
    ) AS avg_per_week
FROM research.flight_metadata
WHERE
    callsign = :callsign
    AND first_seen_ts >= :lookback_start_epoch
GROUP BY callsign, origin_airport, destination_airport
ORDER BY route_flight_count DESC;
```

---

## Statistical Computation Approach

### Recommendation: Pure Python `statistics` stdlib + existing scipy

For the computations this milestone needs, the Python standard library `statistics`
module is sufficient and avoids loading pandas DataFrames for small in-memory result
sets. scipy (already installed at 1.17.1) handles anything requiring z-scores.

**Use `statistics` stdlib for:**
- `statistics.mean(values)` — average departure lat/lon from SQL results
- `statistics.stdev(values)` — standard deviation when SQL STDDEV is inconvenient
- `statistics.median(values)` — median departure time

**Use `scipy.stats` for:**
- Z-score normalization: `scipy.stats.zscore(array)` — when comparing a subject
  flight's departure position against historical distribution
- `scipy.stats.norm.ppf(0.99)` — computing statistical thresholds (e.g. 2.5 sigma
  = ~99th percentile of normal distribution)

**Do NOT use pandas for behavioral cube compute.** SQL GROUP BY with STDDEV/AVG
already returns scalar statistics from the DB. There is no tabular transformation
work that justifies DataFrame overhead for these cubes. Pandas is appropriate for
the existing network_graph_builder and temporal_heatmap cubes where columnar
reshaping is required — not here.

### Z-Score Anomaly Detection Pattern

This is the core computation for "unusual departure location" and "unusual departure
time" cubes:

```python
import math

def z_score_anomaly(
    subject_value: float,
    historical_mean: float,
    historical_stddev: float,
    threshold: float = 2.5,
) -> dict:
    """Compute z-score deviation and flag if anomalous.

    Returns:
        dict with keys: z_score, is_anomaly, deviation_pct
    """
    if historical_stddev is None or historical_stddev == 0:
        # No variance in historical data — any deviation is suspicious
        is_anomaly = abs(subject_value - historical_mean) > 0
        return {
            "z_score": None,
            "is_anomaly": is_anomaly,
            "deviation_pct": None,
            "note": "zero historical variance",
        }

    z = (subject_value - historical_mean) / historical_stddev
    return {
        "z_score": round(z, 3),
        "is_anomaly": abs(z) > threshold,
        "deviation_pct": round(abs(subject_value - historical_mean) / abs(historical_mean) * 100, 1)
                         if historical_mean != 0 else None,
    }
```

### Circular Time-of-Day Statistics

Departure time-of-day is a **circular quantity** (23:50 and 00:10 are 20 minutes
apart, not 23h40m apart). Naive mean/stddev on seconds-since-midnight will give wrong
answers for overnight routes.

Use circular statistics from scipy:

```python
import numpy as np
from scipy.stats import circmean, circstd

def circular_time_stats(epochs_list: list[int], utc_offset_seconds: int = 0) -> dict:
    """Compute circular mean and stddev for time-of-day from epoch values."""
    # Convert to angle in radians (0..2π over 24h)
    day_seconds = 86400
    times_sec = [(e + utc_offset_seconds) % day_seconds for e in epochs_list]
    angles = [2 * math.pi * t / day_seconds for t in times_sec]
    arr = np.array(angles)
    mean_angle = circmean(arr)
    std_angle = circstd(arr)
    # Convert back to seconds
    mean_sec = (mean_angle / (2 * math.pi)) * day_seconds
    std_sec = (std_angle / (2 * math.pi)) * day_seconds
    return {
        "mean_time_of_day_sec": mean_sec,
        "std_time_of_day_sec": std_sec,
        "mean_time_hhmm": f"{int(mean_sec // 3600):02d}:{int((mean_sec % 3600) // 60):02d}",
    }
```

`scipy.stats.circmean` and `scipy.stats.circstd` — confirmed available in
scipy 1.17.1 (already locked in the project).

---

## Datetime/Lookback Toggle Parameter Pattern

The v4.0 milestone requires a UI toggle letting users switch between absolute
datetime ranges and relative lookback. The existing `AllFlightsCube` already
implements this pattern with `start_time` / `end_time` overriding `time_range_seconds`.

**Adopt the same pattern for new behavioral cubes:**

```python
# Cube input params (add to any cube needing configurable lookback)
ParamDefinition(
    name="lookback_days",
    type=ParamType.NUMBER,
    required=False,
    default=90,
    description=(
        "Historical baseline window in days. Default: 90 days. "
        "Increase for routes with sparse traffic."
    ),
    widget_hint="number",
),
ParamDefinition(
    name="baseline_start_time",
    type=ParamType.STRING,
    required=False,
    description=(
        "Absolute start of baseline window as epoch seconds. "
        "Overrides lookback_days if both provided."
    ),
    widget_hint="datetime",
),
ParamDefinition(
    name="baseline_end_time",
    type=ParamType.STRING,
    required=False,
    description="Absolute end of baseline window as epoch seconds.",
    widget_hint="datetime",
),
```

Resolution logic in `execute()`:

```python
baseline_start = inputs.get("baseline_start_time")
baseline_end = inputs.get("baseline_end_time")
if baseline_start and baseline_end:
    start_epoch = int(float(baseline_start))
    end_epoch = int(float(baseline_end))
else:
    lookback_days = int(inputs.get("lookback_days") or 90)
    end_epoch = int(time.time())
    start_epoch = end_epoch - lookback_days * 86400
```

This exactly mirrors `AllFlightsCube` — the `widget_hint="datetime"` signals the
frontend to render a datetime picker, `widget_hint="number"` renders a number input.
No frontend changes needed; the existing parameter editor already handles these hints.

---

## Performance Strategies for 76M Row Table

### What to Avoid

| Approach | Why Dangerous | Alternative |
|----------|--------------|-------------|
| `SELECT * FROM research.normal_tracks WHERE first_seen_ts BETWEEN ...` (historical range) | Full table scan over 76M rows with no flight_id filter | Never query normal_tracks without `flight_id = ANY(:ids)` |
| `SELECT DISTINCT callsign FROM research.normal_tracks` | Aggregation over 76M rows | Use `research.flight_metadata` for callsign/route data |
| `COUNT(*) FROM research.normal_tracks WHERE lat BETWEEN ...` for baseline | bbox scan without flight_id = massive seq scan | Push all population-level stats to flight_metadata |
| Per-flight subqueries in a loop | N+1 queries against 76M rows | Always batch with `flight_id = ANY(:flight_ids)` |

### What Works

1. **`flight_id = ANY(:flight_ids)` batching** — The existing pattern in all cubes.
   With an index on `(flight_id)` in normal_tracks, this is an index scan against
   only the rows for the specific flights. Used in NoRecordedTakeoff detection (see above).

2. **Push statistical baselines to `flight_metadata`** — 113K rows vs 76M rows.
   All route-level stats (departure lat/lon, departure time, O/D frequency) are
   computable from flight_metadata alone. Reserve normal_tracks for track geometry only.

3. **Single batch query per cube execution** — Never query in a loop per flight_id.
   Use `GROUP BY flight_id` with `flight_id = ANY(:ids)` to get per-flight stats
   in one round trip (identical pattern to `FilterFlightsCube` Tier 2 query).

4. **Result capping** — Set `LIMIT 5000` on normal_tracks queries, `LIMIT 50000` on
   flight_metadata baselines (consistent with existing cubes). Behavioral cubes are
   expected to receive 50-200 flights from upstream, not 10,000+.

5. **Short-circuit on empty input** — All new cubes must check `if not flight_ids`
   immediately and return empty result, avoiding any DB query (identical pattern in
   `GetFlightCourseCube`, `FilterFlightsCube`).

---

## New Cube Inventory for v4.0

| Cube | Category | Primary Table | Historical Baseline? | Normal Tracks Use? |
|------|----------|--------------|---------------------|--------------------|
| NoRecordedTakeoffCube | analysis | normal_tracks | No — per-flight check | Yes — MIN(alt) by flight_id |
| UnusualTakeoffLocationCube | analysis | flight_metadata | Yes — avg/stddev of start_lat/lon for route | No |
| UnusualTakeoffTimeCube | analysis | flight_metadata | Yes — circular mean/std of first_seen_ts for route | No |
| ODVerificationCube | analysis | flight_metadata | Yes — historical route frequency for callsign | No |
| RouteStatsCube | aggregation | flight_metadata | Yes — avg flights/route, avg per day-of-week | No |

---

## What NOT to Add

| Library | Why Not |
|---------|---------|
| `pyod` (outlier detection) | Heavy ML library. Z-score with scipy is sufficient and already available. Not justified. |
| `statsmodels` | Regression/ARIMA complexity not needed. scipy.stats handles every computation here. |
| PostGIS / geoalchemy2 | Not available on the research schema (read-only RDS, no PostGIS extension). Python-side computation already proven via `point_in_polygon()` in AllFlights. |
| `asyncpg` raw queries (bypass SQLAlchemy) | SQLAlchemy async already wraps asyncpg. No performance benefit for read-only queries. Adds inconsistency. |
| `redis` / in-memory cache for baselines | Premature. Baseline queries against 113K-row flight_metadata are fast. Add cache only if profiling shows >2s baseline queries in production. |

---

## Summary: Install Commands

```bash
# No new backend dependencies — everything needed is already installed
# Verify current locked versions:
# numpy==2.4.2, scipy==1.17.1, pandas==3.0.1

# No frontend dependencies needed for behavioral analysis cubes
```

---

## Sources

- `/Users/oriklain/work/five/tracer/12-flow/backend/pyproject.toml` and `uv.lock` —
  confirmed numpy 2.4.2, scipy 1.17.1, pandas 3.0.1 already installed — HIGH confidence
- `backend/app/cubes/all_flights.py` — bigint epoch query pattern, datetime toggle,
  SQL fragment construction — HIGH confidence (direct observation)
- `backend/app/cubes/filter_flights.py` — GROUP BY aggregate on normal_tracks with
  `flight_id = ANY(:ids)` batch pattern — HIGH confidence (direct observation)
- `backend/app/cubes/get_flight_course.py` — normal_tracks column schema
  (flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source)
  — HIGH confidence (direct observation)
- [PostgreSQL EXTRACT / to_timestamp docs](https://www.postgresql.org/docs/current/functions-datetime.html)
  — to_timestamp(bigint), EXTRACT(dow), epoch conversion — HIGH confidence
- [scipy.stats.circmean / circstd](https://docs.scipy.org/doc/scipy/reference/stats.html)
  — available in scipy 1.17.1 — HIGH confidence
- [python statistics stdlib](https://docs.python.org/3/library/statistics.html)
  — mean, stdev, median — HIGH confidence (stdlib, no version concerns)
- PROJECT.md — column inventory, table row counts, bigint epoch format — HIGH confidence

---

*Stack research for: v4.0 Flight Behavioral Analysis Cubes, Project 12-flow*
*Researched: 2026-03-29*
