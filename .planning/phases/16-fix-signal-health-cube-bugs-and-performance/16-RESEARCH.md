# Phase 16: Fix Signal Health Cube Bugs and Performance — Research

**Researched:** 2026-03-13
**Domain:** FastAPI async Python, SQLAlchemy async, asyncio concurrency, PostgreSQL batch queries
**Confidence:** HIGH

## Summary

Phase 16 is a surgical bug-fix and performance refactor of the signal health detection system
(`signal_health_analyzer.py`, `rule_based.py`, `kalman.py`). The bugs and performance issues are
fully documented in `docs/signal_health_analysis.md`, which was authored specifically for this
phase and contains exact code examples for every fix required.

The central problem is a query architecture inversion: the original batch scripts use 3 SQL
queries for any number of aircraft, while the Phase 14 port issues 4 queries per hex (up to
4,001 queries for 1,000 hexes). Fixing this requires replacing per-hex async functions with
batch async equivalents that use `WHERE hex = ANY(:hexes)` and partition results in Python.

The secondary problems are: CPU-bound Kalman/numpy work running synchronously on the async
event loop (blocking all coroutines during math), a `_serialize_datetimes()` deep copy that
walks 10,000-item result structures per hex, a coverage baseline that returns `{}` on first
call causing silent wrong classifications, a lookback window silently reduced from 30 days to
3 days, a missing `n_severe_alt_div` field from Kalman events, and dead fallback code inside
`classify_flight_async()` that fires a redundant DB query if called without timestamps.

**Primary recommendation:** Implement batch async functions in `rule_based.py` and `kalman.py`,
restructure `signal_health_analyzer.py` execute() to use the bulk-fetch + Python fan-out
pattern, wrap CPU-bound Kalman work in `run_in_executor`, move coverage baseline pre-warm to
FastAPI lifespan hook, fix lookback defaults, restore `n_severe_alt_div`, and eliminate the
`_serialize_datetimes()` deep copy.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Batch query migration
- Replace per-hex query functions with batch-only equivalents (`WHERE hex = ANY(:hexes)`)
- No dual per-hex/batch — single batch implementation that works for 1 hex or many
- Batch functions return `dict[str, list[dict]]` keyed by hex, partitioned in Python after fetch
- `_analyze_hex()` loop replaced by bulk fetch → in-memory fan-out pattern (as described in analysis doc section 2)

#### CLI script compatibility
- Do NOT modify `scripts/detect_batch.py`, `scripts/detect_rule_based.py`, or `scripts/detect_kalman.py`
- These scripts are separate from the cube system and will remain as-is
- If signature differences exist between scripts and `app.signal.*` modules, that's acceptable — scripts import their own local functions

#### Coverage baseline startup behavior
- Load coverage baseline at app startup via FastAPI lifespan hook (background, non-blocking)
- Lookback window: 48 hours (not 7 or 30 days)
- No TTL refresh or periodic updates — load once at startup, stays in memory
- Log progress during build (start, cell count, duration)
- Requests before baseline is ready use whatever is available (empty dict if still building)

#### Default lookback for detection queries
- Default `lookback_hours` should be 24 hours (1 day), not the current value
- Users want to see flights from the last day by default
- Still configurable via cube input parameter

#### Code quality
- Code must be clean and readable — prioritize clarity over cleverness
- Avoid unnecessary abstractions, deep nesting, or overly compact patterns

### Claude's Discretion
- Event loop blocking fix: offload CPU-bound Kalman/physics to `run_in_executor` as needed
- `_serialize_datetimes()` removal/optimization — serialize only what the API returns
- `n_severe_alt_div` restoration in `kalman_event_from_result()`
- Redundant `fetch_time_range_async()` cleanup inside `classify_flight_async()`
- Exact batch query chunking strategy (e.g., 200-hex chunks for positions)
- Test updates to match new batch signatures

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

## Standard Stack

### Core (all already installed)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| SQLAlchemy async | Already installed | Async DB access via `engine.connect()` + `text()` | Pattern used by all cubes |
| asyncio | stdlib | `run_in_executor`, `asyncio.gather`, `asyncio.Lock` | Already used throughout |
| numpy | Already installed | Kalman filter matrix math | CPU-bound, must go in executor |
| scipy | Already installed | `scipy.linalg.inv` in Kalman filter | CPU-bound, must go in executor |
| FastAPI | Already installed | Lifespan hook for baseline pre-warm | Replace `@app.on_event("startup")` |

