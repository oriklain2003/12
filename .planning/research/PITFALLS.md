# Pitfalls Research

**Domain:** Behavioral analysis cubes added to visual dataflow flight workflow builder (12-flow v4.0)
**Researched:** 2026-03-29
**Confidence:** HIGH — based on direct inspection of codebase, schema, and execution model

---

## Critical Pitfalls

### Pitfall 1: Epoch Arithmetic Against Bigint Timestamp Columns

**What goes wrong:**
A historical lookback query written as `WHERE timestamp >= NOW() - INTERVAL '90 days'` fails silently or returns zero rows because `timestamp` in `research.normal_tracks` is a bigint (Unix epoch seconds), not a native PostgreSQL timestamp. PostgreSQL does not raise an error — it silently coerces or the condition evaluates against the integer value incorrectly. The query completes in milliseconds with zero rows. The developer assumes there is no historical data for the callsign, not that the filter is broken.

**Why it happens:**
The column is named `timestamp`, which implies a timestamp type. The trap is reinforced by `public.positions` (used by `dark_flight_detector.py`) having a native timestamp column — so the pattern of using `datetime.now()` works there but not in `research.normal_tracks` or `research.flight_metadata`. Developers who write one cube then copy the query pattern to another cube without checking column types will import the wrong approach.

**How to avoid:**
Always compute epoch cutoffs in Python before passing as parameters. The existing pattern from `all_flights.py` lines 202-205 is the correct reference:
```python
import time
cutoff = int(time.time()) - (lookback_days * 86400)
# Then: WHERE first_seen_ts >= :cutoff
```
Create a shared utility function `epoch_cutoff(days: int) -> int` in the first phase that adds behavioral cubes. Add a comment near the top of every new cube file: `# NOTE: normal_tracks.timestamp and flight_metadata timestamps are bigint epoch seconds.`

**Warning signs:**
- Query returns 0 rows for a callsign known to have recent history
- Query runs in < 100ms against `normal_tracks` (should take seconds for a real scan)
- Cube uses `datetime.now()`, `datetime.utcnow()`, or `timedelta` objects in SQL params

**Phase to address:**
First phase implementing any historical lookback cube. Establish the shared `epoch_cutoff()` helper before writing the first behavioral cube.

---

### Pitfall 2: N+1 Query Pattern — Per-Flight Historical Lookups

**What goes wrong:**
A behavioral cube receives a list of 200+ flight IDs or callsigns from upstream and issues one SQL query per item to check historical patterns. At 200 flights × 1 query each = 200 round-trips to RDS. At 5ms per query that is 1+ seconds minimum, but on a loaded RDS instance with 200ms latency spikes it reaches 40 seconds. The SSE stream stalls, the client timeout fires, and the user sees the cube stuck in "running" state indefinitely.

**Why it happens:**
The natural Python pattern is a loop: `for callsign in callsigns: result = await conn.execute(query, {"callsign": callsign})`. This reads clearly and works fine on small inputs. The failure mode only appears at scale. Behavioral cubes that compare each flight against its own historical record are especially prone to this — each flight has a unique callsign requiring its own statistics query.

**How to avoid:**
Use `ANY(:array)` to batch all lookups, then `GROUP BY callsign` to produce per-entity results in one query:
```sql
SELECT callsign,
       MIN(first_seen_ts)  AS earliest_seen,
       AVG(start_lat)      AS avg_start_lat,
       AVG(start_lon)      AS avg_start_lon,
       STDDEV(start_lat)   AS stddev_start_lat,
       STDDEV(start_lon)   AS stddev_start_lon,
       COUNT(*)            AS flight_count
FROM research.flight_metadata
WHERE callsign = ANY(:callsigns)
  AND first_seen_ts >= :cutoff
GROUP BY callsign
```
Then join the result dict against the input list in Python. This replaces N queries with 1.

**Warning signs:**
- `for x in input_list:` loop in `execute()` followed by `await conn.execute()`
- Cube execution time scales linearly with upstream result count
- SSE stream shows a cube "running" for 30+ seconds with no output

