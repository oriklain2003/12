# SQL Query Optimization Report — 12-Flow Cubes

> Generated 2026-03-11 by parallel agent analysis of all cubes with SQL queries.
> Note: Agents could not connect to the live DB (psql denied). All findings are from static code analysis + PostgreSQL internals knowledge. Run the validation queries at the end to confirm.

---

## Executive Summary

Analyzed **12 cubes** across 4 tables. Found **8 HIGH**, **10 MEDIUM**, and **6 LOW** priority issues.

**Top 3 most impactful changes:**
1. **Composite index `(hex, ts)` on `public.positions`** — serves ~15 queries across 7 cubes
2. **Materialized view for coverage baseline** — eliminates the single most expensive query (full scan + percentile_cont over millions of rows)
3. **GIN index on `research.anomaly_reports.matched_rule_names`** — array containment without GIN = guaranteed seq scan

---

## Tables Overview

| Table | Est. Size | Used By |
|-------|-----------|---------|
| `public.positions` | 46M–135M+ rows | AreaSpatialFilter, GetFlightCourse, AlisonFlights, DarkFlightDetector, SquawkFilter, SignalHealthAnalyzer (rule_based + kalman) |
| `research.normal_tracks` | Large (track data) | AllFlights, FilterFlights, GetFlightCourse, AreaSpatialFilter, SquawkFilter |
| `research.flight_metadata` | Medium | AllFlights |
| `public.aircraft` | ~35K rows | AlisonFlights, RegistrationCountryFilter |
| `research.anomaly_reports` | Medium | GetAnomalies |
| `public.learned_paths` | Small (thousands) | GetLearnedPaths |

---

## HIGH Priority Issues

### H1. Missing `(hex, ts)` composite index on `public.positions`

**Impact:** Nearly every cube that touches `positions` filters on `hex = X AND ts >= Y`. Without this index, every such query is a sequential scan of 46M–135M+ rows.

**Affected cubes:** AreaSpatialFilter, GetFlightCourse, AlisonFlights (EXISTS), DarkFlightDetector, SquawkFilter (Alison), SignalHealthAnalyzer (all 4 SQL queries)

```sql
CREATE INDEX CONCURRENTLY idx_positions_hex_ts
    ON public.positions (hex, ts);
```

**Partial index variant** (if most queries also filter `source_type` and `lat`):
```sql
CREATE INDEX CONCURRENTLY idx_positions_hex_ts_adsb
    ON public.positions (hex, ts)
    WHERE source_type = 'adsb_icao' AND lat IS NOT NULL;
```

---

### H2. Missing `(flight_id, timestamp)` composite index on `research.normal_tracks`

**Impact:** Every query on normal_tracks filters `flight_id = ANY(...)` and often sorts by timestamp. Without this index, all such queries do full sequential scans.

**Affected cubes:** AllFlights (polygon filter), FilterFlights (all 3 queries), GetFlightCourse (FR), AreaSpatialFilter (FR LATERAL), SquawkFilter (FR)

```sql
CREATE INDEX CONCURRENTLY idx_normal_tracks_fid_ts
    ON research.normal_tracks (flight_id, "timestamp");
```

---

### H3. Missing index on `research.flight_metadata.last_seen_ts`

**Impact:** The always-active time filter `last_seen_ts >= cutoff` in AllFlightsCube runs on every execution. Without an index, this scans the entire metadata table.

```sql
CREATE INDEX CONCURRENTLY idx_flight_metadata_last_seen_ts
    ON research.flight_metadata (last_seen_ts);
```

---

### H4. `callsign ILIKE '%...%'` — leading wildcard prevents B-tree usage

**Impact:** AllFlightsCube and AlisonFlightsCube both use `ILIKE '%pattern%'` on callsign columns. A leading `%` makes B-tree indexes useless. Requires `pg_trgm` GIN index.

**Affected cubes:** AllFlights (`callsign`), AlisonFlights (`flight` column on positions)

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- flight_metadata.callsign
CREATE INDEX CONCURRENTLY idx_flight_metadata_callsign_trgm
    ON research.flight_metadata USING GIN (callsign gin_trgm_ops);

