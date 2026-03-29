# Project Research Summary

**Project:** 12-flow — v4.0 Flight Behavioral Analysis Cubes
**Domain:** ADS-B flight behavioral analysis and anomaly detection for Tracer 42 intelligence workflows
**Researched:** 2026-03-29
**Confidence:** HIGH

## Executive Summary

The v4.0 milestone extends 12-flow's existing visual dataflow canvas with behavioral analysis cubes that compare current flight patterns against historical baselines from the Tracer 42 PostgreSQL database. The research confirms that **no new dependencies are required**: the existing stack (FastAPI, SQLAlchemy async, asyncpg, scipy 1.17.1, numpy 2.4.2, pandas 3.0.1) already provides everything needed for z-score anomaly detection, circular time-of-day statistics, and Haversine distance calculations. The work is entirely in SQL query design and cube implementation — not in acquiring new libraries or changing any existing infrastructure.

The recommended approach follows established patterns already present in the codebase. Five new analysis cubes (`NoRecordedTakeoff`, `UnusualTakeoffLocation`, `UnusualTakeoffTime`, `ODVerifier`, `RouteStats`) plus two aggregation cubes integrate via the existing `BaseCube` drop-in mechanism: place a `.py` file in `backend/app/cubes/`, implement `execute()`, and auto-discovery handles registration. A shared `historical_query.py` utility module should be built first to avoid SQL duplication across the three cubes that need callsign-level historical baselines. All new cubes must accept the `full_result` port to chain naturally after `AllFlights` or `FilterFlights` without explicit wiring.

The primary risks are data-layer traps rather than architectural challenges. Three critical pitfalls dominate: (1) epoch arithmetic — `research.flight_metadata` and `research.normal_tracks` store timestamps as bigint Unix epoch seconds, not native PostgreSQL timestamps, so any cube using `datetime.now()` or `NOW()` in SQL will silently return zero rows; (2) N+1 query patterns — behavioral cubes that loop per-flight and issue per-callsign historical lookups will time out above 50 input flights; (3) direct callsign queries on the 76M-row `normal_tracks` table without a `flight_id` filter trigger full table scans (45–120 seconds). All three are preventable with established patterns already in the codebase.

## Key Findings

### Recommended Stack

No new backend or frontend dependencies are needed. The existing locked versions (`scipy==1.17.1`, `numpy==2.4.2`) provide `scipy.stats.circmean`/`circstd` for circular time-of-day statistics, z-score computation, and all statistical operations required. Python's `statistics` stdlib covers mean/stdev for small in-memory result sets. The key investment is in SQL query patterns: two-tier queries that pull aggregated baselines from `flight_metadata` (113K rows) rather than raw track points from `normal_tracks` (76M rows).

**Core technologies:**
- **scipy.stats** (1.17.1, already installed): z-score anomaly detection, circular time-of-day statistics (`circmean`, `circstd`) — use instead of adding `pyod` or `statsmodels`
- **Python `statistics` stdlib**: in-memory mean/stdev on small SQL result sets — simpler than pandas DataFrames for scalar outputs
- **SQLAlchemy async + asyncpg** (already installed): shared engine singleton, `text()` with `:param` placeholders — no raw asyncpg bypasses
- **`asyncio.gather()`** (stdlib): concurrent callsign history fetches — batch instead of per-flight loop

**What NOT to add:** `pyod` (ML overkill), `statsmodels` (regression not needed), PostGIS/geoalchemy2 (not available on read-only RDS), Redis (premature optimization).

### Expected Features

**Must have (table stakes) — v4.0 launch:**
- No Recorded Takeoff cube — first track point altitude check against `normal_tracks`; threshold 300ft; foundational ADS-B dark-flight signal
- Unusual Takeoff Location cube — Haversine distance vs. historical departure centroid for same callsign/route; threshold 5 NM; uses `flight_metadata.start_lat/start_lon`
- Unusual Takeoff Time cube — z-score vs. historical departure time distribution using circular statistics; threshold 2.0 stddev; uses `flight_metadata.first_seen_ts`
- O/D Verification cube — rare/new route flagging; historical O/D frequency for callsign; 180-day lookback; rare threshold 5%
- Route Statistics cube — SQL GROUP BY aggregation over routes; avg flights per route, total count, min/max duration; 30-day default window
- Avg Flights Per Day-of-Week cube — 7-element DOW distribution per route; `EXTRACT(DOW FROM to_timestamp(...))` pattern
- Lookback/datetime toggle — `lookback_days` + `baseline_start`/`baseline_end` + `time_mode` select; same pattern as `AllFlights`; partial-input guard required

