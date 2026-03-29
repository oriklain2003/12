# Feature Research

**Domain:** Flight behavioral analysis and anomaly detection cubes for ADS-B/Tracer 42 data
**Researched:** 2026-03-29
**Confidence:** HIGH for cube design and thresholds (derived from existing codebase, domain analysis, Tracer 42 DB schema); MEDIUM for industry standard thresholds (no authoritative public specification found — values below are derived from domain reasoning and existing DarkFlightDetector patterns)

---

## Scope Note

This is a SUBSEQUENT MILESTONE feature document for v4.0. The visual canvas, cube execution engine, workflow CRUD, and all v3.0 AI agents are already built. This covers only the new v4.0 additions: behavioral analysis cubes, route statistics cubes, and parameter enhancements to existing cubes.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that analysts in the Tracer 42 ecosystem assume exist given the new behavioral analysis scope. Missing these makes the v4.0 milestone feel incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| No Recorded Takeoff detection | The "first track report at altitude" pattern is a fundamental ADS-B anomaly — every analyst using Tracer 42 knows dark/shadow flight starts this way. Already partially referenced in existing anomaly rules ("היעדר טביעה מסחרית"). | MEDIUM | Query `normal_tracks` for flight's first position: if `alt` > threshold AND no preceding ground-level reports, flag it. Threshold: 300ft is conservatively "airborne" for ADS-B; existing `DarkFlightDetectorCube` already uses 1000ft for the airborne gap check. 300–500ft is the right range for "no takeoff recorded". |
| Unusual Takeoff Location detection | If an aircraft historically departs from LLBG but today's first track position is 40km away, that's significant. This is the most actionable spatial anomaly. | MEDIUM | Uses `start_lat`/`start_lon` from `flight_metadata` (populated from first track point). Compare against historical centroid of departure positions for same origin airport or callsign. Distance threshold: 5–10 NM (9–18 km) is appropriate — commercial aircraft are within 2 NM of gate at taxi; 5 NM flags something genuinely off-airport. |
| Unusual Takeoff Time detection | Schedule-based anomalies are table stakes for any pattern-of-life tool. Bellingcat's Turnstone, FR24 intelligence tools, and Tracer 42's own anomaly rules all address temporal deviations. | MEDIUM | Group historical flights by route (origin_airport + destination_airport) or callsign; compute mean + stddev of departure hour. Flag flights outside ±N stddev. Default N=2 (95th percentile); configurable. Lookback default: 90 days. |
| Origin/Destination Verification | Comparing actual vs. historical O/D pairs is fundamental to any route-based intelligence analysis. If LY101 always flies TLV→NYC but today files TLV→Istanbul, that's a reportable event. | MEDIUM | Query historical `flight_metadata` for callsign/airline; build O/D frequency distribution; flag current flight if its O/D pair appears in <5% of historical flights or never appeared. |
| Route statistics (avg flights per route) | Users expect to be able to ask "how often does this route operate?" as a baseline before judging anomalies. The Tracer 42 DB has 113K flights — rich enough for meaningful route frequency stats. | LOW | `GROUP BY origin_airport, destination_airport` with COUNT and AVG by time window. Pure SQL aggregation, no track queries needed. |
| Duration filtering on behavioral cubes | The existing `FilterFlights` cube already has duration filtering via `first_seen_ts`/`last_seen_ts`. New behavioral cubes should accept the same flight metadata input and honor the same duration semantics. | LOW | Applies to all new cubes that accept `flight_ids` or `full_result` input — filter flights shorter than min or longer than max before behavioral analysis. |
| Lookback / datetime toggle | Analysis queries that scan historical data (baseline computation) need configurable time windows. "Last 90 days" for baseline is the standard, but analysts need overrides. | LOW | Add `lookback_days` (relative, e.g., 90) and optional `start_time`/`end_time` (absolute epoch strings) to all historical-query cubes. Same pattern already in `AllFlights`. When both are provided, absolute wins. |

### Differentiators (Competitive Advantage)