**Phase to address:**
Every phase implementing a behavioral analysis cube. Make this a code review requirement: no loop-per-item database queries allowed.

---

### Pitfall 3: Result Explosion From Fetching Raw Track Points for Statistical Baselines

**What goes wrong:**
A behavioral cube fetches all raw track points from `normal_tracks` for a callsign across a 90-day window to compute departure location statistics in Python. A busy callsign like `SVA123` might have 500 historical flights × ~400 track points each = 200,000 rows fetched into Python memory per cube execution. The 10,000-row *result* cap in the WorkflowExecutor does not protect against this — it limits what the cube *returns*, not what it fetches internally. Memory spikes, the process is killed by Docker's OOM killer, or the query times out.

**Why it happens:**
The 10,000-row executor cap creates a false sense of safety. Developers assume "the system already handles large results." They do not distinguish between the output row limit and the intermediate data volume inside `execute()`. The existing `filter_flights.py` demonstrates safe patterns (aggregate query, not raw fetch) but new cube authors may not study it.

**How to avoid:**
Push all statistical computation into SQL using aggregate functions. Never `fetchall()` raw track points for the purpose of computing statistics:
```sql
-- Correct: compute stats in DB
SELECT flight_id,
       FIRST_VALUE(lat) OVER (PARTITION BY flight_id ORDER BY timestamp) AS first_lat,
       FIRST_VALUE(lon) OVER (PARTITION BY flight_id ORDER BY timestamp) AS first_lon
FROM research.normal_tracks
WHERE flight_id = ANY(:flight_ids)
```
Or better: use `flight_metadata.start_lat` / `start_lon` columns — these are precomputed takeoff coordinates already stored in the 113K-row metadata table, eliminating the need to touch 76M-row `normal_tracks` at all for departure location analysis.

**Warning signs:**
- `fetchall()` on a `normal_tracks` query without a tight `LIMIT` or `GROUP BY`
- Cube takes 60+ seconds for a single execution
- Docker container OOM killed during cube execution
- `EXPLAIN` shows `rows=76000000` for a full-table estimate

**Phase to address:**
Any phase adding a cube that needs departure location, departure time, or route statistics. Verify the query plan before shipping.

---

### Pitfall 4: Missing Index Coverage for Callsign-Based Historical Lookups

**What goes wrong:**
A new behavioral cube queries `research.normal_tracks` directly by callsign: `WHERE callsign = ANY(:callsigns) AND timestamp >= :cutoff`. If `normal_tracks` lacks a composite index on `(callsign, timestamp)`, this triggers a sequential scan of 76M rows regardless of how tight the time filter is. At the 76M-row scale, a seq scan takes 45-120 seconds — effectively hanging the cube execution.

**Why it happens:**
Existing cubes always filter `normal_tracks` by `flight_id = ANY(:ids)`, which uses whatever index exists on `flight_id`. New behavioral cubes that query by `callsign` directly (which is stored in `normal_tracks` per the schema) bypass that index. The developer tests against a small dev dataset where a seq scan completes in 0.1s, never seeing the production problem.

**How to avoid:**
Avoid querying `normal_tracks` by callsign directly. Use the two-step pattern established in `all_flights.py`:
1. Query `flight_metadata` (113K rows) by callsign to retrieve `flight_ids`
2. Query `normal_tracks` with `flight_id = ANY(:ids)` using the existing index

```python
# Step 1: get flight_ids from the small metadata table
meta_sql = """
    SELECT flight_id FROM research.flight_metadata
    WHERE callsign ILIKE :callsign AND first_seen_ts >= :cutoff
    LIMIT 5000
"""
# Step 2: fetch track aggregates using indexed flight_id lookup
track_sql = """
    SELECT flight_id, MIN(lat) AS first_lat, MIN(lon) AS first_lon
    FROM research.normal_tracks
    WHERE flight_id = ANY(:flight_ids)
    GROUP BY flight_id
"""
```

