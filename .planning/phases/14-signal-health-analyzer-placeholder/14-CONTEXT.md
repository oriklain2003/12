# Phase 14: Signal Health Analyzer - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement `signal_health_analyzer` ANALYSIS cube with real detection logic adapted from the existing `scripts/` detection pipeline. The cube runs on-demand signal health analysis for individual flights (by hex), combining rule-based integrity/shutdown detection with Kalman filter anomaly detection. Alison provider only. Read-only (no DB writes).

</domain>

<decisions>
## Implementation Decisions

### Detection Logic — Ported from scripts/
- **Two detection layers**, both required:
  1. **Rule-based** (from `detect_rule_based.py`):
     - `detect_integrity_events()` — Version-aware NACp/NIC degradation with 30s event segmentation
     - `detect_transponder_shutdowns()` — Mid-flight gap detection (>5 min, airborne, good NACp)
     - `score_event()` + `classify_event()` — 16-point evidence scoring (jam/cov/spf scores) → category classification
     - `build_coverage_baseline()` — 0.5-degree grid with median RSSI for coverage hole detection
  2. **Kalman** (from `detect_kalman.py`):
     - `kalman_filter()` — Constant-velocity Kalman with chi-squared innovation testing
     - `detect_position_jumps()` — Consecutive reports >30 NM apart in <30s
     - `detect_altitude_divergence()` — |alt_baro - alt_geom| > 1000ft
     - `physics_cross_validation()` — Multi-sensor consistency (alt, GS/TAS, track/heading, vrate)
     - `classify_flight()` — Aggregate evidence → gps_spoofing / anomalous / normal

### Provider Support
- **Alison only** — queries `public.positions` (hex, ts, lat, lon, alt_baro, alt_geom, gs, tas, track, true_heading, nac_p, nic, baro_rate, geom_rate, on_ground, rssi, seen_pos, messages, gps_ok_before, gps_ok_lat, gps_ok_lon, version, sil, gva, nac_v, region, source_type, emergency, squawk)
- No FR/research schema support needed
- Input: hex list from upstream AlisonFlights cube

### Database Interaction
- **Read-only** — no writes to any DB tables
- Results returned in-memory as cube outputs
- Coverage baseline query runs against `public.positions` (same as scripts)

### Cube Inputs (from spec)
- `hex_list` (LIST_OF_STRINGS, required) — hex identifiers from AlisonFlights
- `full_result` (JSON_OBJECT) — accepts Full Result from upstream
- `target_phase` (STRING, select: takeoff/cruise/landing/any, default: "any") — flight phase to analyze
- `classify_mode` (LIST_OF_STRINGS, tags, default: ["all"]) — filter output by classification: Stable, Jamming, Spoofing, Dark Target (transponder off), Technical Gaps (coverage holes)

### Cube Outputs
- `flight_ids` (LIST_OF_STRINGS) — hex list of flights with non-normal events matching classify_mode filter
- `count` (NUMBER) — count of matching flights
- `events` (JSON_OBJECT) — array of all non-normal events, each containing:
  - `hex` — aircraft identifier
  - `category` — classification (gps_jamming, gps_spoofing, transponder_off, coverage_hole, probable_jamming, anomalous)
  - `start_ts`, `end_ts` — event time window
  - `duration_s` — event duration
  - `entry_lat`, `entry_lon`, `exit_lat`, `exit_lon` — event coordinates
  - `jamming_score`, `spoofing_score`, `coverage_score` — evidence scores (rule-based events)
  - `evidence` — human-readable evidence string (rule-based events)
  - `classification` — Kalman classification (Kalman events)
  - `n_flagged`, `flag_pct`, `n_jumps`, `n_alt_divergence` — Kalman metrics
  - `physics_confidence` — physics cross-validation confidence (Kalman events)
- `stats_summary` (JSON_OBJECT) — count of events per category across all analyzed flights
- Full Result — auto-bundled

### Classification Mapping (spec labels → detection categories)
- **Stable** → normal (no non-normal events)
- **Jamming** → gps_jamming, probable_jamming (rule-based jam_score ≥ 4)
- **Spoofing** → gps_spoofing (rule-based spf_score ≥ 4 OR Kalman gps_spoofing)
- **Dark Target** → transponder_off (gap detection)
- **Technical Gaps** → coverage_hole, ambiguous (coverage-related)

### Architecture — Detection Modules in backend/app/
- Copy detection logic from `scripts/` into `backend/app/signal/` module
- Adapt from sync psycopg to async SQLAlchemy (same SQL queries, different driver)
- Keep the same constants, thresholds, and scoring logic — proven and tested
- The cube orchestrates: for each hex, run rule-based + Kalman, merge events, filter by classify_mode

### Claude's Discretion
- Exact module structure within `backend/app/signal/`
- How to handle coverage baseline caching (build once per execution vs per hex)
- target_phase filtering implementation (altitude-based flight phase segmentation)
- Performance: whether to batch hexes or process one at a time
- How to handle `classify_mode=["all"]` vs specific category filters

</decisions>

<specifics>
## Specific Ideas

- The detection scripts are proven — user trusts the logic and wants it ported faithfully, not reimplemented
- `detect_batch.py` shows the batch pattern; the cube should be the single-flight on-demand equivalent
- Coverage baseline (`build_coverage_baseline()`) is expensive (~30s on 30 days of data) — consider caching or reducing lookback window for interactive use
- The Kalman layer requires numpy and scipy (for `scipy.linalg.inv`) — these are new backend dependencies
- Rule-based events have scores (jam/cov/spf); Kalman events have different metrics (chi2, jumps, alt_div, physics_confidence) — both should appear in output events with their respective fields
- `classify_mode` maps user-facing labels to internal categories: user selects "Jamming" → cube filters for gps_jamming + probable_jamming events

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/detect_rule_based.py` (850 lines): Full rule-based detection — integrity events, transponder shutdowns, 16-point scoring, classification
- `scripts/detect_kalman.py` (703 lines): Kalman filter, position jumps, altitude divergence, physics cross-validation, flight classification
- `scripts/detect_batch.py` (767 lines): Batch orchestration showing how both layers combine
- `BaseCube` + auto-discovery: Standard cube pattern in `backend/app/cubes/`
- `AlisonFlightsCube`: Template for Alison-only cube with hex_list input/output pattern

### Established Patterns
- Async SQLAlchemy with `text()` for raw SQL — all existing cubes use this
- Safety caps (LIMIT) on large queries
- Dual-layer detection: rule-based runs first, Kalman runs on candidates from rule-based results (see `get_kalman_candidates()` in detect_batch.py)

### Integration Points
- New cube auto-discovered by CubeRegistry — place in `backend/app/cubes/`
- Detection modules go in `backend/app/signal/` — imported by the cube
- Accepts hex_list + full_result from AlisonFlightsCube
- Frontend catalog auto-updates from `GET /api/cubes/catalog`
- New dependencies: numpy, scipy (for Kalman filter)

</code_context>

<deferred>
## Deferred Ideas

- FR provider support (research.normal_tracks) — could be added later but not needed now
- Writing detection results to DB tables (rule_based_events, kalman_events) — the scripts do this but the cube is read-only
- Scheduled/batch detection runs — the scripts handle this; the cube is on-demand
- Additional classification categories or scoring adjustments — iterate after initial deployment

</deferred>

---

*Phase: 14-signal-health-analyzer-placeholder*
*Context gathered: 2026-03-08*