Features specific to Tracer 42's data model that differentiate from generic aviation analytics tools.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Average flights per day-of-week breakdown | Route frequency analysis gains significant intelligence value when broken down by day of week. A charter flight that always runs Sunday–Tuesday but now appears Wednesday is suspicious. Generic tools (OAG, FR24) show raw counts; this shows anomaly-weighted deviation from day-of-week baseline. | LOW | `GROUP BY EXTRACT(DOW FROM to_timestamp(first_seen_ts)), origin_airport, destination_airport` — pure SQL, no track access. Output: 7-element distribution per route. |
| Deviation scoring (not just boolean flags) | Each behavioral cube should output a numeric `deviation_score` (0.0–1.0) rather than a binary flag. This lets analysts chain `CountByField` or `FilterFlights` downstream to rank anomalies. Existing `DarkFlightDetectorCube` already uses this pattern. | LOW | Normalize distance/time deviations to 0–1 scale. For takeoff location: `min(distance_nm / 50.0, 1.0)`. For takeoff time: `min(z_score / 4.0, 1.0)`. |
| Accepts Full Result port on all new cubes | All existing cubes use `accepts_full_result=True` on their primary input — new cubes must follow the same pattern for pipeline compatibility. This is what makes all new cubes droppable after `AllFlights` or `FilterFlights` without explicit parameter wiring. | LOW | Standard pattern already established. Every new cube gets a `full_result` input parameter with `accepts_full_result=True`. |
| Extensible O/D verification framework | The O/D Verification cube is explicitly designed for extension: the same historical-comparison pattern applies to aircraft type, route altitude, callsign format changes, etc. Building it with a pluggable "what to compare" structure makes future cubes trivial to add. | MEDIUM | Output `verification_results` as an array of `{flight_id, check_name, expected, actual, deviation_score, flagged}` objects — supports multiple check types per flight in one cube run. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time / live baseline updates | "Compare against flights from the last hour" sounds powerful | `research.flight_metadata` is historical (113K rows, not live feed); rebuilding baselines from a constantly-changing window creates inconsistent results across workflow runs | Use fixed `lookback_days` window; document that baseline reflects data at execution time |
| ML-based anomaly scoring | "Use machine learning to find anomalies" feels more sophisticated | Requires model training, versioning, and a feature store — vastly out of scope; the 113K-flight dataset is adequate for statistical baselines but small for supervised anomaly detection | Use statistical baselines (mean ± stddev, z-score) — Gaussian model is defensible and interpretable |
| Per-aircraft learning (individual tail number baseline) | "This specific aircraft always departs at 3am" is compelling | Tracer 42's `research.flight_metadata` schema doesn't have reliable per-registration data for individual aircraft learning (hex/registration is inconsistent) | Route-level baselines (origin_airport + destination_airport + callsign prefix) are more data-dense and reliable |
| Configurable anomaly rule engine | "Let analysts write their own detection rules" sounds flexible | Rule engine UI is a product unto itself; massively expands scope | Fixed detection logic in cubes; analysts configure thresholds via cube parameters (what they actually need) |
| Writing detected anomalies back to DB | "Save flagged flights for later review" is a reasonable want | `research` schema is read-only; `public.workflows` is the only writable table | Workflow results are the artifact; analysts save the workflow that found anomalies, not the anomalies themselves |
| PostGIS spatial operations for takeoff location | Using PostGIS `ST_Distance` for precise geographic distance | PostGIS not confirmed available on the RDS instance; existing codebase uses Python ray-casting and bounding-box SQL for all spatial operations | Python-side Haversine distance computation — adequate accuracy (±0.1% error), no DB extension required |

---

## Feature Dependencies

```
[No Recorded Takeoff Cube]
    └──requires──> [AllFlights cube] (source of flight_ids + metadata)
    └──queries──>  [research.normal_tracks] (first track point altitude check)
    └──pattern follows──> [DarkFlightDetectorCube] (airborne threshold pattern)

[Unusual Takeoff Location Cube]
    └──requires──> [AllFlights cube] (start_lat, start_lon from flight_metadata)
    └──requires──> [baseline window of historical flights] (same callsign/route)
    └──uses──> [Haversine distance] (Python-side, no PostGIS)

[Unusual Takeoff Time Cube]
    └──requires──> [AllFlights cube] (first_seen_ts from flight_metadata)
    └──requires──> [baseline window of historical flights] (same callsign/route)
    └──computes──> [mean + stddev of departure hour] (pure Python stats)

[O/D Verification Cube]
    └──requires──> [AllFlights cube] (origin_airport, destination_airport from flight_metadata)
    └──requires──> [baseline window of historical flights] (same callsign)

[Route Statistics Cube]
    └──requires──> [AllFlights cube] (or direct origin/destination string inputs)
    └──queries──> [research.flight_metadata] (pure SQL aggregation)
    └──no track data needed]

[Avg Flights Per Day-of-Week Cube]
    └──requires (or is part of)──> [Route Statistics Cube]
    └──queries──> [research.flight_metadata] (GROUP BY DOW)

[Duration filtering on behavioral cubes]
    └──pattern reuses──> [FilterFlightsCube Tier 1 duration logic]
    └──inputs from──> [flight_metadata first_seen_ts / last_seen_ts]

[Lookback/datetime toggle]
    └──pattern reuses──> [AllFlightsCube time parameter pattern]
    └──applied to──> [All new behavioral cubes with historical queries]
```

