# Signal Health Analyzer — Performance & Bug Analysis

> **Comparing** `detect_batch.py / detect_rule_based.py / detect_kalman.py` (original)
> **→** `signal_health_analyzer.py / rule_based.py / kalman.py` (agent port)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Root Cause — Query Architecture Inversion](#2-root-cause--query-architecture-inversion)
3. [Performance Issue 2 — Blocking the Async Event Loop](#3-performance-issue-2--blocking-the-async-event-loop)
4. [Performance Issue 3 — _serialize_datetimes() Deep Copy](#4-performance-issue-3--_serialize_datetimes-deep-copy)
5. [Bug 1 — score_event() Signature Changed (Runtime Crash)](#5-bug-1--score_event-signature-changed-runtime-crash)
6. [Bug 2 — classify_event() Signature Changed (Runtime Crash)](#6-bug-2--classify_event-signature-changed-runtime-crash)
7. [Bug 3 — Coverage Baseline Silent Failure on First Call](#7-bug-3--coverage-baseline-silent-failure-on-first-call)
8. [Bug 4 — Baseline Lookback Silently Reduced 30d → 3d](#8-bug-4--baseline-lookback-silently-reduced-30d--3d)
9. [Bug 5 — n_severe_alt_div Dropped from Kalman Events](#9-bug-5--n_severe_alt_div-dropped-from-kalman-events)
10. [Bug 6 — Redundant fetch_time_range_async() Inside classify_flight_async()](#10-bug-6--redundant-fetch_time_range_async-inside-classify_flight_async)
11. [Summary Tables](#11-summary-tables)

---

## 1. Executive Summary

The agent faithfully copied the detection math (Kalman filter, physics checks, scoring rules) but
**completely inverted the query architecture**. The original processes every aircraft in a time window
with 3 total SQL queries. The new code issues 4 queries per hex — on 100 hexes that is ~400 queries
instead of 3.

On top of that, two public function signatures were silently broken, causing `detect_batch.py` to
crash at runtime with `TypeError` and `AttributeError`.

---

## 2. Root Cause — Query Architecture Inversion

### What the original does

`detect_batch.py` was designed from the ground up around **bulk SQL**. It processes every aircraft
in the time window with three queries regardless of how many hexes there are:

```
Step 1  →  detect_integrity_batch()    — 1 CTE scan, all hexes
Step 2  →  detect_shutdowns_batch()    — 1 LAG-window scan, all hexes
Step 3  →  fetch_positions_batch()     — 1 SELECT … ANY(chunk), per 200-hex chunk
           + Python Kalman loop over in-memory results
```

**Total: ~3 queries for any N aircraft.**

The key is `WHERE hex = ANY(%(hexes)s)` — PostgreSQL evaluates one plan for the entire list:

```python
# detect_batch.py — fetch_positions_batch()
def fetch_positions_batch(conn, hexes: list[str], start, end) -> dict[str, list[dict]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT ts, hex, lat, lon, alt_baro, alt_geom, gs, tas, track,
                   true_heading, nac_p, nic, baro_rate, geom_rate, on_ground
            FROM positions
            WHERE hex = ANY(%(hexes)s)          -- ← one query, all hexes
              AND source_type = 'adsb_icao'
              AND on_ground = false
              AND lat IS NOT NULL
              AND ts >= %(start)s AND ts <= %(end)s
            ORDER BY hex, ts
        """, {"hexes": hexes, "start": start, "end": end})

        cols = [d[0] for d in cur.description]
        by_hex: dict[str, list[dict]] = {}
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            by_hex.setdefault(d["hex"], []).append(d)  # partition in Python

    return by_hex  # {hex_code: [positions...]}
```

---

### What the agent does instead

The agent wrote `_analyze_hex()` which opens **4 separate DB round-trips for every single hex**:

```python
# signal_health_analyzer.py — _analyze_hex()  ← called once per hex in asyncio.gather
async def _analyze_hex(self, hex_code, coverage_baseline, target_phase, lookback_hours):

    # Round-trip 1 — new, did not exist in original
    time_range = await fetch_time_range_async(hex_code, lookback_hours=lookback_hours)

    start_ts, end_ts = time_range

    # Round-trips 2, 3, 4 — run concurrently but still 3 separate connections
    integrity_events, shutdown_events, kalman_result = await asyncio.gather(
        detect_integrity_events_async(hex_code, start_ts, end_ts),   # ← was 1 query for ALL hexes
        detect_transponder_shutdowns_async(hex_code, start_ts, end_ts),  # ← was 1 query for ALL hexes
        classify_flight_async(hex_code, start_ts, end_ts),           # ← fetch_positions inside
    )
```

**Query count comparison:**

| Hexes | Original queries | New queries |
|-------|-----------------|-------------|
| 10    | 3               | 41          |
| 100   | 3               | 401         |
| 500   | 5 (3 chunks)   | 2,001       |
| 1,000 | 6 (5 chunks)   | 4,001       |

> **Note on the semaphore:** `asyncio.Semaphore(8)` limits concurrent `_analyze_hex()` calls,
> but each call fires 3 connections simultaneously inside `asyncio.gather`. Peak concurrent
> connections = **8 × 3 = 24**, which likely saturates the SQLAlchemy pool and adds queuing
> wait on top of the already inflated query count.

---

### How it should be written

The fix is to keep the batch SQL pattern and fan out results in Python after a single fetch.
Below is how `execute()` in `SignalHealthAnalyzerCube` should be restructured:

```python
async def execute(self, **inputs: Any) -> dict[str, Any]:
    hex_list: list[str] = inputs.get("hex_list") or []
    # ... (input extraction unchanged) ...

    coverage_baseline = await get_coverage_baseline()

    # ── Step 1: integrity events — ONE query for all hexes ────────────────
    integrity_by_hex = await detect_integrity_events_batch_async(hex_list, start_ts, end_ts)

    # ── Step 2: shutdown events — ONE query for all hexes ─────────────────
    shutdowns_by_hex = await detect_shutdowns_batch_async(hex_list, start_ts, end_ts)

    # ── Step 3: positions for Kalman — ONE query per 200-hex chunk ────────
    positions_by_hex = await fetch_positions_batch_async(hex_list, start_ts, end_ts)

    # ── Step 4: run Kalman in Python on in-memory data ────────────────────
    hex_events: dict[str, list[dict]] = {}

    async def _process_hex(hx: str) -> tuple[str, list[dict]]:
        rule_events = []
        for ev in integrity_by_hex.get(hx, []) + shutdowns_by_hex.get(hx, []):
            scored = score_event(ev, coverage_baseline)
            scored["category"] = classify_event(scored)
            rule_events.append(scored)

        kalman_events = []
        positions = positions_by_hex.get(hx, [])
        if len(positions) >= 3:
            # CPU-bound — run in thread pool so the event loop stays free
            loop = asyncio.get_event_loop()
            kr = await loop.run_in_executor(None, kalman_filter, positions)
            jumps = await loop.run_in_executor(None, detect_position_jumps, positions)
            alt_div = await loop.run_in_executor(None, detect_altitude_divergence, positions)
            physics = await loop.run_in_executor(None, physics_cross_validation, positions)
            classification = classify_flight(kr, jumps, alt_div, physics)
            if classification not in ("normal", None):
                kalman_events.append(kalman_event_from_result(hx, {
                    "classification": classification,
                    "kalman_results": kr,
                    "jumps": jumps,
                    "alt_divergence": alt_div,
                    "physics": physics,
                    "start": positions[0]["ts"].isoformat(),
                    "end": positions[-1]["ts"].isoformat(),
                }))

        return hx, rule_events + kalman_events

    results = await asyncio.gather(*[_process_hex(h) for h in hex_list])
    # ... rest unchanged
```

And the two batch async helpers (ported from the sync batch versions):

```python
# rule_based.py — batch version of detect_integrity_events_async
async def detect_integrity_events_batch_async(
    hex_list: list[str],
    start_ts: datetime,
    end_ts: datetime,
) -> dict[str, list[dict]]:
    """One query for all hexes — returns {hex: [events]}."""
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            WITH degraded AS (
                SELECT ts, hex, lat, lon, nac_p, nic, version, sil, gva, nac_v,
                       alt_baro, alt_geom, gs, region, rssi, seen_pos, messages,
                       gps_ok_before, gps_ok_lat, gps_ok_lon,
                       CASE WHEN LAG(ts) OVER (PARTITION BY hex ORDER BY ts) IS NULL THEN 1
                            WHEN EXTRACT(EPOCH FROM ts - LAG(ts) OVER (PARTITION BY hex ORDER BY ts)) > 30 THEN 1
                            ELSE 0 END AS event_start
                FROM positions
                WHERE source_type = 'adsb_icao'
                  AND on_ground = false
                  AND lat IS NOT NULL
                  AND hex = ANY(:hex_list)       -- ← key difference
                  AND ts >= :start AND ts <= :end
                  AND (
                      (version = 2 AND (nac_p = 0 OR nic < 7))
                      OR (version = 1 AND nac_p = 0 AND (nic = 0 OR gps_ok_before IS NOT NULL))
                      OR ((version = 0 OR version IS NULL) AND gps_ok_before IS NOT NULL)
                  )
            ),
            events AS (
                SELECT *, SUM(event_start) OVER (PARTITION BY hex ORDER BY ts) AS event_id
                FROM degraded
            )
            SELECT hex, event_id, min(ts), max(ts), ...  -- same aggregations as before
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

---

## 3. Performance Issue 2 — Blocking the Async Event Loop

### The problem

All Kalman and physics functions are **synchronous and CPU-bound**. They run directly inside the
async coroutine without being offloaded to a thread. While one hex's Kalman filter runs, **every
other coroutine waits** — including the 7 other concurrent `_analyze_hex()` calls behind the semaphore.

```python
# kalman.py — these are all synchronous
async def classify_flight_async(hex_code, start_ts, end_ts):
    positions = await fetch_positions_async(hex_code, start_ts, end_ts)  # async ✓

    kalman_results = kalman_filter(positions)          # ← blocks event loop (numpy)
    jumps = detect_position_jumps(positions)           # ← blocks event loop (pure Python O(N))
    alt_div = detect_altitude_divergence(positions)    # ← blocks event loop (pure Python O(N))
    physics = physics_cross_validation(positions)      # ← blocks event loop (pure Python O(N))
    classification = classify_flight(...)              # ← blocks event loop
```

With 10,000 positions per hex, `kalman_filter()` runs a numpy matrix loop ~10,000 times.
`asyncio` cannot interrupt a synchronous function — the event loop is frozen for the duration.

---

### How it should be written

Use `run_in_executor` to hand CPU work to a thread pool. The event loop remains free to handle
I/O (DB responses from other hexes) while Python crunches numbers in a worker thread:

```python
async def classify_flight_async(hex_code: str, start_ts: datetime, end_ts: datetime) -> dict:
    positions = await fetch_positions_async(hex_code, start_ts, end_ts)

    if not positions:
        return _empty_kalman_result(hex_code, start_ts, end_ts)

    loop = asyncio.get_event_loop()

    # Run all CPU-bound work in the thread pool — event loop stays free
    kalman_results = await loop.run_in_executor(None, kalman_filter, positions)
    jumps          = await loop.run_in_executor(None, detect_position_jumps, positions)
    alt_div        = await loop.run_in_executor(None, detect_altitude_divergence, positions)
    physics        = await loop.run_in_executor(None, physics_cross_validation, positions)

    # classify_flight is pure Python but fast — ok to keep sync
    classification = classify_flight(kalman_results, jumps, alt_div, physics)

    # ... build and return result dict
```

If multiple hexes run concurrently, the thread pool (default: `min(32, os.cpu_count() + 4)`)
handles all of them in parallel at the OS level, rather than serialising them through the event loop.

---

## 4. Performance Issue 3 — _serialize_datetimes() Deep Copy

### The problem

After running the Kalman filter, `classify_flight_async()` calls `_serialize_datetimes()` which
**recursively walks the entire result structure** — including `kalman_results` with up to 10,000
dicts — to convert datetime objects to ISO strings. This runs once per hex in the hot path:

```python
# kalman.py
def _serialize_datetimes(obj):
    """Recursively convert datetime objects to ISO strings."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize_datetimes(v) for k, v in obj.items()}  # full deep copy
    if isinstance(obj, list):
        return [_serialize_datetimes(item) for item in obj]           # full deep copy
    return obj

async def classify_flight_async(...):
    # ...
    return _serialize_datetimes(result)  # ← walks 10,000-item kalman_results every call
```

The original batch script avoids this entirely — datetimes stay as Python objects and are
formatted only once during the COPY write via `_copy_value()`.

---

### How it should be written

`kalman_event_from_result()` in `signal_health_analyzer.py` only uses `result["start"]`,
`result["end"]`, and summary counts from `kalman_results`. It never needs the full per-point
datetime objects serialized. Serialize only the fields you actually return to the API:

```python
async def classify_flight_async(hex_code, start_ts, end_ts) -> dict:
    positions = await fetch_positions_async(hex_code, start_ts, end_ts)
    # ... run detection ...

    # ✓ Only serialize the two timestamps the cube actually reads.
    # Do NOT walk kalman_results — they are discarded after summary counting.
    return {
        "hex": hex_code,
        "start": start_ts.isoformat() if isinstance(start_ts, datetime) else start_ts,
        "end": end_ts.isoformat() if isinstance(end_ts, datetime) else end_ts,
        "n_positions": len(positions),
        "classification": classification,
        "kalman_results": kalman_results,   # keep as Python dicts — caller only counts them
        "jumps": jumps,
        "alt_divergence": alt_div,
        "physics": physics,
        "summary": summary,
    }
    # No _serialize_datetimes() call needed
```

---

## 5. Bug 1 — score_event() Signature Changed (Runtime Crash)

### The problem

The original `score_event()` returns a plain `tuple[int, int, int]`. The agent rewrote it to
return a full copy of the event dict with scores embedded. **`detect_batch.py` still calls the
old signature and crashes at runtime.**

```python
# detect_rule_based.py — ORIGINAL
def score_event(event, coverage_baseline) -> tuple[int, int, int]:
    # ... scoring logic ...
    return jam, cov, spf        # ← returns three ints


# rule_based.py — NEW (agent version)
def score_event(event, coverage_baseline) -> dict:
    # ... same scoring logic ...
    scored = dict(event)
    scored["jamming_score"] = jam
    scored["coverage_score"] = cov
    scored["spoofing_score"] = spf
    scored["evidence"] = ", ".join(evidence_parts)
    return scored               # ← returns a dict


# detect_batch.py — CALLER (unchanged, still expects old signature)
def score_and_classify(events, coverage):
    for event in events:
        jam, cov_sc, spf = score_event(event, coverage)  # ← TypeError: cannot unpack dict
        category = classify_event(jam, cov_sc, spf)
```

**Error at runtime:**
```
TypeError: cannot unpack non-sequence dict
```

---

### How it should be written

Pick one convention and apply it everywhere. The cleanest fix with least churn is to keep
the dict-return pattern (it is actually more informative) and update the one caller in
`detect_batch.py`:

```python
# rule_based.py — keep the new dict-returning version
def score_event(event: dict, coverage_baseline: dict) -> dict:
    """Score an integrity event. Returns event dict augmented with scores."""
    # ... scoring logic unchanged ...
    scored = dict(event)
    scored["jamming_score"] = jam
    scored["coverage_score"] = cov
    scored["spoofing_score"] = spf
    scored["in_coverage_hole"] = in_hole
    scored["evidence"] = ", ".join(evidence_parts)
    return scored


# detect_batch.py — UPDATE the caller to use the new return type
def score_and_classify(events: list[dict], coverage: dict) -> list[dict]:
    for event in events:
        scored = score_event(event, coverage)           # ← now receives dict
        event["jamming_score"] = scored["jamming_score"]
        event["coverage_score"] = scored["coverage_score"]
        event["spoofing_score"] = scored["spoofing_score"]
        event["category"] = classify_event(scored)      # ← pass dict to classify
        event["evidence"] = scored["evidence"]
    return events


# signal_health_analyzer.py — already correct with new signature
async def _analyze_hex(self, hex_code, coverage_baseline, target_phase, lookback_hours):
    # ...
    for ev in integrity_events:
        scored = score_event(ev, coverage_baseline)     # ← dict ✓
        scored["category"] = classify_event(scored)     # ← dict ✓
        rule_events.append(scored)
```

---

## 6. Bug 2 — classify_event() Signature Changed (Runtime Crash)

### The problem

Same pattern as Bug 1. The original `classify_event()` accepts three separate ints. The agent
rewrote it to accept a single scored-event dict. **`detect_batch.py` still passes three ints.**

```python
# detect_rule_based.py — ORIGINAL
def classify_event(jam_score: int, cov_score: int, spf_score: int) -> str:
    if spf_score >= 4:
        return "gps_spoofing"
    elif jam_score >= 6 or (jam_score >= 4 and jam_score > cov_score):
        return "gps_jamming"
    # ...


# rule_based.py — NEW (agent version)
def classify_event(scored_event: dict) -> str:
    if scored_event.get("source") == "gap_detection":
        return "transponder_off"
    spf_score = scored_event.get("spoofing_score", 0)
    jam_score = scored_event.get("jamming_score", 0)
    # ...


# detect_batch.py — CALLER (unchanged, passes three ints)
category = classify_event(jam, cov_sc, spf)
# ↑ jam is an int — int.get() raises AttributeError
```

**Error at runtime:**
```
AttributeError: 'int' object has no attribute 'get'
```

---

### How it should be written

Update `detect_batch.py` to build a minimal dict and pass it, or update `classify_event()` to
accept both calling conventions. The simplest fix that doesn't break anything else:

```python
# detect_batch.py — fix the caller
def score_and_classify(events, coverage):
    for event in events:
        scored = score_event(event, coverage)   # returns dict
        event.update(scored)                    # merge scores into event
        event["category"] = classify_event(scored)  # pass dict ✓
    return events
```

Or, if you want `classify_event()` to remain usable with raw ints for testing/scripts,
add an overload guard:

```python
# rule_based.py — backwards-compatible classify_event
def classify_event(scored_event_or_jam, cov_score=None, spf_score=None) -> str:
    """Accept either a scored dict or three separate ints (backwards compat)."""
    if isinstance(scored_event_or_jam, dict):
        scored = scored_event_or_jam
        jam_score = scored.get("jamming_score", 0)
        cov_score = scored.get("coverage_score", 0)
        spf_score = scored.get("spoofing_score", 0)
        if scored.get("source") == "gap_detection":
            return "transponder_off"
    else:
        jam_score = scored_event_or_jam  # called as classify_event(jam, cov, spf)

    if spf_score >= 4:
        return "gps_spoofing"
    elif jam_score >= 6 or (jam_score >= 4 and jam_score > cov_score):
        return "gps_jamming"
    elif cov_score >= 2 and cov_score > jam_score:
        return "coverage_hole"
    elif jam_score >= 2:
        return "probable_jamming"
    return "ambiguous"
```

---

## 7. Bug 3 — Coverage Baseline Silent Failure on First Call

### The problem

`get_coverage_baseline()` returns `{}` immediately on the first call while kicking off a
background task to build the real baseline. This means **every classification during the warm-up
window (typically 5–30 seconds) silently uses an empty baseline**:

```python
# rule_based.py — current implementation
async def get_coverage_baseline(lookback_days=3) -> dict:
    global _baseline_cache, _baseline_ts, _baseline_building

    if _baseline_cache is not None and (now - _baseline_ts) <= _BASELINE_TTL:
        return _baseline_cache      # ← cache hit, correct

    if not _baseline_building:
        _baseline_building = True
        asyncio.create_task(_build())   # ← fire and forget

    return _baseline_cache if _baseline_cache is not None else {}  # ← returns {} on first call!
```

What happens to events scored against `{}`:

```python
# rule_based.py — score_event()
cell_info = coverage_baseline.get((lat_cell, lon_cell))  # always None when baseline is {}
if cell_info is not None:
    in_hole = cell_info.get("is_coverage_hole", False)
# in_hole stays False for every event → coverage_hole category is never returned
# jamming_score misses the coverage-hole deduction → probable_jamming inflated
```

The original batch script has no such window — it **blocks at startup** until the baseline is
fully built before touching a single event.

---

### How it should be written

Block on the first build. Use a lock so concurrent requests don't each trigger their own build:

```python
# rule_based.py — fixed get_coverage_baseline()
import asyncio

_baseline_cache: dict | None = None
_baseline_ts: float = 0.0
_BASELINE_TTL = 3600.0
_baseline_lock = asyncio.Lock()


async def get_coverage_baseline(lookback_days: int = 30) -> dict:
    """Return coverage baseline, building it synchronously if not yet cached.

    Blocks on first call until the build is complete so no request ever
    receives an empty baseline. Uses a lock to prevent concurrent builds.
    """
    global _baseline_cache, _baseline_ts

    now = time.monotonic()
    if _baseline_cache is not None and (now - _baseline_ts) <= _BASELINE_TTL:
        return _baseline_cache

    async with _baseline_lock:
        # Re-check inside the lock — another coroutine may have built it while we waited
        now = time.monotonic()
        if _baseline_cache is not None and (now - _baseline_ts) <= _BASELINE_TTL:
            return _baseline_cache

        log.info("Building coverage baseline (blocking)...")
        _baseline_cache = await build_coverage_baseline_async(lookback_days)
        _baseline_ts = time.monotonic()
        log.info("Coverage baseline ready: %d cells", len(_baseline_cache))
        return _baseline_cache
```

If you want to keep a non-blocking warm-up for app startup, pre-warm it in the lifespan hook
**before** the app starts accepting requests:

```python
# app/main.py (FastAPI example)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm before accepting any traffic
    await get_coverage_baseline(lookback_days=30)
    yield
    # cleanup on shutdown if needed

app = FastAPI(lifespan=lifespan)
```

---

## 8. Bug 4 — Baseline Lookback Silently Reduced 30d → 3d

### The problem

The original `build_coverage_baseline()` defaults to 30 days. The agent changed this to 3 days
with no comment or explanation:

```python
# detect_rule_based.py — ORIGINAL
def build_coverage_baseline(conn, lookback_days: int = 30) -> dict:
    ...

# rule_based.py — NEW (agent version)
async def get_coverage_baseline(lookback_days=3) -> dict:       # ← 3 days!
async def build_coverage_baseline_async(lookback_days: int = 7) # ← 7 days!
```

A 3-day baseline has roughly **10× fewer data points** than a 30-day baseline. In low-traffic
regions (exactly the regions where coverage holes matter most), there may not be enough data
to even cross the `HAVING count(*) >= 10` threshold, so entire grid cells are absent from the
baseline and silently treated as non-holes.

### How it should be written

```python
# rule_based.py — restore the original default
_BASELINE_LOOKBACK_DAYS = 30  # match original detect_rule_based.py

async def get_coverage_baseline(lookback_days: int = _BASELINE_LOOKBACK_DAYS) -> dict:
    ...

async def build_coverage_baseline_async(lookback_days: int = _BASELINE_LOOKBACK_DAYS) -> dict:
    ...
```

---

## 9. Bug 5 — n_severe_alt_div Dropped from Kalman Events

### The problem

The original `run_kalman_batch()` includes `n_severe_alt_div` (count of altitude divergences
greater than 2000 ft) in every Kalman event. The new `kalman_event_from_result()` omits it:

```python
# detect_batch.py — ORIGINAL kalman event dict
all_events.append({
    "hex": hex_code,
    "classification": classification,
    "n_positions": len(positions),
    "n_flagged": n_flagged,
    "flag_pct": round(flag_pct, 2),
    "n_jumps": len(jumps),
    "n_alt_divergence": len(alt_div),
    "n_severe_alt_div": n_severe,          # ← present in original
    "physics_confidence": physics.get("confidence", 0.0),
    # ...
})


# signal_health_analyzer.py — NEW kalman_event_from_result()
return {
    "hex": hex_code,
    "category": result["classification"],
    "source": "kalman",
    "n_flagged": n_flagged,
    "flag_pct": round(flag_pct, 2),
    "n_jumps": len(result.get("jumps", [])),
    "n_alt_divergence": len(alt_div),
    # "n_severe_alt_div" is missing ← any consumer reading this gets KeyError
    "physics_confidence": result.get("physics", {}).get("confidence", 0.0),
    # ...
}
```

---

### How it should be written

```python
# signal_health_analyzer.py — kalman_event_from_result()
def kalman_event_from_result(hex_code: str, result: dict) -> dict:
    kr = result.get("kalman_results", [])
    n_flagged = sum(1 for r in kr if r.get("flagged"))
    n_kalman = len(kr)
    flag_pct = (n_flagged / n_kalman * 100) if n_kalman else 0.0
    alt_div = result.get("alt_divergence", [])
    n_severe = sum(1 for a in alt_div if a.get("severe"))  # ← count severe events

    return {
        "hex": hex_code,
        "category": result["classification"],
        "classification": result["classification"],
        "source": "kalman",
        "start_ts": result.get("start"),
        "end_ts": result.get("end"),
        "duration_s": None,
        "n_flagged": n_flagged,
        "flag_pct": round(flag_pct, 2),
        "n_jumps": len(result.get("jumps", [])),
        "n_alt_divergence": len(alt_div),
        "n_severe_alt_div": n_severe,       # ← restored
        "physics_confidence": result.get("physics", {}).get("confidence", 0.0),
        # ... rest of fields
    }
```

---

## 10. Bug 6 — Redundant fetch_time_range_async() Inside classify_flight_async()

### The problem

`classify_flight_async()` contains a fallback that re-calls `fetch_time_range_async()` if
`start_ts` or `end_ts` is `None`. But `_analyze_hex()` always passes both — it got them from
`fetch_time_range_async()` one line earlier. This is dead code that adds a latent extra query
if the function is ever called without timestamps:

```python
# kalman.py — classify_flight_async() has an internal fallback fetch
async def classify_flight_async(hex_code, start_ts=None, end_ts=None):
    # Auto-detect time range if not supplied
    if start_ts is None or end_ts is None:
        time_range = await fetch_time_range_async(hex_code)   # ← extra DB query
        if time_range is None:
            return {"error": f"No positions found for hex={hex_code}"}
        ...

# signal_health_analyzer.py — caller always provides both timestamps
async def _analyze_hex(self, hex_code, ...):
    time_range = await fetch_time_range_async(hex_code, ...)  # ← fetches here
    start_ts, end_ts = time_range

    _, _, kalman_result = await asyncio.gather(
        ...
        classify_flight_async(hex_code, start_ts, end_ts),    # ← always passes them
    )
    # So the fallback inside classify_flight_async never fires... unless called directly
```

The real risk: if `classify_flight_async()` is called directly from a test, a script, or another
cube without timestamps, it silently fires an extra query that the caller doesn't know about.

### How it should be written

Make `classify_flight_async()` a thin async wrapper that assumes timestamps are always provided,
and move the auto-detect logic to the caller only:

```python
# kalman.py — simplified, no hidden fallback query
async def classify_flight_async(
    hex_code: str,
    start_ts: datetime,
    end_ts: datetime,
) -> dict:
    """Run all Kalman detection steps. Timestamps are required — caller must
    call fetch_time_range_async() first if they don't have them."""
    positions = await fetch_positions_async(hex_code, start_ts, end_ts)

    if not positions:
        return {
            "hex": hex_code,
            "start": start_ts.isoformat(),
            "end": end_ts.isoformat(),
            "n_positions": 0,
            "classification": "normal",
            "kalman_results": [],
            "jumps": [],
            "alt_divergence": [],
            "physics": {},
            "summary": "No qualifying positions found.",
        }

    loop = asyncio.get_event_loop()
    kalman_results = await loop.run_in_executor(None, kalman_filter, positions)
    jumps          = await loop.run_in_executor(None, detect_position_jumps, positions)
    alt_div        = await loop.run_in_executor(None, detect_altitude_divergence, positions)
    physics        = await loop.run_in_executor(None, physics_cross_validation, positions)
    classification = classify_flight(kalman_results, jumps, alt_div, physics)

    return {
        "hex": hex_code,
        "start": start_ts.isoformat(),
        "end": end_ts.isoformat(),
        "n_positions": len(positions),
        "classification": classification,
        "kalman_results": kalman_results,
        "jumps": jumps,
        "alt_divergence": alt_div,
        "physics": physics,
    }
```

---

## 11. Summary Tables

### Performance issues — ranked by impact

| Rank | Issue | Impact | Severity |
|------|-------|--------|----------|
| 1 | 4 DB queries per hex instead of 3 total | ~133× more queries on 100 hexes | **Critical** |
| 2 | Synchronous CPU work blocks the async event loop | All coroutines stall during Kalman numpy loop | **High** |
| 3 | `_serialize_datetimes()` deep-copies 10k-row results per hex | O(N) overhead multiplied by hex count | **Medium** |
| 4 | `Semaphore(8)` × 3 concurrent connections = 24 peak DB connections | Pool saturation adds queuing delay | **Medium** |

### Bugs — ranked by severity

| Rank | Bug | Effect | Severity |
|------|-----|--------|----------|
| 1 | `score_event()` returns `dict` instead of `(int, int, int)` | `detect_batch.py` crashes — `TypeError` | **Critical** |
| 2 | `classify_event()` accepts `dict` instead of 3 ints | `detect_batch.py` crashes — `AttributeError` | **Critical** |
| 3 | Coverage baseline returns `{}` on first call | Silent wrong classifications for all first-run requests | **High** |
| 4 | Baseline lookback changed from 30 → 3 days | Unreliable coverage-hole detection in sparse regions | **Medium** |
| 5 | `n_severe_alt_div` field dropped from Kalman event output | `KeyError` or silent `None` for downstream consumers | **Medium** |
| 6 | Redundant `fetch_time_range_async()` inside `classify_flight_async()` | Latent extra query if called without timestamps | **Low** |