-- positions.flight (callsign in Alison)
CREATE INDEX CONCURRENTLY idx_positions_flight_trgm
    ON public.positions USING GIN (flight gin_trgm_ops);
```

---

### H5. `airport ILIKE '%XYZ%'` — same leading wildcard issue

**Impact:** AllFlightsCube filters `origin_airport ILIKE '%XYZ%' OR destination_airport ILIKE '%XYZ%'`. Airport codes are 3-4 char ICAO codes — likely better as exact match.

**Option A** — Change to exact match (preferred, code change):
```python
# Change ILIKE to =
sql_parts.append("AND (origin_airport = :airport OR destination_airport = :airport)")
params["airport"] = airport  # no % wrapping
```

**Option B** — GIN trigram indexes:
```sql
CREATE INDEX CONCURRENTLY idx_flight_metadata_origin_trgm
    ON research.flight_metadata USING GIN (origin_airport gin_trgm_ops);
CREATE INDEX CONCURRENTLY idx_flight_metadata_dest_trgm
    ON research.flight_metadata USING GIN (destination_airport gin_trgm_ops);
```

---

### H6. GIN index needed for `matched_rule_names` array column

**Impact:** GetAnomaliesCube uses `:matched_rule_name = ANY(matched_rule_names)` — a scalar-in-array check. Without a GIN index, every row's array must be scanned linearly.

```sql
CREATE INDEX CONCURRENTLY idx_anomaly_reports_rule_names_gin
    ON research.anomaly_reports USING GIN (matched_rule_names);
```

**Code change needed** — rewrite to use GIN-compatible operator:
```python
# Change from:
sql_parts.append("AND :matched_rule_name = ANY(matched_rule_names)")
# To:
sql_parts.append("AND matched_rule_names @> ARRAY[:matched_rule_name]")
```

---

### H7. Coverage baseline query — most expensive query in codebase

**Impact:** `build_coverage_baseline_async()` in `rule_based.py` does a full scan of positions over 3 days with `percentile_cont` aggregation. On 135M+ rows this can take minutes.

**Recommendation:** Replace with a materialized view:
```sql
CREATE MATERIALIZED VIEW mv_coverage_grid AS
SELECT
    floor(lat/0.5)*0.5 AS lat_cell,
    floor(lon/0.5)*0.5 AS lon_cell,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY rssi) AS median_rssi,
    count(*) AS total_reports,
    count(DISTINCT hex) AS unique_aircraft,
    min(ts) AS first_seen,
    max(ts) AS last_seen,
    count(DISTINCT floor(extract(epoch FROM ts) / 600)) AS bins_with_data
FROM public.positions
WHERE source_type = 'adsb_icao'
    AND on_ground = false
    AND lat IS NOT NULL
    AND rssi IS NOT NULL
    AND ts >= NOW() - INTERVAL '3 days'
GROUP BY 1, 2
HAVING count(*) >= 10;

-- Refresh hourly via pg_cron or app-level scheduler:
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_coverage_grid;
```

If materialized views aren't feasible, add a partial index:
```sql
CREATE INDEX CONCURRENTLY idx_positions_baseline
    ON public.positions (ts)
    INCLUDE (lat, lon, rssi, hex, nac_p)
    WHERE source_type = 'adsb_icao'
      AND on_ground = false
      AND lat IS NOT NULL
      AND rssi IS NOT NULL;
```

---

### H8. Missing index on `research.anomaly_reports.flight_id`

```sql
CREATE INDEX CONCURRENTLY idx_anomaly_reports_flight_id
    ON research.anomaly_reports (flight_id);