### Dependency Notes

- **All new behavioral cubes depend on `AllFlights` upstream.** They accept `full_result` (full_result port) or `flight_ids` directly. This is the established pattern — do not add direct DB query capability as a fallback; require the caller to wire an `AllFlights` or `FilterFlights` upstream.
- **Baseline queries are internal to each behavioral cube.** The cube itself issues the historical-window query using the same flight's `origin_airport`/`callsign` as the grouping key. The user does not need to provide a separate "baseline flights" input — that would require complex multi-wire configuration.
- **No new cubes require track data except `No Recorded Takeoff`.** All other behavioral cubes operate on `flight_metadata` fields only (`start_lat`, `start_lon`, `first_seen_ts`, `origin_airport`, `destination_airport`). Only `No Recorded Takeoff` needs `normal_tracks` to check the first position's altitude.
- **Route Statistics and Day-of-Week are pure aggregation** — no per-flight anomaly logic, just SQL GROUP BY. They can be placed at any point in the pipeline and are safe to run on large flight sets.

---

## MVP Definition

### Launch With (v4.0)

The complete target feature set for this milestone — all features are focused, low-risk, and grounded in available DB data.

- [ ] **Duration filter enhancement on `FilterFlights`** — Already partially built; confirm min/max duration params work with behavioral cube outputs. Low effort, high polish value.
- [ ] **Lookback/datetime toggle parameter** — Standardize across all new cubes and backfill into existing `AllFlights` if not already present. Core to making behavioral baselines configurable.
- [ ] **No Recorded Takeoff cube (`no_recorded_takeoff`)** — Queries `normal_tracks` for first track point altitude; flags flights first seen at >300ft with no preceding ground-level signal. Accepts `full_result` from `AllFlights`.
- [ ] **Unusual Takeoff Location cube (`unusual_takeoff_location`)** — Uses `start_lat`/`start_lon` from `flight_metadata`; computes Haversine distance from historical departure centroid for same callsign/route. Configurable threshold in NM.
- [ ] **Unusual Takeoff Time cube (`unusual_takeoff_time`)** — Uses `first_seen_ts` from `flight_metadata`; computes z-score against historical departure time distribution for same callsign/route. Configurable stddev threshold.
- [ ] **O/D Verification cube (`od_verification`)** — Checks actual `origin_airport`/`destination_airport` against historical O/D distribution for same callsign. Flags new or rare routes. Outputs per-flight verification results with deviation score.
- [ ] **Route Statistics cube (`route_statistics`)** — Aggregates `research.flight_metadata` by route (origin + destination); outputs avg flights per route, total count, min/max/mean duration. Accepts origin/destination filter params or `flight_ids` input.
- [ ] **Avg Flights Per Day-of-Week cube (`flights_per_dow`)** — Aggregates by (origin, destination, day_of_week); outputs a 7-element distribution per route showing typical weekly cadence.

### Add After Validation (v1.x)

- [ ] **Unified behavioral scoring cube** — If analysts routinely wire all 4 detection cubes (no-takeoff, unusual-location, unusual-time, O/D verification) in series, consider a single "Behavioral Anomaly Bundle" cube that runs all checks in one DB round-trip. Add when pipeline complexity feedback warrants it.
- [ ] **Percentile-based thresholds** — Replace fixed stddev thresholds with data-driven percentile cutoffs (e.g., "flag top 5% outliers"). Add when analysts report too many false positives with default stddev=2.

### Future Consideration (v2+)