No new libraries needed. All dependencies are already present.

---

## Architecture Patterns

### Pattern 1: Batch SQL with Python Fan-Out

The core pattern replacing per-hex queries. One query returns results for all hexes; Python
partitions into a dict keyed by hex.

```python
# Source: docs/signal_health_analysis.md section 2
async def detect_integrity_events_batch_async(
    hex_list: list[str],
    start_ts: datetime,
    end_ts: datetime,
) -> dict[str, list[dict]]:
    """One query for all hexes — returns {hex: [events]}."""
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            WITH degraded AS (
                SELECT ts, hex, lat, lon, nac_p, nic, version, sil, gva, nac_v, ...
                FROM positions
                WHERE source_type = 'adsb_icao'
                  AND on_ground = false
                  AND lat IS NOT NULL
                  AND hex = ANY(:hex_list)   -- key: one query, all hexes
                  AND ts >= :start AND ts <= :end
                  AND (...)
            ),
            events AS (
                SELECT *, SUM(event_start) OVER (PARTITION BY hex ORDER BY ts) AS event_id
                FROM degraded
            )
            SELECT hex, event_id, min(ts), max(ts), ...
            FROM events
            GROUP BY hex, event_id
            HAVING max(ts) - min(ts) >= INTERVAL '30 seconds'
            ORDER BY hex, min(ts)
        """), {"hex_list": hex_list, "start": start_ts, "end": end_ts})

        by_hex: dict[str, list[dict]] = {}
        for row in result.fetchall():
            ev = _row_to_integrity_event(row)
            by_hex.setdefault(ev["hex"], []).append(ev)

    return by_hex
```

**SQLAlchemy note:** PostgreSQL array binding with async SQLAlchemy text() requires passing a
Python list directly — `{"hex_list": hex_list}` works with `ANY(:hex_list)` syntax.

### Pattern 2: Positions Fetch with 200-Hex Chunking

Positions table is large; chunks prevent parameter list overflow and allow progress logging.

```python
# Source: docs/signal_health_analysis.md section 2 + scripts/detect_batch.py KALMAN_CHUNK_SIZE=200
async def fetch_positions_batch_async(
    hex_list: list[str],
    start_ts: datetime,
    end_ts: datetime,
    chunk_size: int = 200,
) -> dict[str, list[dict]]:
    """Fetch positions for all hexes in chunks of 200."""
    by_hex: dict[str, list[dict]] = {}
    for i in range(0, len(hex_list), chunk_size):
        chunk = hex_list[i:i + chunk_size]
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT ts, hex, lat, lon, alt_baro, alt_geom, gs, tas, track,
                       true_heading, nac_p, nic, baro_rate, geom_rate, on_ground
                FROM positions
                WHERE hex = ANY(:hexes)
                  AND source_type = 'adsb_icao'
                  AND on_ground = false
                  AND lat IS NOT NULL
                  AND ts >= :start AND ts <= :end
                ORDER BY hex, ts
            """), {"hexes": chunk, "start": start_ts, "end": end_ts})
            cols = list(result.keys())
            for row in result.fetchall():
                d = dict(zip(cols, row))
                by_hex.setdefault(d["hex"], []).append(d)
    return by_hex
```

### Pattern 3: CPU-Bound Work in run_in_executor

```python
# Source: docs/signal_health_analysis.md section 3
loop = asyncio.get_event_loop()
kalman_results = await loop.run_in_executor(None, kalman_filter, positions)
jumps          = await loop.run_in_executor(None, detect_position_jumps, positions)
alt_div        = await loop.run_in_executor(None, detect_altitude_divergence, positions)
physics        = await loop.run_in_executor(None, physics_cross_validation, positions)
# classify_flight is fast pure Python — keep sync
classification = classify_flight(kalman_results, jumps, alt_div, physics)
```

Note: `run_in_executor(None, fn, *args)` uses the default `ThreadPoolExecutor`. The functions
must be picklable (they are — pure Python/numpy functions with no closures over non-picklable
objects).

### Pattern 4: FastAPI Lifespan Hook (replaces @app.on_event)

```python
# Source: docs/signal_health_analysis.md section 7
# main.py — replace @app.on_event("startup") with lifespan context manager
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm before accepting any traffic
    log.info("Building coverage baseline...")
    asyncio.create_task(_build_baseline_background())  # non-blocking
    yield
    # cleanup on shutdown if needed

app = FastAPI(lifespan=lifespan)
```