**Should have (competitive differentiators):**
- Deviation scoring (0.0–1.0 normalized float) alongside boolean flags — enables downstream ranking via `FilterFlights`
- `accepts_full_result=True` port on all new cubes — drop-in after any upstream cube without explicit wiring
- Extensible O/D check registry — internal `_CHECKS` list pattern allows future checks without interface changes
- `diagnostic` output key per cube — distinguishes "no anomalies found" from "insufficient history" from "empty input"
- `severity` string output (`low/medium/high/critical`) alongside raw deviation score

**Defer (v2+):**
- Unified behavioral scoring bundle cube — single cube running all 4 detection checks; add only when pipeline complexity feedback warrants it
- Percentile-based thresholds — replace stddev cutoffs with data-driven percentiles; add when false positive feedback arrives
- Per-registration baseline (individual tail number) — unreliable hex/registration linkage in current schema
- Cross-callsign meeting detection — requires separate `meeting_detector` cube design from `.planning/new-cubes/02-behavioral-analysis.md`
- ML anomaly scoring (isolation forest, autoencoder) — requires model lifecycle management out of scope for v4.0

### Architecture Approach

The architecture is additive: drop new cube files into `backend/app/cubes/`, create one shared utility module, and add two duration-filter params to the existing `FilterFlights` cube. No changes to `BaseCube`, `CubeRegistry`, `WorkflowExecutor`, `ParamType` enum, or any frontend components. The shared `historical_query.py` module is the only structural addition — it provides `get_callsign_history()` and `get_route_history()` async functions used by three of the five new cubes. Each analysis cube handles its own historical baseline fetch internally (not as a separate user-facing upstream cube) to keep the canvas clean.

**Major components:**
1. `backend/app/cubes/historical_query.py` — shared async utility; `get_callsign_history()` and `get_route_history()`; returns `list[dict]`; imported directly by analysis cubes
2. `backend/app/cubes/no_recorded_takeoff.py` — queries `normal_tracks` with `flight_id = ANY(:ids)` for MIN(alt); no historical baseline; validates the output schema pattern
3. `backend/app/cubes/unusual_takeoff_location.py` — calls `get_callsign_history`; Python Haversine vs. centroid; `asyncio.gather()` batch pattern
4. `backend/app/cubes/unusual_takeoff_time.py` — calls `get_callsign_history`; `scipy.stats.circmean/circstd` for time-of-day; z-score anomaly detection
5. `backend/app/cubes/od_verifier.py` — extensible `_CHECKS` registry; calls both `get_callsign_history` and `get_route_history`
6. `backend/app/cubes/route_stats.py` — pure Python aggregation over input flight list; no additional DB queries; includes DOW breakdown
7. `filter_flights.py` (modified) — add `min_flight_time_minutes` and `max_flight_time_minutes` params only; no logic restructure

**Key patterns to follow:**
- Full result input acceptance: `accepts_full_result=True` + fallback key handling (`flights` / `filtered_flights`)
- Early empty-list guard before any DB call — `if not flight_ids: return empty_result`
- Batch callsign fetch: `asyncio.gather()` over unique callsigns, then lookup dict for per-flight processing
- Statistical output schema: `{flight_id, callsign, deviation_type, deviation_score, details, historical_sample_size}`
- DB connection released before statistics computation — avoid holding pool slot during CPU work

### Critical Pitfalls

1. **Epoch arithmetic on bigint timestamp columns** — `research.normal_tracks.timestamp` and `flight_metadata.first_seen_ts` are bigint Unix epoch seconds, not native PostgreSQL timestamps. Using `datetime.now()`, `datetime.utcnow()`, or PostgreSQL `NOW()` in SQL silently returns zero rows. Prevention: always compute epoch cutoffs in Python (`int(time.time()) - lookback_days * 86400`) and pass as integer params. Establish `epoch_cutoff()` shared helper in Phase 1.

2. **N+1 query pattern — per-flight historical lookups** — A loop issuing one `conn.execute()` per callsign fails above 50 input flights. Prevention: extract unique callsigns first, batch-fetch with `asyncio.gather()`, build lookup dict, then process flights in pure Python. No `await conn.execute()` inside a `for flight in flights` loop.