- [ ] **Per-registration baseline** — Individual aircraft tail-number behavioral profiling. Requires more reliable registration→flight linkage than current DB schema provides.
- [ ] **Cross-callsign meeting detection** — Detecting two aircraft at the same airfield within a time window. Requires the `meeting_detector` cube design from `.planning/new-cubes/02-behavioral-analysis.md`.
- [ ] **ML anomaly scoring** — Replace statistical z-score with trained isolation forest or autoencoder. Requires model lifecycle management out of scope for v4.0.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| No Recorded Takeoff cube | HIGH | MEDIUM (requires normal_tracks query) | P1 |
| Unusual Takeoff Location cube | HIGH | MEDIUM (Haversine + historical baseline query) | P1 |
| Unusual Takeoff Time cube | HIGH | LOW (pure metadata + stats) | P1 |
| O/D Verification cube | HIGH | LOW (pure metadata groupby) | P1 |
| Lookback/datetime toggle | HIGH | LOW (parameter pattern already exists) | P1 |
| Route Statistics cube | MEDIUM | LOW (pure SQL GROUP BY) | P1 |
| Avg Flights Per Day-of-Week cube | MEDIUM | LOW (pure SQL GROUP BY + DOW extraction) | P1 |
| Duration filter enhancement | MEDIUM | LOW (pattern already in FilterFlights) | P2 |
| Unified behavioral scoring bundle | LOW | MEDIUM | P3 |
| Percentile-based thresholds | MEDIUM | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v4.0 launch
- P2: Should have — polish existing, low effort
- P3: Defer to future milestone

---

## Thresholds and Parameters Reference

This section documents the specific parameter defaults and thresholds for each new cube. These are not arbitrary — they follow the domain reasoning and existing code patterns in the codebase.

### No Recorded Takeoff (`no_recorded_takeoff`)

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `min_altitude_ft` | 300 | FAA defines 500ft AGL as "airborne" for traffic pattern purposes; 300ft is a conservative lower bound. Existing `DarkFlightDetectorCube` uses 1000ft for gap detection — for "no takeoff recorded" we want a tighter lower bound. Configurable. |
| `lookback_seconds` | N/A | First track point only — no window needed; this is per-flight, not historical |
| Dependency | `normal_tracks` | Must query first N track points (ORDER BY timestamp ASC LIMIT 5) to find ground-level coverage; if first report is already above threshold, flag it |

### Unusual Takeoff Location (`unusual_takeoff_location`)

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `threshold_nm` | 5.0 | 5 NM (~9.3 km) from historical centroid. Commercial aircraft are within 2 NM of the gate at taxi start. 5 NM flags a genuinely different airport or remote ramp. |
| `lookback_days` | 90 | 90 days of history gives ~10–20 samples on regular routes — sufficient for centroid stability |
| `min_historical_flights` | 3 | Minimum historical flights for baseline validity — below this, output `insufficient_history: true` rather than a false flag |
| Input fields used | `start_lat`, `start_lon` from `flight_metadata` | These are populated from the flight's first track point on ingest |

### Unusual Takeoff Time (`unusual_takeoff_time`)

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `threshold_stddev` | 2.0 | 2 standard deviations = ~95.4% of normal distribution. Flags top ~5% outliers. Industry statistical anomaly detection research (PMC 2025) confirms Gaussian model is standard for departure time baselines. |
| `lookback_days` | 90 | 90 days as for location |
| `min_historical_flights` | 5 | Need at least 5 data points for meaningful stddev computation |
| Granularity | Hour of day (0–23) | Sub-hour precision not available reliably from bigint epoch timestamps and route variability; hour-level is meaningful for scheduling anomalies |

### O/D Verification (`od_verification`)

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `lookback_days` | 180 | 6 months gives a full seasonal cycle for routes that may be seasonal |
| `rare_route_threshold` | 0.05 | Routes seen in <5% of historical flights for this callsign are flagged as rare/new |
| `min_historical_flights` | 5 | Below this, flag as `insufficient_history` |
| Group key | `callsign` prefix (first 3 chars = airline code) + exact `origin_airport` | Grouping by full callsign (includes flight number) is too narrow; airline+origin gives stable distribution |

### Route Statistics (`route_statistics`)

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `lookback_days` | 30 | 30 days = recent operational tempo. Can be set to 7 (weekly) or 90 (quarterly) |
| `origin_airport` | None (required or from `flight_ids`) | Either pass explicit airport codes or wire `flight_ids` from upstream |
| `destination_airport` | None (optional) | If omitted, returns all destinations from specified origin |

