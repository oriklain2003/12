# Phase 24: No Recorded Takeoff Cube — Research

**Researched:** 2026-03-29
**Phase Goal:** Users can detect flights with no recorded takeoff using the new cube, establishing the behavioral output schema pattern

## 1. Existing Patterns Analysis

### Cube Structure (from DarkFlightDetector)
- ANALYSIS category cube extending `BaseCube`
- Accepts `full_result` input with `accepts_full_result=True` for drop-in chaining
- Also accepts direct parameter inputs (e.g., `flight_ids` list)
- Uses `engine.connect()` + `sqlalchemy.text()` for raw SQL queries
- Returns dict mapping output param names to values

### Input Extraction Pattern (DarkFlightDetector lines 115-127)
```python
# Direct input first, fall back to full_result
direct = inputs.get("hex_list")
if not direct:
    full_result = inputs.get("full_result")
    raw = full_result.get("hex_list") or full_result.get("flight_ids") or []
```
For Phase 24: extract `flight_ids` from direct input or from `full_result` dict. The upstream cubes (AllFlights, FilterFlights) output `flight_ids` as a list and also include full flight metadata rows in their `results` key.

### Full Result Shape from Upstream
AllFlights/FilterFlights `full_result` contains:
- `flight_ids`: list of flight ID strings
- `results`: list of flight metadata dicts with keys: `flight_id`, `callsign`, `first_seen_ts`, `last_seen_ts`, `start_lat`, `start_lon`, `end_lat`, `end_lon`, `origin_airport`, `destination_airport`
- `count`: number of flights

**Key insight:** To do "full upstream passthrough" (D-07), we should use the `results` rows from `full_result` as the base, then enrich each with behavioral fields. This avoids re-querying flight_metadata.

## 2. Database Schema: research.normal_tracks

Columns used by GetFlightCourse (line 69):
```sql
SELECT flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source
FROM research.normal_tracks
WHERE flight_id = ANY(:flight_ids)
ORDER BY flight_id, timestamp
```

- `timestamp`: bigint epoch seconds (not timestamptz) — confirmed by area_spatial_filter comments
- `alt`: altitude in feet (used by FilterFlights as `MAX(alt)` for altitude thresholds)
- Table is range-partitioned on `timestamp` column

### First Track Point Query
To get each flight's first track point altitude:
```sql
SELECT DISTINCT ON (flight_id) flight_id, alt, timestamp, lat, lon
FROM research.normal_tracks
WHERE flight_id = ANY(:flight_ids)
ORDER BY flight_id, timestamp ASC
```
`DISTINCT ON (flight_id)` with `ORDER BY flight_id, timestamp ASC` gives the earliest row per flight — single query, no per-flight round trips. This satisfies D-06 (single batch query).

## 3. Shared Utilities Available (Phase 23)

### historical_query.py
- `get_callsign_history(callsigns, lookback_seconds)` → `{callsign: [metadata_rows]}`
- Uses `asyncio.gather()` per unique callsign
- Returns flight_metadata rows (same columns as AllFlights output)
- Used for D-11: computing `typical_first_alt_ft` from historical flights

### time_utils.py
- `epoch_cutoff(lookback_seconds)` → int epoch cutoff
- `validate_datetime_pair(start_time, end_time)` → error dict or None
- `TIME_MODE_PARAMS` → reusable ParamDefinition list for time mode toggle

### Usage for Historical Enrichment
1. Extract unique callsigns from input flights
2. Call `get_callsign_history()` to get historical flights per callsign
3. For each historical flight set, query `research.normal_tracks` for first track point altitudes
4. Compute median first altitude → `typical_first_alt_ft`

**Decision needed:** The historical enrichment requires a second query (first track points for historical flights). This is separate from the main detection query. Options:
- Single function that does both detection + enrichment in one pass
- Two-step: detect first, then enrich flagged flights only (D-12 says enrichment only for flagged)

**Recommendation:** Two-step approach per D-12. Detection query is simple and fast. Enrichment query only runs for flagged flights' callsigns, keeping DB load proportional to anomalies (not input size).