Before implementing any new SQL query that touches `normal_tracks`, run `EXPLAIN ANALYZE` against the real database to confirm index usage.

**Warning signs:**
- Any `normal_tracks` query where the `WHERE` clause does not include `flight_id = ANY(:ids)`
- Cube runs fine on dev fixtures (small DB) but hangs on production
- `EXPLAIN` output shows `Seq Scan on normal_tracks (cost=0.00..X)` with X in the millions

**Phase to address:**
Before the first historical lookback cube is written. Add `EXPLAIN ANALYZE` as an explicit checklist item in the phase plan.

---

### Pitfall 5: Datetime/Lookback Toggle — Silent Fallback on Partial Input

**What goes wrong:**
A cube implements a datetime/lookback toggle using three optional params: `lookback_days`, `start_time`, and `end_time`. A user connects an upstream cube's `end_time` output to this cube's `end_time` input (so `end_time` is populated by connection) but leaves `start_time` as None (not connected, no manual value). The `connection value override` rule means `end_time` is set from the connection, but the cube's logic checks `if start_time and end_time:` — the condition is False, and it silently falls back to relative mode using `lookback_days`. The connected `end_time` is ignored. The user's intended time filter does nothing.

**Why it happens:**
The toggle requires *both* `start_time` and `end_time` to activate absolute mode. Partial connections cause silent fallback. `all_flights.py` lines 192-205 already has this pattern without a guard for partial state. New cube authors copy this pattern. The UI shows no indication that the connected `end_time` is being ignored.

**How to avoid:**
Add an explicit partial-input guard in every cube with datetime/lookback toggle:
```python
has_start = start_time is not None
has_end = end_time is not None
if has_start != has_end:
    raise ValueError(
        f"Datetime mode requires both start_time and end_time. "
        f"Received start_time={'set' if has_start else 'None'}, "
        f"end_time={'set' if has_end else 'None'}. "
        f"Either connect both or leave both unconnected to use lookback_days."
    )
```
Document the mode toggle in the cube description field so the AI agents can explain the constraint.

**Warning signs:**
- Cube has `start_time`, `end_time`, and `lookback_days` inputs with no validation logic for partial state
- User reports "my time filter is being ignored"
- Analyst connects one time param but not the other — the case to test explicitly

**Phase to address:**
Every phase adding a cube with datetime/lookback toggle. Extract the validation into a shared helper in the cube utilities module.

---

### Pitfall 6: Callsign Reuse Contaminates Historical Baselines

**What goes wrong:**
Commercial callsigns (e.g., `EK416`, `SVA123`) are reused across different flights, different days, and sometimes different aircraft operated under the same airline code. A 90-day baseline built from `callsign = 'EK416'` aggregates flights from multiple rotations — different destination airports for charter substitutions, different departure times across seasons. The "unusual departure time" or "unusual takeoff location" detection fires excessive false positives because the historical baseline spans legitimately diverse operations under the same callsign.

**Why it happens:**
Callsigns appear to be identifiers but are actually flight-schedule numbers. The `flight_metadata` table links `callsign` to `flight_id` and `airline_code`, but not to a single airframe. For behavioral baselines, a narrow identity anchor (ICAO24 hex or registration) is more reliable than callsign alone. Developers unfamiliar with aviation data model assume callsign = aircraft.

**How to avoid:**
For Unusual Takeoff Location and Unusual Takeoff Time cubes: require `airline_code` as a secondary grouping key alongside callsign when building the baseline. For the O/D Verification cube: group historical queries by `(callsign, airline_code)` not `callsign` alone. Document this constraint prominently in each cube's description. Add a `min_historical_flights` input (default: 10) — if fewer than N historical flights match, return a diagnostic instead of flagging false anomalies.

**Warning signs:**
- Baseline query for a common airline callsign returns 5+ distinct `origin_airport` values
- Anomaly rate for known-normal scheduled flights exceeds 30%
- Anomaly score distribution clusters near 0 (baseline too noisy to distinguish deviations)