3. **Direct callsign query on `normal_tracks` (76M rows)** — Querying `normal_tracks` by `callsign` without a `flight_id` filter triggers a full table scan (45–120 seconds). Prevention: always use the two-step pattern — query `flight_metadata` (113K rows) for `flight_ids` first, then query `normal_tracks` with `flight_id = ANY(:ids)`. Run `EXPLAIN ANALYZE` on every new `normal_tracks` query before closing a phase.

4. **Raw `fetchall()` on track points for statistical baselines** — The 10,000-row executor output cap protects only returned results, not internal memory consumption. A busy callsign with 500 historical flights × 400 track points = 200K rows in Python memory causes OOM. Prevention: push all statistics into SQL `AVG()`, `STDDEV()`, `COUNT()` aggregate functions. Use `flight_metadata.start_lat/start_lon` (precomputed) instead of querying `normal_tracks` for departure location.

5. **Datetime toggle silent fallback on partial input** — If `end_time` is wired but `start_time` is None, the `if start_time and end_time:` guard silently falls back to relative mode. Prevention: add explicit partial-input validation guard that raises a descriptive `ValueError` when exactly one of `start_time`/`end_time` is set.

6. **Callsign reuse contaminating historical baselines** — Commercial callsigns are flight-schedule numbers reused across different rotations and routes. Grouping historical queries by callsign alone produces noisy baselines and excessive false positives. Prevention: add `airline_code` as secondary grouping key; enforce `min_historical_flights` guard (default 10) before computing deviations.

7. **Threshold defaults uncalibrated for Middle East airspace** — Round-number defaults (2.0 stddev, 5 NM) set without production data calibration will fire false positives on normal regional flights. Prevention: run defaults against 30-day production dataset during Phase 3; verify false positive rate < 10% on known-normal flights before marking each cube complete.

## Implications for Roadmap

Based on combined research, a 4-phase build order is recommended. Component dependencies and risk mitigation determine the sequence.

### Phase 1: Shared Utility Foundation + Duration Filter Enhancement

**Rationale:** Three of the five new analysis cubes depend on `historical_query.py`. Building this shared module first allows statistical cubes to be written cleanly and tested in isolation. Duration filter params on `FilterFlights` are self-contained with no dependencies — low-effort, high polish value, and a natural warm-up. This phase also establishes the `epoch_cutoff()` shared helper that every subsequent cube must use; solving the epoch arithmetic pitfall once eliminates it from all future phases.

**Delivers:** `historical_query.py` with `get_callsign_history()` and `get_route_history()`; `epoch_cutoff()` utility; `min_flight_time_minutes` and `max_flight_time_minutes` params on `FilterFlights`

**Addresses:** Lookback/datetime toggle foundation; duration filter enhancement (P2 feature); establishes shared infrastructure for all P1 analysis cubes

**Avoids:** Epoch arithmetic pitfall (correct pattern established once, reused everywhere); N+1 pitfall (batch fetch functions built into the utility from the start)

### Phase 2: No Recorded Takeoff Cube

**Rationale:** This cube requires no historical baseline — it checks only whether the first track point of specific input flights is already at altitude. It establishes the full behavioral cube pattern (finding output schema, `full_result` port, `accepts_full_result`, empty guard, `deviation_score`) on the simplest possible case before introducing statistical complexity. The output schema validated here becomes the template for all subsequent cubes.

**Delivers:** `no_recorded_takeoff.py` with `min_altitude_ft` param (default 300ft); finding output schema validated end-to-end; `accepts_full_result=True` pattern proven

**Addresses:** No Recorded Takeoff detection (P1 feature); finding schema standardized for downstream reuse

**Avoids:** Index pitfall — only queries `normal_tracks` with `flight_id = ANY(:ids)`, which uses the existing index; no historical baseline risk

### Phase 3: Statistical Behavioral Analysis Cubes

**Rationale:** Both `UnusualTakeoffLocation` and `UnusualTakeoffTime` depend on `historical_query.py` from Phase 1 and the output pattern from Phase 2. Location is built before time because Haversine distance comparison is simpler to implement and test than circular time-of-day statistics (`scipy.stats.circmean`). Getting location working first validates the batch-callsign fetch pattern (`asyncio.gather()` + lookup dict) before introducing circular arithmetic.