**Context constraint:** Baseline is non-blocking at startup. Requests that arrive before the
baseline is ready use whatever is available (empty dict is acceptable per user decision).
The existing `_build()` fire-and-forget pattern in `get_coverage_baseline()` is the right
mechanism — it just needs to be triggered from the lifespan hook instead of first use.

### Pattern 5: Startup-Only Baseline (no TTL)

Per user decision: load once, no TTL refresh. The module-level `_BASELINE_TTL` and
`_baseline_building` flag should be removed. The baseline is set once at startup and never
invalidated. `get_coverage_baseline()` becomes a simple cache getter.

```python
# rule_based.py — simplified baseline after lifespan pre-warm
_baseline_cache: dict | None = None

async def get_coverage_baseline() -> dict:
    """Return coverage baseline. Built at startup; returns {} if not yet ready."""
    return _baseline_cache if _baseline_cache is not None else {}
```

### Pattern 6: New execute() Structure in SignalHealthAnalyzerCube

The `_analyze_hex()` method is removed. `execute()` is restructured:

1. Compute time range for all hexes: one `fetch_time_range_batch_async()` query
2. `detect_integrity_events_batch_async()` — 1 query all hexes
3. `detect_shutdowns_batch_async()` — 1 query all hexes
4. `fetch_positions_batch_async()` — 1 query per 200-hex chunk
5. Python loop over hexes: score/classify rule events, run Kalman in executor per hex
6. Collect results, apply classify_mode filter

**Total queries:** 3 regardless of hex count (plus chunked positions).

### Anti-Patterns to Avoid

- **Per-hex asyncio.gather inside semaphore:** The current `asyncio.Semaphore(8)` with 3
  concurrent connections each = 24 peak connections saturating the pool. Replace with 3 total
  queries, no semaphore needed.
- **_serialize_datetimes() on full kalman_results:** Never walk the full 10,000-item result.
  Only serialize `start_ts` and `end_ts` fields that are actually returned to the API.
- **Optional timestamps in classify_flight_async:** Remove the `start_ts=None, end_ts=None`
  defaults. Caller must always pass timestamps. Eliminates hidden fallback query.
- **Background baseline build on first request:** Move trigger to lifespan hook so it starts
  at app startup, not when a user first runs the cube.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PostgreSQL array param | Custom escaping | `ANY(:param)` with list value | SQLAlchemy handles psycopg array binding |
| Thread pool for CPU work | Custom pool | `loop.run_in_executor(None, fn, *args)` | Default executor is right size for this |
| Lifespan hook | Custom startup mechanism | FastAPI `lifespan` context manager | Standard pattern, handles startup ordering |
| Concurrent builds lock | Manual flag+check | `asyncio.Lock()` double-checked | Correct pattern for async mutex |

---

## Common Pitfalls

### Pitfall 1: SQLAlchemy ANY() with Python List

**What goes wrong:** `text("WHERE hex = ANY(:hex_list)")` with `{"hex_list": ["a", "b"]}` may
fail depending on driver version — some drivers require explicit cast.

**How to avoid:** Test with the actual async engine. If plain list doesn't work, use
`bindparam("hex_list", value=hex_list, expanding=True)` or cast in SQL:
`WHERE hex = ANY(CAST(:hex_list AS TEXT[]))`.

**Confidence:** MEDIUM — this is known to work with asyncpg driver (used by SQLAlchemy async),
but worth verifying against the actual engine configuration.

### Pitfall 2: run_in_executor Thread Safety

**What goes wrong:** numpy functions called in executor threads are generally thread-safe (they
release the GIL during matrix ops), but any mutable shared state would cause races.

**How to avoid:** Kalman functions take `positions` list (immutable after creation) and return
new lists. No shared state. Safe to use with default ThreadPoolExecutor.

### Pitfall 3: Lifespan vs on_event

**What goes wrong:** `@app.on_event("startup")` is deprecated in recent FastAPI versions.
Mixing it with a `lifespan` parameter raises an error.

**How to avoid:** Replace the existing `@app.on_event("startup") async def warm_db_pool()`
in `main.py` with a single `lifespan` context manager that handles both DB pool warm-up and
baseline pre-warm trigger.

### Pitfall 4: Batch Time Range Query

**What goes wrong:** The current design calls `fetch_time_range_async()` per hex to get
`(start_ts, end_ts)`. With batch architecture, we need a single global time range for the
whole request based on `lookback_hours`, not per-hex min/max detection.

