# Requirements: Project 12 — v4.0 Flight Behavioral Analysis

**Defined:** 2026-03-29
**Core Value:** Users can build and run custom flight analysis pipelines visually — now with behavioral analysis cubes that detect anomalies by comparing flights against historical patterns

## v4.0 Requirements

Requirements for v4.0 milestone. Each maps to roadmap phases.

### Cube Infrastructure

- [x] **INFRA-01**: Shared `historical_query.py` module provides `get_callsign_history()` and `get_route_history()` async functions for historical flight lookups
- [x] **INFRA-02**: Shared `epoch_cutoff()` helper computes bigint epoch cutoffs from lookback days, preventing epoch/datetime mixing bugs
- [ ] **INFRA-03**: All new behavioral cubes accept `full_result` input (`accepts_full_result=True`) for drop-in compatibility after AllFlights/FilterFlights
- [x] **INFRA-04**: Historical lookback queries use batch `asyncio.gather()` pattern over unique callsigns, not per-flight loops

### Cube Enhancements

- [x] **ENHANCE-01**: User can filter flights by minimum and maximum flight duration (minutes) on FilterFlights cube
- [x] **ENHANCE-02**: Cubes with historical queries have a datetime/lookback toggle — user can switch between providing a specific datetime range OR a lookback period
- [x] **ENHANCE-03**: Partial datetime input (only start or only end) raises a descriptive validation error instead of silently falling back

### Anomaly Detection

- [ ] **DETECT-01**: User can identify flights with no recorded takeoff — cube flags flights whose first track report is at 300ft+ altitude (configurable threshold)
- [ ] **DETECT-02**: User can detect unusual takeoff locations — cube compares departure point against historical centroid for that callsign/route with configurable distance threshold (default 5 NM)
- [ ] **DETECT-03**: User can detect unusual takeoff times — cube compares departure time against historical mean using circular statistics with configurable stddev threshold (default 2.0)
- [ ] **DETECT-04**: User can verify origin/destination against historical patterns — cube queries callsign's historical flights, finds most common O/D pair, flags deviations
- [ ] **DETECT-05**: All detection cubes output a numeric `deviation_score` (0.0–1.0) alongside boolean flags for downstream ranking
- [ ] **DETECT-06**: All detection cubes output a `diagnostic` field distinguishing "no anomalies found" from "insufficient history" from "empty input"
- [ ] **DETECT-07**: O/D Verification cube uses extensible check pattern (internal `_CHECKS` registry) for future feature growth

### Route Statistics

- [ ] **STATS-01**: User can compute average number of flights per route (origin/destination pair) over a configurable time window
- [ ] **STATS-02**: User can compute average number of flights per day-of-week for a given route, producing a 7-element distribution
- [ ] **STATS-03**: Route statistics cubes output total count, average, min/max alongside distributions

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Detection

- **DETECT-08**: Unified behavioral scoring bundle cube — single cube running all detection checks in one pass
- **DETECT-09**: Percentile-based thresholds — replace stddev cutoffs with data-driven percentiles
- **DETECT-10**: Per-registration baseline (individual tail number tracking)
- **DETECT-11**: Cross-callsign meeting detection

### Advanced Statistics

- **STATS-04**: Route frequency trend analysis (increasing/decreasing over time)
- **STATS-05**: Seasonal pattern detection (monthly/quarterly variations)

## Out of Scope

| Feature | Reason |
|---------|--------|
| ML-based anomaly scoring (isolation forest, autoencoder) | Requires model lifecycle management; statistical baselines are sufficient and interpretable |
| Writing detected anomalies back to DB | `research` schema is read-only; workflow results are the artifact |
| PostGIS spatial operations | Not confirmed on RDS; Python Haversine is adequate |
| Real-time / live baseline updates | `flight_metadata` is historical, not live feed; fixed lookback windows are appropriate |
| Per-aircraft learning (tail number) | Unreliable hex/registration linkage in current schema |
| Configurable anomaly rule engine | Rule engine UI is a product unto itself; cube parameters cover analyst needs |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 23 | Complete |
| INFRA-02 | Phase 23 | Complete |
| INFRA-03 | Phase 24 | Pending |
| INFRA-04 | Phase 23 | Complete |
| ENHANCE-01 | Phase 23 | Complete |
| ENHANCE-02 | Phase 23 | Complete |
| ENHANCE-03 | Phase 23 | Complete |
| DETECT-01 | Phase 24 | Pending |
| DETECT-02 | Phase 25 | Pending |
| DETECT-03 | Phase 25 | Pending |
| DETECT-04 | Phase 26 | Pending |
| DETECT-05 | Phase 24 | Pending |
| DETECT-06 | Phase 24 | Pending |
| DETECT-07 | Phase 26 | Pending |
| STATS-01 | Phase 26 | Pending |
| STATS-02 | Phase 26 | Pending |
| STATS-03 | Phase 26 | Pending |

**Coverage:**
- v4.0 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-03-29*
*Last updated: 2026-03-29 — traceability updated after roadmap creation*