**Delivers:** `unusual_takeoff_location.py` (Haversine vs. historical centroid, 5 NM threshold, 90-day default); `unusual_takeoff_time.py` (circular mean/stddev, 2.0 stddev threshold, 90-day default); both with datetime/lookback toggle and validated partial-input guard; threshold calibration against production data

**Addresses:** Unusual Takeoff Location (P1 feature); Unusual Takeoff Time (P1 feature); configurable thresholds with production calibration

**Avoids:** Callsign reuse pitfall — `airline_code` secondary grouping key and `min_historical_flights` guard built in; epoch arithmetic — inherits `epoch_cutoff()` from Phase 1; N+1 — `asyncio.gather()` batch pattern required

### Phase 4: O/D Verification + Route Statistics + Aggregation Cubes

**Rationale:** O/D Verification uses both `get_callsign_history` and `get_route_history` and introduces the extensible `_CHECKS` registry pattern — building it after simpler cubes validates the extensibility design against a working foundation. Route Statistics and Flights Per Day-of-Week are pure SQL aggregation with no external dependencies. O/D Verifier is built before route stats because it has higher analytical priority and its extensibility pattern needs early validation.

**Delivers:** `od_verifier.py` with extensible check registry (`new_destination`, `unusual_origin`); `route_stats.py` with avg flights per route and total counts; day-of-week distribution (7-element output per route); 180-day lookback for O/D, 30-day default for route stats

**Addresses:** O/D Verification (P1 feature); Route Statistics (P1 feature); Avg Flights Per DOW (P1 feature)

**Avoids:** Historical baseline as separate upstream cube anti-pattern — all baselines remain internal to each analysis cube; result explosion — route_stats uses in-memory aggregation over already-fetched flight list, not raw track queries

### Phase Ordering Rationale

- `historical_query.py` must precede all statistical analysis cubes — it is a hard dependency for three of five new cubes and establishes the epoch arithmetic pattern
- `NoRecordedTakeoff` before statistical cubes — establishes output schema on the simplest case; no historical baseline risk; a cheap validation of the full-result port pattern
- Location before time in Phase 3 — Haversine is simpler than circular statistics; same batch-fetch infrastructure validates at lower complexity first
- O/D Verifier before route stats in Phase 4 — higher analytical priority; extensibility pattern tested before the simpler aggregation cubes
- Duration filter in Phase 1 — isolated change, unblocks analysts who need duration filtering before behavioral cubes ship

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 3 (statistical cubes):** Threshold calibration requires running default values against production data to verify false positive rate < 10% for Middle East airspace traffic patterns. The thresholds (5 NM, 2.0 stddev) are derived from domain reasoning and literature; they must be validated against real `research.flight_metadata` distributions before the phase can be marked complete. Plan an explicit calibration task in the phase ticket.
- **Phase 4 (O/D Verification):** The extensible check registry pattern needs design validation — specifically, which checks to include in v4.0 vs. what to defer. Review `.planning/new-cubes/02-behavioral-analysis.md` for the full check inventory before committing to the check list.

Phases with standard patterns (skip `/gsd:research-phase`):

- **Phase 1 (shared utility):** Well-established async SQLAlchemy pattern; `epoch_cutoff()` is straightforward arithmetic; duration filter is a param addition only.
- **Phase 2 (No Recorded Takeoff):** Single-step indexed query against `normal_tracks`; no statistical complexity; standard cube pattern.
- **Phase 4 (Route Statistics / DOW):** Pure SQL `GROUP BY` aggregation; no historical baseline complexity; established DOW extraction pattern documented in STACK.md.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All findings grounded in direct inspection of `pyproject.toml`, `uv.lock`, and existing cube code. No new dependencies needed — verified by reading existing cube implementations against v4.0 computational requirements. |
| Features | HIGH | Cube design and thresholds derived from existing codebase patterns and planning docs. MEDIUM confidence on specific threshold values (300ft, 5 NM, 2.0 stddev) — domain-reasoned but not yet calibrated against production data; validation required in Phase 3. |
| Architecture | HIGH | All architecture findings based on direct codebase inspection of `BaseCube`, `CubeRegistry`, `WorkflowExecutor`, and existing cube implementations. No speculation — every pattern references a specific existing cube file. |
| Pitfalls | HIGH | Pitfalls identified by direct inspection of schema (bigint vs. native timestamp divergence between `public.positions` and `research.*`), table row counts, and execution model. The epoch arithmetic trap is directly observable from comparing `dark_flight_detector.py` vs. `all_flights.py` timestamp handling. |