```

---

## MEDIUM Priority Issues

### M1. SquawkFilter FR — missing timestamp filter

The FR branch of SquawkFilter has **no timestamp cutoff**, unlike the Alison branch. This prevents partition pruning on `normal_tracks` and scans all historical data.

**File:** `squawk_filter.py:199-217`
**Fix:** Add `AND "timestamp" >= :cutoff_epoch` to the FR query, mirroring the Alison branch.

---

### M2. AlisonFlights polygon post-filter — missing time filter

The polygon post-filter query (line 228) fetches positions with **no time filter**, scanning all historical positions for candidate hexes.

**File:** `alison_flights.py:226-243`
**Fix:** Add `AND ts >= :cutoff` (or `AND ts BETWEEN :ts_start AND :ts_end`) to the polygon post-filter query.

---

### M3. GetFlightCourse — no time filter or LIMIT (both providers)

Both FR and Alison queries fetch **all historical track data** with no time constraint and no row limit.

**File:** `get_flight_course.py:78-99`
**Fix:** Add optional `time_window_hours` input parameter and apply `AND ts >= cutoff` + `LIMIT` to both queries.

---

### M4. RegistrationCountryFilter — duplicate DB round-trips

Queries `public.aircraft` twice with identical SQL for unresolved hexes then resolved hexes. Could be merged into a single query.

**File:** `registration_country_filter.py:218-276`
**Fix:** Query all hexes once, partition results in Python.

---

### M5. Partial index for `squawk IS NOT NULL` on normal_tracks

SquawkFilter FR adds `AND squawk IS NOT NULL`. If squawk is mostly NULL, a partial index helps:
```sql
CREATE INDEX CONCURRENTLY idx_normal_tracks_fid_ts_squawk
    ON research.normal_tracks (flight_id, "timestamp")
    WHERE squawk IS NOT NULL;
```

---

### M6. Partial index for `emergency` on positions

SquawkFilter Alison emergency mode filters `emergency IS NOT NULL AND emergency != 'none'`. If emergencies are rare:
```sql
CREATE INDEX CONCURRENTLY idx_positions_emergency
    ON public.positions (hex, ts)
    WHERE emergency IS NOT NULL AND emergency != 'none';
```

---

### M7. Covering index for FilterFlights GROUP BY aggregate

FilterFlights Tier 2 computes `MAX(alt), MAX(gspeed)` per flight_id. A covering index enables index-only scans:
```sql
CREATE INDEX CONCURRENTLY idx_normal_tracks_fid_alt_gspeed
    ON research.normal_tracks (flight_id, alt, gspeed);
```

---

### M8. Integrity events — double LAG() computation

`detect_integrity_events_async` computes `LAG(ts)` twice in the same CTE. Refactor to compute once:

**File:** `rule_based.py:296-353`
**Fix:** Split into a `pre` CTE that computes `LAG(ts) AS prev_ts`, then reference `prev_ts` in the `degraded` CTE.

---

### M9. DarkFlightDetector — global LIMIT truncates later hexes

`LIMIT 200000` with `ORDER BY hex, ts` means early-alphabet hexes get full data while later ones may be silently truncated. Consider per-hex batching or LATERAL pattern.

---

### M10. Partial index for anomaly boolean filter

```sql
CREATE INDEX CONCURRENTLY idx_anomaly_reports_severity
    ON research.anomaly_reports (severity_cnn DESC)
    WHERE is_anomaly = true;
```

---

## LOW Priority Issues

### L1. Remove redundant `DISTINCT` in AreaSpatialFilter Phase 1 LATERAL

The `LATERAL ... LIMIT 1` already guarantees one row per input ID. `SELECT DISTINCT` is unnecessary.

### L2. Remove unnecessary `ORDER BY` in SquawkFilter

Both FR and Alison queries sort by id + timestamp at the DB level, but Python re-groups results anyway. Removing the ORDER BY saves a sort step.

### L3. `fetch_time_range_async` missing `source_type` filter

The time range query doesn't filter `source_type = 'adsb_icao'`, potentially returning a wider range than downstream queries will use.

### L4. GetLearnedPaths — `ILIKE` on small table

Not a performance concern at current scale, but for correctness use `lower(origin) = lower(:origin)` with a functional index if needed.

### L5. AllFlights bounding box filter — consider GiST spatial index

`start_lat BETWEEN X AND Y AND start_lon BETWEEN A AND B` is a 2D range query. A GiST point index would be more efficient than two B-tree range scans, but only matters at scale.

### L6. Consider PostGIS for polygon filtering

Multiple cubes do Python-side ray-casting after fetching all bounding-box rows. PostGIS `ST_Contains()` would push filtering to SQL, reducing data transfer. Only worth it if PostGIS can be enabled on the RDS instance.

---

## Consolidated Index DDL

Run in this order (highest impact first):

```sql
-- Enable trigram extension
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- HIGH: positions hex+ts (serves ~15 queries across 7 cubes)
CREATE INDEX CONCURRENTLY idx_positions_hex_ts
    ON public.positions (hex, ts);