**Phase to address:**
Phase implementing Unusual Takeoff Location and Unusual Takeoff Time cubes. Add a "minimum baseline quality" check before computing deviations.

---

### Pitfall 7: Threshold Defaults That Are Meaningless for Middle East Airspace

**What goes wrong:**
Statistical threshold defaults (e.g., `sensitivity: 2.0` standard deviations, `min_deviation_nm: 5.0`) are set based on generic aviation patterns. Middle East airspace has different characteristics: shorter domestic routes, more military-adjacent airspace, frequent route deviations around conflict zones, and different traffic density patterns. A 2-stddev sensitivity threshold produces constant false positives for normal regional flights, causing analysts to distrust the cube's output entirely.

**Why it happens:**
Developers set defaults based on documentation examples or Western-airspace assumptions without calibrating against the actual data in `research.flight_metadata` and `research.normal_tracks`. The first time an analyst runs the cube, they see dozens of "anomalous" flights that are obviously normal.

**How to avoid:**
Before finalizing any threshold default, run the query against the production database to establish baseline distributions for the Middle East routes in the dataset. For departure time anomaly: compute the actual standard deviation of `first_seen_ts % 86400` for common callsigns and pick a default sensitivity that produces a false positive rate below 5% on known-normal flights. Document the calibration in the cube description field. Make thresholds prominent first-class inputs, not buried optional params.

**Warning signs:**
- Default threshold values are round numbers (2.0, 5.0, 15) without calibration evidence
- First demo of the cube produces anomaly flags on obviously normal flights
- No calibration note in the cube description or parameter documentation