**How to avoid:** Compute the time range in Python from `lookback_hours`:
```python
end_ts = datetime.now(timezone.utc)
start_ts = end_ts - timedelta(hours=lookback_hours)
```
This matches how the batch scripts work: one time window for all hexes. Per-hex time ranges
were only needed because per-hex queries existed.

### Pitfall 5: Test Updates

**What goes wrong:** Phase 15 tests mock `detect_integrity_events_async`, `detect_transponder_shutdowns_async`, and `classify_flight_async` at their import locations. After renaming to batch variants, the mock patch targets need updating.

**How to avoid:** Update test patch paths to the new function names. The test logic itself
(mock return values, assertion structure) should not need to change.

### Pitfall 6: Baseline Lookback Discrepancy

**What goes wrong:** CONTEXT.md says 48 hours, analysis doc section 8 says "restore 30 days".
These conflict.

**Resolution:** CONTEXT.md is locked — use 48 hours. The analysis doc was written before the
discuss-phase session locked this decision. 48 hours is the correct value.

---

## Code Examples

### Time Range Computation (replaces fetch_time_range_async per hex)

```python
# signal_health_analyzer.py — compute once, use for all hexes
from datetime import datetime, timedelta, timezone

end_ts = datetime.now(timezone.utc)
start_ts = end_ts - timedelta(hours=lookback_hours)
```

### n_severe_alt_div Restoration

```python
# signal_health_analyzer.py — kalman_event_from_result()
alt_div = result.get("alt_divergence", [])
n_severe = sum(1 for a in alt_div if a.get("severe"))  # restore from analysis doc section 9

return {
    ...
    "n_alt_divergence": len(alt_div),
    "n_severe_alt_div": n_severe,   # was missing
    ...
}
```

### _serialize_datetimes Elimination

```python
# kalman.py — classify_flight_async() — REMOVE _serialize_datetimes call
# Only serialize the two timestamps the cube reads
return {
    "hex": hex_code,
    "start": start_ts.isoformat() if isinstance(start_ts, datetime) else start_ts,
    "end": end_ts.isoformat() if isinstance(end_ts, datetime) else end_ts,
    "n_positions": len(positions),
    "classification": classification,
    "kalman_results": kalman_results,   # kept as Python dicts — caller only counts
    "jumps": jumps,
    "alt_divergence": alt_div,          # kept as Python dicts — .get("severe") used
    "physics": physics,
    "summary": summary,
}
# _serialize_datetimes() function can be removed entirely
```

### Lifespan Hook Pattern

```python
# main.py — replace @app.on_event("startup") entirely
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    log = logging.getLogger(__name__)
    # DB pool warm-up (was previously @app.on_event("startup"))
    from app.database import engine
    from sqlalchemy import text
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    log.info("DB connection pool warmed")

    # Coverage baseline pre-warm (non-blocking)
    from app.signal.rule_based import start_coverage_baseline_build
    asyncio.create_task(start_coverage_baseline_build())
    log.info("Coverage baseline build started in background")

    yield

app = FastAPI(title="Project 12 — Flow", version="0.1.0", lifespan=lifespan)
```

---

## File-by-File Change Map

### `backend/app/signal/rule_based.py`

| Change | Details |
|--------|---------|
| Remove TTL machinery | Remove `_BASELINE_TTL`, `_baseline_building`, TTL check logic |
| New baseline behavior | Load once at startup; `get_coverage_baseline()` returns cache or `{}` |
| Update lookback | `build_coverage_baseline_async(lookback_hours=48)` — convert hours to days for the SQL |
| Add startup trigger | `start_coverage_baseline_build()` function called from lifespan hook |
| Add `detect_integrity_events_batch_async()` | Batch version with `ANY(:hex_list)`, returns `dict[str, list[dict]]` |
| Add `detect_shutdowns_batch_async()` | Batch version with `ANY(:hex_list)`, returns `dict[str, list[dict]]` |
| Keep per-hex functions | `detect_integrity_events_async()` and `detect_transponder_shutdowns_async()` can be removed or kept — not called by cube after refactor |

### `backend/app/signal/kalman.py`

| Change | Details |
|--------|---------|
| Add `fetch_positions_batch_async()` | Chunked batch fetch, returns `dict[str, list[dict]]` |
| Wrap CPU work in executor | `run_in_executor` for kalman_filter, detect_position_jumps, detect_altitude_divergence, physics_cross_validation |
| Remove `_serialize_datetimes()` | Eliminate function and call site |
| Simplify `classify_flight_async()` | Required timestamps (no optional None), no fallback fetch_time_range call |
| Keep pure computation functions | `kalman_filter`, `detect_position_jumps`, etc. unchanged |