### Flights Per Day of Week (`flights_per_dow`)

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `lookback_days` | 90 | 90 days = 12–13 occurrences of each day of week — sufficient for stable distribution |
| Output | Array of 7 objects `{day_of_week: 0-6, avg_flights: float, total_flights: int}` | 0=Sunday per PostgreSQL `EXTRACT(DOW ...)` convention |

---

## Database Fields Available for Behavioral Analysis

These are the `research.flight_metadata` columns confirmed available from existing cube code:

| Column | Used By |
|--------|---------|
| `flight_id` | All cubes |
| `callsign` | Unusual Takeoff Time, O/D Verification (grouping key) |
| `airline` | O/D Verification (airline code extraction) |
| `first_seen_ts` | Unusual Takeoff Time (bigint epoch), Duration filtering |
| `last_seen_ts` | Duration filtering |
| `origin_airport` | Route Statistics, O/D Verification, Flights Per DOW |
| `destination_airport` | Route Statistics, O/D Verification, Flights Per DOW |
| `start_lat`, `start_lon` | Unusual Takeoff Location |
| `end_lat`, `end_lon` | O/D Verification supplement |
| `min_altitude_ft`, `max_altitude_ft` | No Recorded Takeoff (supplementary) |
| `is_anomaly` | No Recorded Takeoff (correlate with existing flags) |

`research.normal_tracks` columns (used only by No Recorded Takeoff):

| Column | Purpose |
|--------|---------|
| `flight_id` | Join key |
| `alt` | Altitude in feet at each track point |
| `ts` (timestamp) | Sort to find first report |
| `lat`, `lon` | Position of first report |

---

## Competitor Feature Analysis

| Feature | Bellingcat Turnstone | FR24 Intelligence (API) | 12-flow v4.0 |
|---------|---------------------|-------------------------|--------------|
| No-takeoff detection | Manual inspection only | Not a product feature | Automated: first track altitude check, configurable threshold |
| Unusual departure location | Manual geo comparison | Not exposed to users | Automated: Haversine vs historical centroid |
| Unusual departure time | Manual time-series review | Not exposed to users | Automated: z-score vs historical DOW/hour distribution |
| Route O/D verification | Manual callsign history lookup | Flight summary API (raw data, no anomaly scoring) | Automated: rare route flagging with deviation score |
| Route frequency stats | Time-series chart (manual read) | `flight_summary` endpoint (raw) | Cube output: avg/total with DOW breakdown |
| Day-of-week breakdown | Chart visualization | Not structured as anomaly feature | Structured 7-element distribution output, connectable to downstream cubes |
| Historical baseline | Manual, researcher-defined | Researcher builds their own | Configurable `lookback_days` with auto-baseline, `min_historical_flights` guard |

---

## Sources

- Existing codebase: `backend/app/cubes/dark_flight_detector.py` — airborne altitude threshold pattern (1000ft for gaps; 300ft as lower bound for "no takeoff")
- Existing codebase: `backend/app/cubes/filter_flights.py` — duration filter pattern using `first_seen_ts`/`last_seen_ts`
- Existing codebase: `backend/app/cubes/all_flights.py` — confirmed `flight_metadata` schema: `start_lat`, `start_lon`, `first_seen_ts`, `last_seen_ts`, `origin_airport`, `destination_airport`
- `.planning/new-cubes/02-behavioral-analysis.md` — `pattern_of_life` cube spec: baseline_days=90, analysis_days=7, sensitivity=2.0 stddev — validated these defaults
- [Bellingcat Turnstone Tool (2026)](https://www.bellingcat.com/resources/2026/03/05/turnstone-flight-tracking-tool/) — confirms manual baseline comparison is current SOTA for OSINT flight analysis; automated deviation scoring is a differentiator
- [Machine learning anomaly detection in commercial aircraft — PMC 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC11801582/) — Gaussian statistical model with mean±stddev is standard for aviation departure time anomaly detection
- [Recent Advances in Anomaly Detection Methods Applied to Aviation — MDPI](https://www.mdpi.com/2226-4310/6/11/117) — confirms statistical baseline approaches; Gaussian model is most common

---

*Feature research for: Flight behavioral analysis cubes — 12-flow v4.0 milestone*
*Researched: 2026-03-29*