## 4. Output Schema Design (Template for Phases 25-26)

Per CONTEXT.md decisions:
```python
{
    "results": [
        {
            # Upstream passthrough fields (D-07)
            "flight_id": "...",
            "callsign": "...",
            "first_seen_ts": ...,
            "last_seen_ts": ...,
            "start_lat": ...,
            "start_lon": ...,
            "end_lat": ...,
            "end_lon": ...,
            "origin_airport": "...",
            "destination_airport": "...",

            # Behavioral fields (new)
            "no_recorded_takeoff": True/False,  # D-08: cube-specific boolean
            "deviation_score": 0.0 or 1.0,      # D-01: binary scoring
            "diagnostic": "no anomalies found",  # D-10: one of three states
            "first_alt_ft": 5200,                # cube-specific detail
            "typical_first_alt_ft": 200,         # D-11: historical context (flagged only)
        },
        ...
    ]
}
```

### Diagnostic States (D-10)
1. `"empty input"` — no flight_ids provided at all
2. `"insufficient history"` — flight_id has zero rows in normal_tracks
3. `"no anomalies found"` — flights checked, none above threshold

**Edge case:** What diagnostic to set for clean (unflagged) flights? They were checked and passed → `"no anomalies found"` per flight. The cube-level diagnostic is different from per-row diagnostic.

**Recommendation:** Each row gets its own diagnostic. Flagged rows: `"no anomalies found"` doesn't apply. Clean rows: `"no anomalies found"`. Flights with no track data: `"insufficient history"`. If input is empty: return `{"results": []}` with no rows.

## 5. Configuration Parameters

Per CONTEXT.md and success criteria:
- `altitude_threshold_ft` (NUMBER, default 300): minimum altitude to consider "no recorded takeoff"
- `full_result` (JSON_OBJECT, accepts_full_result=True): upstream chaining
- `flight_ids` (LIST_OF_STRINGS): direct input alternative
- TIME_MODE_PARAMS from time_utils.py: for historical enrichment lookback window

## 6. Implementation Plan Sketch

### Plan 1: Core Cube Implementation
1. Create `backend/app/cubes/no_recorded_takeoff.py`
2. Define inputs (full_result, flight_ids, altitude_threshold_ft, TIME_MODE_PARAMS)
3. Define outputs (single `results` param per D-09)
4. Implement execute():
   a. Extract flight_ids and upstream metadata from inputs
   b. Query first track point per flight from normal_tracks (DISTINCT ON)
   c. Flag flights where first alt >= threshold
   d. Set deviation_score (1.0 flagged, 0.0 clean) and diagnostic per row
   e. Historical enrichment for flagged flights via get_callsign_history()
   f. Return results with upstream passthrough

### Plan 2: Tests
1. Unit tests for the cube with mocked DB responses
2. Test cases: empty input, no track data, all clean, some flagged, historical enrichment

## 7. Risk Assessment

### Low Risk
- Cube follows well-established patterns (DarkFlightDetector, other ANALYSIS cubes)
- Database schema is known (normal_tracks columns confirmed)
- Auto-discovery by CubeRegistry means no registration needed
- Frontend auto-renders ANALYSIS cubes in catalog — no frontend changes

### Medium Risk
- Historical enrichment query performance — mitigated by only enriching flagged flights (D-12)
- `DISTINCT ON` with `ORDER BY` may need index on (flight_id, timestamp) — likely already exists given other cubes query the same pattern

### Validation Architecture

**Testable properties:**
1. Cube appears in catalog API response (`GET /api/cubes/catalog`)
2. Cube accepts full_result from AllFlights output
3. Flights with first alt >= 300ft are flagged with `no_recorded_takeoff: True`
4. Flights with first alt < 300ft have `no_recorded_takeoff: False`
5. `deviation_score` is 1.0 for flagged, 0.0 for clean
6. `diagnostic` is correct per state
7. Flagged flights include `typical_first_alt_ft` from historical data
8. Clean flights do NOT include `typical_first_alt_ft` (D-12)
9. Empty input returns empty results
10. Single DB round-trip for detection (no per-flight queries)

## RESEARCH COMPLETE