**Phase to address:**
Every phase implementing a detection/threshold cube. Include a calibration task in the phase plan: "Run default threshold against 30-day dataset; verify false positive rate < 10%."

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use `first_seen_ts` as departure time proxy | No need to query `normal_tracks` for first track point | `first_seen_ts` reflects ADS-B first pick-up, which may be mid-flight for some sources; produces incorrect departure-time baseline for "No Recorded Takeoff" detection | Never for takeoff detection; acceptable for O/D route analysis |
| Skip `EXPLAIN ANALYZE` during development | Faster initial iteration | Queries that run in 0.1s against dev fixtures take 60s in production; discovered only after shipping | Never — always EXPLAIN against prod-scale data before marking a phase complete |
| Python `statistics.stdev()` on fetched rows instead of SQL `STDDEV()` | Simpler Python code | Requires fetching all historical rows into memory; crashes for busy callsigns with 500+ flights | Never for inputs that could exceed 100 rows |
| Hardcode `lookback_days=90` without input parameter | Simpler cube definition | Analyst cannot tune to shorter windows; every run touches maximum data volume | Never — always expose as a configurable input |
| Omit LIMIT on `normal_tracks` historical queries | Avoids truncation of statistical sample | Memory exhaustion and timeout for common callsigns | Never — always add a LIMIT reflecting cube's computational budget |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| WorkflowExecutor input resolution | New cube reads `inputs.get("flight_ids")` expecting a Python list but connection passes a JSON string from upstream serialization | Always normalize: `if isinstance(raw, str): raw = [s.strip() for s in raw.split(",") if s.strip()]` — see `get_flight_course.py` lines 56-57 |
| Full Result port | Behavioral cube reads `full_result["flights"]` directly, crashing when upstream is FilterFlights which uses key `filtered_flights` | Always check multiple keys: `full_result.get("flights") or full_result.get("filtered_flights") or []` |
| Empty `ANY()` array | `WHERE flight_id = ANY(:ids)` with empty Python list causes PostgreSQL type error or silent empty result | Always guard: `if not flight_ids: return early_empty_result` — established pattern in `get_flight_course.py` lines 63-66 |
| Bigint timestamps in output | Cube returns raw `first_seen_ts` bigint; frontend renders it as a 13-digit integer instead of a date | Always convert in Python: `datetime.utcfromtimestamp(ts).isoformat() + "Z"` before returning |
| `public.positions` vs `research.normal_tracks` | Developer copies timestamp handling from `dark_flight_detector.py` (which queries `public.positions` with native timestamp) and applies it to `normal_tracks` (bigint) | The two tables use different timestamp formats; never copy timestamp handling across these tables without checking column type |
| SSE execution timeout | Long historical query (>25s) holds the async event loop; SSE heartbeat misses; client disconnects | Set `SET LOCAL statement_timeout = '20s'` before expensive queries; catch timeout and return partial result with diagnostic message |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Direct callsign query on `normal_tracks` | Seq scan; 45-120s query time | Use two-step: metadata → flight_ids → normal_tracks with `ANY(:ids)` | Immediately on production 76M-row table |
| `fetchall()` without GROUP BY on historical track query | Memory spike; OOM kill | Push all aggregation into SQL; never fetch raw points for statistical computation | Any callsign with > 200 historical flights in the window |
| N+1 per-flight queries in execute() | Linear execution time scaling with input count | Batch all lookups with `ANY(:array)` + `GROUP BY` | Input count > 50 flights |
| Multiple independent connections per cube | Connection pool exhaustion under concurrent workflow runs | Combine related queries within a single `async with engine.connect()` context using CTEs or sequential execution | 4+ behavioral cubes running concurrently in one workflow |
| Python ray-casting inherited from AllFlights polygon filter | Memory spike when bbox returns 100K+ tracks | Cap candidate track fetch at 50K rows; behavioral cubes should avoid polygon-on-tracks patterns entirely | Any polygon filter over Middle East region with large bbox |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| String interpolation of callsign input into SQL | SQL injection via analyst-entered callsign | Always use SQLAlchemy `text()` with `:param` placeholders; established throughout codebase |
| Logging raw SQL with interpolated parameter values at INFO level | Analyst callsigns and flight IDs appear in server logs in plaintext | Log query structure at DEBUG; log parameter keys (not values) at INFO |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Toggle mode params all visible simultaneously | Analyst sees `lookback_days`, `start_time`, and `end_time` with no indication of mutual exclusivity | Use `widget_hint` groups or parameter descriptions to clearly indicate "OR: use these two together / OR: use this one" |
| Threshold params with no units | Analyst sets `sensitivity: 2` thinking it is a percentage; it is standard deviations | Always include units and range in description: "Standard deviations above historical mean. Typical range: 1.5–3.0. Lower = more sensitive." |
| Cube returns 0 results with no diagnostic | Analyst cannot distinguish "no anomalies found" from "callsign has no historical data" from "query misconfigured" | Return a `diagnostic` output key: `{"callsigns_matched": 0, "historical_flights_found": 0, "reason": "No flights found for callsign in lookback window"}` |
| Default lookback of 90 days | First run takes 30+ seconds; analyst waits with no feedback | Default to 30 days; document that longer windows are available; let analyst opt into 90 days |
| Deviation score as raw float only | Analyst does not know if 0.72 is alarming or normal | Expose a `severity` string output (`low / medium / high / critical`) alongside raw score, with documented thresholds in the cube description |

---

## "Looks Done But Isn't" Checklist

