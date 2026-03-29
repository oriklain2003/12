# Phase 24: No Recorded Takeoff Cube - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

A new detection cube (`no_recorded_takeoff`) that flags flights whose first track point in `research.normal_tracks` is at or above a configurable altitude threshold (default 300 ft). This cube establishes the behavioral output schema pattern (deviation_score + diagnostic + cube-specific flag) that all Phase 25-26 behavioral cubes will follow. It also enriches flagged flights with historical context (typical first altitude for that callsign).

</domain>

<decisions>
## Implementation Decisions

### Deviation Score
- **D-01:** Binary scoring: `deviation_score` = 1.0 if flagged, 0.0 if not. No graduated scaling.
- **D-02:** All input flights appear in output (both flagged and clean). Clean flights get `deviation_score = 0.0`.
- **D-03:** Binary scoring is the **standard for all v4.0 behavioral cubes** (Phases 25-26 follow this pattern). Graduated scoring deferred to future.

### Track Data Source
- **D-04:** Query `research.normal_tracks` for first track point altitude — cleaned track data, already used by GetFlightCourse.
- **D-05:** Cube accepts **both** `full_result` (extracts flight_ids from upstream) **and** a direct `flight_ids` list input. Same pattern as DarkFlightDetector.
- **D-06:** Single batch query with `IN` clause for all flight_ids — one DB round-trip, not asyncio.gather per flight.

### Output Schema (Template for Phase 25-26)
- **D-07:** **Full upstream passthrough** — each output row includes all upstream flight metadata (callsign, flight_id, first_seen_ts, airports, etc.) plus behavioral fields. Downstream cubes can chain without losing context.
- **D-08:** Boolean flag uses **cube-specific name**: `no_recorded_takeoff` (not generic `is_anomaly`). Phase 25-26 cubes follow: `unusual_takeoff_location`, `unusual_takeoff_time`, etc.
- **D-09:** **Single `results` output param** — one list of dicts, each row = one flight with all fields. No split outputs (flight_ids/events/count). Count derivable from `len()`.

### Historical Context
- **D-10:** `diagnostic` field: "insufficient history" means flight_id exists in metadata but has **zero rows in normal_tracks**. Distinct from "empty input" (no flight_ids provided) and "no anomalies found" (flights checked, none flagged).
- **D-11:** Cube **uses `get_callsign_history()`** from Phase 23 for context enrichment — computes `typical_first_alt_ft` (median/mean first-track-point altitude from historical flights for each callsign).
- **D-12:** Historical enrichment applies to **flagged flights only** (no_recorded_takeoff=True). Clean flights don't get the historical comparison.

### Claude's Discretion
- How to compute `typical_first_alt_ft` from historical data (mean vs median)
- Internal query structure for extracting first track point per flight from normal_tracks
- How to handle flights where the callsign has no historical data (set typical_first_alt_ft to null or omit)
- Category assignment (ANALYSIS, consistent with DarkFlightDetector)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — INFRA-03, DETECT-01, DETECT-05, DETECT-06 definitions
- `.planning/ROADMAP.md` — Phase 24 success criteria (4 items), depends on Phase 23

### Existing Cube Patterns
- `backend/app/cubes/dark_flight_detector.py` — Reference for ANALYSIS cube with full_result input, suspicion scoring, and batch query pattern
- `backend/app/cubes/base.py` — BaseCube abstract class with auto __full_result__ output
- `backend/app/cubes/get_flight_course.py` — Reference for querying `research.normal_tracks` (SELECT flight_id, timestamp, lat, lon, alt ... ORDER BY flight_id, timestamp)

### Shared Utilities (Phase 23)
- `backend/app/cubes/utils/historical_query.py` — `get_callsign_history()` for historical enrichment (returns flight metadata rows keyed by callsign)
- `backend/app/cubes/utils/time_utils.py` — `epoch_cutoff()` helper

### Phase 23 Context
- `.planning/phases/23-shared-utility-foundation-duration-filter/23-CONTEXT.md` — Prior decisions (D-04 through D-06) on historical query shape and utils location

### Behavioral Cube Specs
- `.planning/new-cubes/02-behavioral-analysis.md` — Broader behavioral analysis cube designs (pattern_of_life, dark_flight_detector spec)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseCube` (base.py): Abstract base with auto full_result output — extend for new cube
- `get_callsign_history()` (historical_query.py): Batch async historical lookup — use for typical_first_alt_ft enrichment
- `epoch_cutoff()` (time_utils.py): Compute bigint epoch cutoffs from lookback seconds
- `engine` (database.py): Async SQLAlchemy engine for DB connections

### Established Patterns
- ANALYSIS cubes: DarkFlightDetector shows full_result + direct input pattern, suspicion scoring, batch queries
- Track queries: GetFlightCourse uses `research.normal_tracks` with `SELECT flight_id, timestamp, lat, lon, alt` — reuse this column set
- DB queries: Raw SQL via `sqlalchemy.text()` with async connections
- Cube params: `ParamDefinition` with `accepts_full_result=True` for full_result input

### Integration Points
- Cube file: `backend/app/cubes/no_recorded_takeoff.py` — auto-discovered by CubeRegistry
- Inputs: Connects after AllFlights/FilterFlights via full_result or flight_ids
- Outputs: Single `results` list — renderable in frontend results table
- Frontend: No changes needed — cube auto-appears in catalog sidebar under ANALYSIS category

</code_context>

<specifics>
## Specific Ideas

- Historical enrichment adds `typical_first_alt_ft` to flagged rows — lets analysts see "this flight started at 5000ft but this callsign normally starts at 200ft"
- The three diagnostic states map to: "empty input" (no flight_ids at all), "insufficient history" (flight_id has no normal_tracks rows), "no anomalies found" (all flights checked, none above threshold)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 24-no-recorded-takeoff-cube*
*Context gathered: 2026-03-29*