-- HIGH: normal_tracks flight_id+timestamp (serves ~8 queries across 5 cubes)
CREATE INDEX CONCURRENTLY idx_normal_tracks_fid_ts
    ON research.normal_tracks (flight_id, "timestamp");

-- HIGH: flight_metadata time filter
CREATE INDEX CONCURRENTLY idx_flight_metadata_last_seen_ts
    ON research.flight_metadata (last_seen_ts);

-- HIGH: anomaly_reports lookups
CREATE INDEX CONCURRENTLY idx_anomaly_reports_flight_id
    ON research.anomaly_reports (flight_id);

-- HIGH: GIN for array containment
CREATE INDEX CONCURRENTLY idx_anomaly_reports_rule_names_gin
    ON research.anomaly_reports USING GIN (matched_rule_names);

-- HIGH: callsign trigram (ILIKE with leading wildcard)
CREATE INDEX CONCURRENTLY idx_flight_metadata_callsign_trgm
    ON research.flight_metadata USING GIN (callsign gin_trgm_ops);

-- MEDIUM: airport trigram
CREATE INDEX CONCURRENTLY idx_flight_metadata_origin_trgm
    ON research.flight_metadata USING GIN (origin_airport gin_trgm_ops);
CREATE INDEX CONCURRENTLY idx_flight_metadata_dest_trgm
    ON research.flight_metadata USING GIN (destination_airport gin_trgm_ops);

-- MEDIUM: covering index for FilterFlights aggregate
CREATE INDEX CONCURRENTLY idx_normal_tracks_fid_alt_gspeed
    ON research.normal_tracks (flight_id, alt, gspeed);

-- MEDIUM: anomaly severity partial index
CREATE INDEX CONCURRENTLY idx_anomaly_reports_severity
    ON research.anomaly_reports (severity_cnn DESC)
    WHERE is_anomaly = true;
```

---

## Code Changes Required

| File | Line(s) | Change | Priority |
|------|---------|--------|----------|
| `squawk_filter.py` | 199-217 | Add `AND "timestamp" >= :cutoff_epoch` to FR query | MEDIUM |
| `alison_flights.py` | 226-243 | Add `AND ts >= :cutoff` to polygon post-filter query | MEDIUM |
| `get_flight_course.py` | 78-99 | Add optional `time_window_hours` param + time filter | MEDIUM |
| `get_anomalies.py` | 94 | Change `= ANY(matched_rule_names)` to `matched_rule_names @> ARRAY[...]` | HIGH |
| `registration_country_filter.py` | 218-276 | Merge two identical aircraft queries into one | MEDIUM |
| `rule_based.py` | 296-353 | Refactor double LAG() to single computation | MEDIUM |

---

## Validation Queries

Run these against the live database to confirm which indexes already exist:

```sql
-- Check existing indexes on all tables
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE (schemaname = 'public' AND tablename IN ('positions', 'aircraft', 'learned_paths'))
   OR (schemaname = 'research' AND tablename IN ('normal_tracks', 'flight_metadata', 'anomaly_reports'))
ORDER BY schemaname, tablename, indexname;

-- Table sizes
SELECT schemaname, relname, reltuples::bigint AS row_estimate,
       pg_size_pretty(pg_total_relation_size(schemaname || '.' || relname)) AS total_size
FROM pg_stat_user_tables
WHERE (schemaname = 'public' AND relname IN ('positions', 'aircraft', 'learned_paths'))
   OR (schemaname = 'research' AND relname IN ('normal_tracks', 'flight_metadata', 'anomaly_reports'));

-- Check partitioning
SELECT inhparent::regclass AS parent, inhrelid::regclass AS partition
FROM pg_inherits
WHERE inhparent IN ('public.positions'::regclass, 'research.normal_tracks'::regclass);

-- Check pg_trgm availability
SELECT * FROM pg_available_extensions WHERE name = 'pg_trgm';
```