- [ ] **Epoch arithmetic:** Every time-based filter uses `int(time.time()) - offset` — not `datetime.now()`, `datetime.utcnow()`, or PostgreSQL `NOW()`
- [ ] **Empty flight_id guard:** Every `ANY(:ids)` query has an early-return before the query when the list is empty
- [ ] **N+1 check:** No `for item in list: await conn.execute()` pattern anywhere in `execute()` — search for loops containing DB calls
- [ ] **EXPLAIN verified:** Every new SQL query touching `normal_tracks` or `flight_metadata` has been tested with `EXPLAIN ANALYZE` against the real database before the phase closes
- [ ] **SQL aggregation:** All statistical computations (mean, stddev, count, percentile) are computed via SQL aggregate functions, not by fetching raw rows into Python
- [ ] **Output key consistency:** Cube output key names match what downstream cubes expect — verify against `ParamDefinition.name` of the expected downstream inputs
- [ ] **Bigint-to-ISO conversion:** Every timestamp in cube output is converted to ISO string, not returned as a raw integer
- [ ] **Full result key fallback:** `full_result` extraction handles multiple possible upstream key names (`flights`, `filtered_flights`, `flight_data`)
- [ ] **Toggle mode validation:** Cubes with `start_time`/`end_time`/`lookback_days` guard against partial input (one of start/end set, other is None)
- [ ] **Threshold defaults calibrated:** All threshold defaults have been validated against production data and produce < 10% false positive rate on known-normal flights
- [ ] **Callsign ambiguity documented:** Any cube using callsign-only historical lookup documents the reuse caveat in its `description` field

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Epoch arithmetic bug (zero results) | LOW | Replace datetime usage with `int(time.time()) - offset`; add unit test with known fixture epoch; redeploy |
| Full table scan discovered post-implementation | MEDIUM | Add two-step metadata→normal_tracks query; no schema changes needed; rewrite query logic only |
| N+1 pattern under load | MEDIUM | Refactor loop into batched `ANY()` query + `GROUP BY`; Python join replaces per-item lookup; test with 500-flight input |
| Memory exhaustion from raw `fetchall()` | HIGH | Requires rethinking computation model: push aggregation into SQL; test with realistic data volume before re-shipping |
| False positive rate too high from callsign reuse | MEDIUM | Add `airline_code` as secondary grouping key; OR add hex input; requires UI parameter addition and logic update |
| Toggle mode silent fallback confusing analysts | LOW | Add partial-input validation guard; raise informative ValueError; manifests as visible error in cube status, not silent wrong output |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Epoch timestamp arithmetic | Every cube phase touching time-based queries | Unit test: pass known bigint epoch, verify correct result; check query plan shows no date-type coercion |
| N+1 query pattern | Every behavioral cube phase | Code review: no loops containing `conn.execute()` in execute() methods |
| Result explosion from raw track fetch | Phases adding historical baseline cubes | EXPLAIN must show index scan not seq scan; memory profile stays under 100MB during execution |
| Missing index coverage | First phase adding historical lookback — before coding begins | Run EXPLAIN ANALYZE on production DB against real table; confirm index scan |
| Toggle mode silent fallback | Phases with datetime/lookback toggle | Integration test: provide only `end_time` without `start_time`; verify ValueError is raised |
| Callsign reuse contaminating baselines | Phases adding unusual-behavior detection | Functional test: run known scheduled-airline callsign through anomaly detection; verify false positive rate < 10% |
| Threshold defaults uncalibrated | Every phase with detection/threshold cube | Calibration task in phase plan: run defaults against 30-day dataset; document false positive rate |
| Empty ANY() list crash | Every cube receiving flight_ids from upstream | Unit test: pass empty `flight_ids`; verify early empty return without DB error |
| Bigint in output | Every cube returning timestamps | Functional test: verify output JSON timestamps are ISO strings, not 10-digit integers |

---

## Sources

- Direct code inspection: `backend/app/cubes/all_flights.py`, `filter_flights.py`, `get_flight_course.py`, `dark_flight_detector.py`, `base.py`
- Schema from `PROJECT.md`: 76M-row `research.normal_tracks` with bigint `timestamp`; 113K-row `research.flight_metadata`; `public.positions` uses native timestamp (contrast case)
- Execution model from `CLAUDE.md` and `backend/app/engine/` (10,000-row output cap applies to returned results, not internal fetches)
- Established patterns: two-step flight_metadata → normal_tracks query in `all_flights.py` (polygon branch); empty-list guard in `get_flight_course.py`; `dark_flight_detector.py` timestamp divergence (lines 89 vs 161-165)
- New cube requirements: `PROJECT.md` v4.0 section (Unusual Takeoff Location, Unusual Takeoff Time, O/D Verification, No Recorded Takeoff)
- Planned behavioral cube specs: `.planning/new-cubes/02-behavioral-analysis.md`

---
*Pitfalls research for: behavioral analysis cubes — visual flight workflow builder (12-flow v4.0)*
*Researched: 2026-03-29*