### `backend/app/cubes/signal_health_analyzer.py`

| Change | Details |
|--------|---------|
| Restructure `execute()` | Use batch functions, compute time range in Python |
| Remove `_analyze_hex()` | Replaced by per-hex Python loop after bulk fetch |
| Add `n_severe_alt_div` | Restore in `kalman_event_from_result()` |
| Update imports | Batch function names instead of per-hex names |

### `backend/app/main.py`

| Change | Details |
|--------|---------|
| Replace startup hook | Convert `@app.on_event("startup")` to `lifespan` context manager |
| Add baseline trigger | `asyncio.create_task(start_coverage_baseline_build())` in lifespan |

### `backend/tests/test_signal_*.py`

| Change | Details |
|--------|---------|
| Update patch targets | Patch `detect_integrity_events_batch_async` etc. instead of per-hex names |
| Update mock signatures | Batch functions return `dict[str, list[dict]]` not `list[dict]` |
| `test_signal_rule_based.py` | Tests for `get_coverage_baseline()` need to account for simplified (no TTL) implementation |

---

## State of the Art

| Old Approach | Current Approach | Changed In | Impact |
|--------------|------------------|------------|--------|
| `@app.on_event("startup")` | FastAPI `lifespan` context manager | FastAPI 0.93+ | `on_event` deprecated but functional |
| Per-hex asyncio.gather | Batch SQL + Python fan-out | This phase | 133x fewer queries on 100 hexes |
| Sync CPU in async coroutine | `run_in_executor` for CPU-bound | Python asyncio standard | Event loop unblocked during Kalman math |

---

## Open Questions

1. **SQLAlchemy ANY() list binding**
   - What we know: works in asyncpg driver with Python list directly
   - What's unclear: exact SQLAlchemy version and whether explicit cast needed
   - Recommendation: try plain list first; if binding fails, use `CAST(:hex_list AS TEXT[])` or `bindparam(expanding=True)`

2. **Coverage baseline lookback: hours vs days**
   - What we know: CONTEXT.md says 48 hours; `build_coverage_baseline_async()` currently accepts `lookback_days`
   - What's unclear: whether to change the internal parameter to hours or convert at call site
   - Recommendation: keep internal parameter as `lookback_days`, pass `48/24 = 2` days from the lifespan hook; add a `_BASELINE_LOOKBACK_HOURS = 48` constant for clarity

3. **Per-hex function removal**
   - What we know: `detect_integrity_events_async()` and `detect_transponder_shutdowns_async()` are tested in Phase 15 tests
   - What's unclear: whether to delete them (clean) or keep as internal helpers (safe)
   - Recommendation: keep them but mark as internal with leading underscore OR remove and update the tests — the tests mock DB calls anyway so removal is safe

---

## Sources

### Primary (HIGH confidence)
- `docs/signal_health_analysis.md` — authoritative analysis with exact code examples for all fixes
- `backend/app/cubes/signal_health_analyzer.py` — current implementation, confirmed read
- `backend/app/signal/rule_based.py` — current implementation, confirmed read
- `backend/app/signal/kalman.py` — current implementation, confirmed read
- `backend/app/main.py` — current FastAPI app, startup hook pattern confirmed
- `scripts/detect_batch.py` — original batch pattern reference, `KALMAN_CHUNK_SIZE = 200`
- `.planning/phases/16-fix-signal-health-cube-bugs-and-performance/16-CONTEXT.md` — locked decisions

### Secondary (MEDIUM confidence)
- FastAPI lifespan documentation pattern (from training data, standard since 0.93)
- asyncio `run_in_executor` with ThreadPoolExecutor (Python stdlib docs)

---

## Metadata

**Confidence breakdown:**
- Bug list: HIGH — fully enumerated in analysis doc with code evidence from actual files
- Batch query patterns: HIGH — exact SQL exists in analysis doc and `scripts/detect_batch.py`
- SQLAlchemy ANY() binding: MEDIUM — known to work with asyncpg but exact syntax needs verification against engine
- Lifespan hook: HIGH — standard FastAPI pattern
- Test update scope: HIGH — test files read and patch targets identified

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable domain — no fast-moving dependencies)