**Overall confidence:** HIGH

### Gaps to Address

- **Threshold calibration:** The specific values for `min_altitude_ft` (300ft), `threshold_nm` (5.0 NM), `threshold_stddev` (2.0), and `rare_route_threshold` (0.05) are derived from domain reasoning and literature citations, not from querying production data. Each Phase 3 implementation task must include an explicit calibration step: run defaults against 30-day production dataset and verify false positive rate < 10% on known-normal flights. Adjust defaults before marking a phase complete.

- **`normal_tracks` index availability:** The research establishes that querying `normal_tracks` by `callsign` (not `flight_id`) triggers a full table scan, but the actual composite index coverage of the table beyond `flight_id` is unconfirmed. Before Phase 2 ships, run `EXPLAIN ANALYZE` against the production RDS instance to confirm the `flight_id` index exists and that the `MIN(alt) GROUP BY flight_id` query plan uses an index scan, not a seq scan.

- **`flight_metadata` column population rates:** `start_lat`, `start_lon`, `callsign`, `origin_airport`, and `destination_airport` are not guaranteed to be populated for all 113K rows (varied ADS-B source quality). The null guard (`f.get("callsign")` pattern) is established as the defensive approach, but the actual null rate for behavioral analysis fields is unknown. If null rates exceed 30% for key fields, the effective coverage of behavioral cubes would be significantly reduced. Worth checking with an exploratory query in Phase 1 before finalizing cube design.

- **Circular time statistics edge case — overnight routes:** `scipy.stats.circmean`/`circstd` correctly handles the 23:50→00:10 wraparound, but the implementation must explicitly convert epoch timestamps to angles in radians (0..2π over 86400 seconds) before passing to scipy. This is documented in STACK.md but easy to implement incorrectly — include explicit unit tests for overnight routes in Phase 3.

## Sources

### Primary (HIGH confidence)
- `backend/app/cubes/all_flights.py` — epoch bigint pattern, datetime toggle, SQL fragment construction
- `backend/app/cubes/filter_flights.py` — GROUP BY aggregate on `normal_tracks` with `flight_id = ANY(:ids)` batch pattern
- `backend/app/cubes/dark_flight_detector.py` — airborne altitude threshold (1000ft), contrast case for `public.positions` native timestamp
- `backend/app/cubes/get_flight_course.py` — `normal_tracks` column schema, empty-list guard pattern
- `backend/app/cubes/signal_health_analyzer.py` — `asyncio.gather()` batch detection pattern
- `backend/pyproject.toml` and `uv.lock` — confirmed dependency versions (numpy 2.4.2, scipy 1.17.1, pandas 3.0.1)
- `backend/app/engine/executor.py`, `registry.py`, `schemas/cube.py`, `database.py` — confirmed execution model and BaseCube contract
- `.planning/PROJECT.md` — column inventory, table row counts, bigint epoch format, v4.0 feature list
- `.planning/new-cubes/02-behavioral-analysis.md` — `pattern_of_life` cube spec, baseline_days=90, sensitivity=2.0 stddev defaults

### Secondary (MEDIUM confidence)
- [PostgreSQL EXTRACT / to_timestamp docs](https://www.postgresql.org/docs/current/functions-datetime.html) — to_timestamp(bigint), EXTRACT(DOW), epoch conversion
- [scipy.stats.circmean / circstd](https://docs.scipy.org/doc/scipy/reference/stats.html) — confirmed available in scipy 1.17.1
- [Bellingcat Turnstone Tool (2026)](https://www.bellingcat.com/resources/2026/03/05/turnstone-flight-tracking-tool/) — confirms manual baseline comparison is current OSINT SOTA; automated deviation scoring is a differentiator
- [Machine learning anomaly detection in commercial aircraft — PMC 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC11801582/) — Gaussian statistical model with mean±stddev is standard for aviation departure time anomaly detection
- [Recent Advances in Anomaly Detection Methods Applied to Aviation — MDPI](https://www.mdpi.com/2226-4310/6/11/117) — statistical baseline approaches; Gaussian model most common

### Tertiary (LOW confidence)
- Threshold defaults (300ft, 5 NM, 2.0 stddev): derived from domain reasoning and existing code patterns. Must be calibrated against production data before marking Phase 3 complete.

---
*Research completed: 2026-03-29*
*Ready for roadmap: yes*
