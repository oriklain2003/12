# Phase 23: Shared Utility Foundation + Duration Filter - Research

**Researched:** 2026-03-29
**Domain:** Python async utility modules, SQLAlchemy async patterns, cube infrastructure
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Claude's discretion on toggle mechanism — choose between explicit `time_mode` param or auto-detect from filled inputs, whichever fits existing cube patterns best
- **D-02:** Default lookback period is **7 days** — consistent with AllFlights default (604800s)
- **D-03:** Claude's discretion on time format — choose between epoch seconds or ISO 8601 based on existing codebase patterns (AllFlights uses epoch seconds, DB stores bigint epochs)
- **D-04:** `get_callsign_history()` and `get_route_history()` return **flight metadata rows** — same shape as AllFlights output (list of dicts with flight_id, callsign, first_seen_ts, last_seen_ts, lat/lon, etc.). Downstream cubes extract what they need.
- **D-05:** Module location: **`backend/app/cubes/utils/`** — new utils subpackage inside cubes directory
- **D-06:** Utility handles **deduplication internally** — takes a list of callsigns, deduplicates, runs one query per unique callsign via asyncio.gather(), returns results keyed by callsign
- **D-07:** ENHANCE-01 is **already satisfied** — FilterFlights has working min/max_duration_minutes params with Tier 1 metadata-based logic (filter_flights.py:134-155). No changes needed.
- **D-08:** Validation applies to **all cubes with datetime params** — retrofit AllFlights and AlisonFlights, not just new behavioral cubes.
- **D-09:** Error surfaces as **cube output error field** — return an 'error' key in the output dict with a descriptive message. No exception raising. Frontend shows it in results panel.

### Claude's Discretion

- Toggle mechanism (D-01): Claude picks explicit param vs auto-detect
- Time format (D-03): Claude picks epoch vs ISO 8601 based on codebase patterns
- `epoch_cutoff()` helper API design
- Internal structure of the utils subpackage (single file vs multiple)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Shared `historical_query.py` module provides `get_callsign_history()` and `get_route_history()` async functions for historical flight lookups | D-04, D-05, D-06: module location, return shape, and deduplication/gather pattern all locked |
| INFRA-02 | Shared `epoch_cutoff()` helper computes bigint epoch cutoffs from lookback days, preventing epoch/datetime mixing bugs | AllFlights uses `int(time.time()) - int(seconds)` pattern; helper standardizes this |
| INFRA-04 | Historical lookback queries use batch `asyncio.gather()` pattern over unique callsigns, not per-flight loops | asyncio.gather is standard library; pattern confirmed in signal_health_analyzer.py |
| ENHANCE-01 | User can filter flights by min/max flight duration (minutes) on FilterFlights cube | ALREADY COMPLETE per D-07 — filter_flights.py:134-155 |
| ENHANCE-02 | Cubes with historical queries have a datetime/lookback toggle | AllFlights already has start_time/end_time + time_range_seconds pattern to follow |
| ENHANCE-03 | Partial datetime input (only start or only end) raises a descriptive validation error instead of silently falling back | AllFlights currently silently falls back — needs guard added |
</phase_requirements>

---

## Summary

Phase 23 builds shared infrastructure that all v4.0 behavioral cubes (Phases 24-26) will import. The scope is tightly bounded: create `backend/app/cubes/utils/` with two files (`historical_query.py` and `time_utils.py`), then retrofit the partial-datetime validation into AllFlights and AlisonFlights.

ENHANCE-01 (duration filtering) is already complete and confirmed in `filter_flights.py:134-155`. No work needed there beyond verifying the implementation and ensuring the test suite covers it.

The codebase has a fully established async SQLAlchemy pattern: raw SQL via `sqlalchemy.text()` with `async with engine.connect() as conn` from `app.database`. All new utilities follow this exact pattern. The `asyncio.gather()` pattern is already used in `signal_health_analyzer.py` (via `fetch_positions_batch_async` and `detect_integrity_events_batch_async`), so the batch query approach is proven in this codebase.

**Primary recommendation:** Create `cubes/utils/__init__.py`, `cubes/utils/historical_query.py`, and `cubes/utils/time_utils.py`. Retrofit AllFlights and AlisonFlights with a shared `validate_datetime_pair()` guard that returns an error dict when only one of start_time/end_time is provided. Use explicit `time_mode` parameter for toggle (cleaner than auto-detect given AllFlights' existing precedent of defaulting to relative when both are absent).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncio | stdlib | Concurrent query execution via `gather()` | Already used throughout codebase |
| sqlalchemy[asyncio] | 2.0.48 | Async DB connections with `engine.connect()` | Established project pattern |
| asyncpg | 0.30.0+ | PostgreSQL async driver under SQLAlchemy | Already wired in database.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| time (stdlib) | stdlib | `time.time()` for epoch math | epoch_cutoff() implementation |
| typing | stdlib | `Any`, type hints | All utility signatures |

**No new dependencies needed.** This phase is pure Python using existing stack.

---

## Architecture Patterns

### Recommended Project Structure
```
backend/app/cubes/utils/
├── __init__.py              # Empty or re-exports for convenience
├── historical_query.py      # get_callsign_history(), get_route_history()
└── time_utils.py            # epoch_cutoff(), validate_datetime_pair()
```

CubeRegistry auto-discovers `BaseCube` subclasses in `cubes/`. The `utils/` subpackage contains no `BaseCube` subclasses, so it is safe from accidental auto-discovery. The `__init__.py` must exist to make it a proper Python package.

### Pattern 1: asyncio.gather() for Batch Callsign Queries

**What:** Deduplicate a callsign list, fire one async DB query per unique callsign concurrently using `asyncio.gather()`, return a dict keyed by callsign.

**When to use:** Any historical query where the input is a list of callsigns. Prevents N sequential round-trips.

```python
# Source: established pattern — see app/signal/rule_based.py (detect_integrity_events_batch_async)
import asyncio
from sqlalchemy import text
from app.database import engine

async def get_callsign_history(
    callsigns: list[str],
    lookback_seconds: int = 604800,
) -> dict[str, list[dict]]:
    """Return flight metadata rows keyed by callsign. Deduplicates input."""
    unique = list(set(callsigns))
    if not unique:
        return {}

    async def _fetch_one(callsign: str) -> tuple[str, list[dict]]:
        cutoff = epoch_cutoff(lookback_seconds)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT flight_id, callsign, first_seen_ts, last_seen_ts,
                           start_lat, start_lon, end_lat, end_lon,
                           origin_airport, destination_airport
                    FROM research.flight_metadata
                    WHERE callsign = :callsign
                      AND last_seen_ts >= :cutoff
                    ORDER BY first_seen_ts
                """),
                {"callsign": callsign, "cutoff": cutoff},
            )
            cols = list(result.keys())
            rows = [dict(zip(cols, row)) for row in result.fetchall()]
        return callsign, rows

    results = await asyncio.gather(*[_fetch_one(cs) for cs in unique])
    return dict(results)
```

### Pattern 2: epoch_cutoff() Helper

**What:** Centralizes the `int(time.time()) - lookback_seconds` computation to prevent epoch/datetime mixing in behavioral cubes.

**When to use:** Any cube computing a rolling lookback window cutoff. Replaces all inline `int(time.time()) - int(time_range_seconds or 604800)` calls.

```python
# Source: all_flights.py:203 shows the pattern this helper standardizes
import time

def epoch_cutoff(lookback_seconds: int) -> int:
    """Return the epoch second cutoff for a rolling lookback window.

    Args:
        lookback_seconds: How far back to look (e.g., 604800 = 7 days).

    Returns:
        Integer epoch seconds for the cutoff timestamp.
    """
    return int(time.time()) - int(lookback_seconds)
```

### Pattern 3: Partial Datetime Validation

**What:** Guard that detects when only one of start_time/end_time is provided and returns an error dict. Applied consistently to AllFlights and AlisonFlights.

**When to use:** Any cube accepting start_time + end_time pair. Call at the top of `execute()` before any DB work.

```python
# Returns error dict on violation; None on valid state.
def validate_datetime_pair(
    start_time: str | None,
    end_time: str | None,
) -> dict | None:
    """Validate that datetime params are provided as a complete pair.

    Returns an error dict if only one of start/end is provided.
    Returns None if the combination is valid (both present, neither present).
    """
    has_start = start_time is not None
    has_end = end_time is not None
    if has_start and not has_end:
        return {"error": "Partial datetime input: start_time provided but end_time is missing. Provide both or neither."}
    if has_end and not has_start:
        return {"error": "Partial datetime input: end_time provided but start_time is missing. Provide both or neither."}
    return None
```

Usage in AllFlights.execute():
```python
# At top of execute(), before SQL build
err = validate_datetime_pair(start_time, end_time)
if err:
    return {**err, "flights": [], "flight_ids": []}
```

Usage in AlisonFlights.execute():
```python
err = validate_datetime_pair(start_time, end_time)
if err:
    return {**err, "flights": [], "hex_list": []}
```

### Pattern 4: Datetime/Lookback Toggle — Recommendation

**What:** Explicit `time_mode` parameter ("lookback" or "datetime") on cubes that query historical data.

**Recommendation: Use explicit `time_mode` param.** Rationale from codebase analysis:
- AllFlights already has `time_range_seconds`, `start_time`, and `end_time` as separate params — the auto-detect approach is already established there.
- For new behavioral cubes (Phases 24-26), using an explicit `time_mode` param is cleaner: the frontend can render a toggle UI via `widget_hint="toggle"` and the cube logic branches clearly.
- Auto-detect is fragile when a user might set both values; explicit mode eliminates ambiguity.

Recommended param definition:
```python
ParamDefinition(
    name="time_mode",
    type=ParamType.STRING,
    description="Time selection mode: 'lookback' (rolling window) or 'datetime' (fixed range).",
    required=False,
    default="lookback",
    widget_hint="toggle",
    options=["lookback", "datetime"],
),
ParamDefinition(
    name="lookback_days",
    type=ParamType.NUMBER,
    description="Days of history to query (used when time_mode='lookback'). Default: 7.",
    required=False,
    default=7,
),
ParamDefinition(
    name="start_time",
    type=ParamType.STRING,
    description="Absolute start time as epoch seconds string (used when time_mode='datetime').",
    required=False,
    widget_hint="datetime",
),
ParamDefinition(
    name="end_time",
    type=ParamType.STRING,
    description="Absolute end time as epoch seconds string (used when time_mode='datetime').",
    required=False,
    widget_hint="datetime",
),
```

**Time format decision (D-03): Use epoch seconds.** Rationale:
- `research.flight_metadata` stores `first_seen_ts` and `last_seen_ts` as bigint epoch seconds.
- AllFlights converts `start_time`/`end_time` strings to `int(float(start_time))` — no datetime objects.
- AlisonFlights converts to `datetime.fromtimestamp()` because `public.aircraft.last_seen` is a TIMESTAMP column, not bigint. For the new utils module targeting `research.flight_metadata`, epoch seconds is the native type.
- `epoch_cutoff()` returns int epoch seconds — consistent.

### Anti-Patterns to Avoid

- **Importing utils from cubes in `__init__.py` of cubes package:** The CubeRegistry scans `cubes/` for BaseCube subclasses. Do not import anything in `cubes/__init__.py` that could trigger auto-discovery side effects.
- **datetime objects for research schema queries:** `research.flight_metadata` timestamps are bigint epochs. Mixing `datetime` objects causes type coercion bugs. Always use epoch ints for this schema.
- **Per-callsign sequential queries in a loop:** `for callsign in callsigns: result = await db.execute(...)` creates N serial round-trips. Always use `asyncio.gather()`.
- **Raising exceptions for validation errors:** D-09 specifies returning `{"error": "..."}` in the output dict. Cube execute() methods do not raise — they return.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Concurrent DB queries | Manual task queuing | `asyncio.gather()` | Stdlib, proven in this codebase (signal module) |
| Epoch math | Custom datetime parsing | `int(time.time()) - lookback` | Established pattern in AllFlights; epoch_cutoff() standardizes it |
| Python package creation | Custom import mechanism | Standard `__init__.py` | Python packaging; CubeRegistry relies on standard import |

---

## Common Pitfalls

### Pitfall 1: CubeRegistry Accidentally Discovers Utils

**What goes wrong:** If a class in `cubes/utils/` accidentally inherits from `BaseCube` (or a future change adds one), CubeRegistry will try to register it as a cube and fail.
**Why it happens:** CubeRegistry does recursive discovery in `cubes/` directory.
**How to avoid:** `utils/` must never contain `BaseCube` subclasses. No cube logic in utils.
**Warning signs:** `GET /api/cubes/catalog` returns an error or extra entries.

### Pitfall 2: asyncio.gather() Concurrency Limit

**What goes wrong:** If a behavioral cube receives 500+ unique callsigns, `asyncio.gather()` spawns 500+ concurrent DB connections simultaneously. With `pool_size=10, max_overflow=10` (database.py), this queues connections and can time out.
**Why it happens:** `asyncio.gather()` is unbounded by default.
**How to avoid:** For Phase 23 utilities, this is acceptable — behavioral cubes downstream will typically work with O(10s) to O(100s) callsigns from filtered flight sets. Document the limitation. If needed in Phase 24+, use `asyncio.Semaphore` to cap concurrency.
**Warning signs:** `TimeoutError` or `QueueFull` errors under large inputs.

### Pitfall 3: Partial Datetime Validation Misses AlisonFlights Fallback Logic

**What goes wrong:** AlisonFlights (lines 126-135) has slightly different partial handling than AllFlights — it uses `datetime.fromtimestamp()` for its time columns. The validate_datetime_pair guard must be called *before* the time filter branching logic, not after.
**Why it happens:** Both cubes have `if start_time is not None and end_time is not None:` as their absolute branch — partial input silently falls through to relative mode.
**How to avoid:** Insert `validate_datetime_pair()` call at the very top of execute(), return immediately on non-None result.
**Warning signs:** `start_time` provided without `end_time` silently uses 7-day relative window instead of erroring.

### Pitfall 4: get_route_history() Route Key Format

**What goes wrong:** `get_route_history()` needs a keying strategy — is it `(origin, destination)` tuple or `"ORIG-DEST"` string? Dict keys must be consistent or downstream cubes get misses.
**Why it happens:** Phase 23 defines the function contract; Phases 24-26 consume it.
**How to avoid:** Key by `(origin, destination)` tuple in the returned dict for type safety. Document the contract in the docstring.

### Pitfall 5: ENHANCE-01 Verification Gap

**What goes wrong:** D-07 states ENHANCE-01 is already satisfied, but the test for `test_filter_flights.py` must explicitly cover min/max_duration_minutes. If the test doesn't exercise the duration logic, the phase verification is incomplete.
**Why it happens:** The implementation exists but test coverage confirmation was not in the context.
**How to avoid:** Read `test_filter_flights.py` to confirm duration tests exist before declaring ENHANCE-01 done. If missing, add them in Wave 0.

---

## Code Examples

### Creating the utils Package (Wave 0 task)

```bash
# These files must be created
touch backend/app/cubes/utils/__init__.py
touch backend/app/cubes/utils/historical_query.py
touch backend/app/cubes/utils/time_utils.py
```

### route_history key convention

```python
# Source: D-04 + analysis of flight_metadata schema
async def get_route_history(
    routes: list[tuple[str, str]],   # [(origin, destination), ...]
    lookback_seconds: int = 604800,
) -> dict[tuple[str, str], list[dict]]:
    """Return flight metadata rows keyed by (origin, destination) pair."""
    unique_routes = list(set(routes))
    ...
    return {(origin, destination): rows, ...}
```

### Importing utils from a behavioral cube

```python
# Source: D-05 module location
from app.cubes.utils.historical_query import get_callsign_history, get_route_history
from app.cubes.utils.time_utils import epoch_cutoff, validate_datetime_pair
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Inline `int(time.time()) - int(time_range_seconds)` | `epoch_cutoff()` helper | Phase 23 | Prevents epoch/datetime mixing bugs in behavioral cubes |
| No shared query utilities | `cubes/utils/` subpackage | Phase 23 | Phases 24-26 cubes import from here instead of duplicating SQL |
| Silent fallback on partial datetime | Explicit error output | Phase 23 | Consistent user-visible error for misconfigured time params |

---

## Environment Availability

Step 2.6: SKIPPED — phase is pure Python code changes, no new external dependencies. All required packages (asyncio stdlib, sqlalchemy 2.0.48, asyncpg) are confirmed installed.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]` asyncio_mode = "auto") |
| Quick run command | `cd backend && uv run pytest tests/test_filter_flights.py -x` |
| Full suite command | `cd backend && uv run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | `get_callsign_history()` returns flight rows keyed by callsign | unit | `uv run pytest tests/test_historical_query.py -x` | ❌ Wave 0 |
| INFRA-01 | `get_route_history()` returns flight rows keyed by (origin, dest) | unit | `uv run pytest tests/test_historical_query.py -x` | ❌ Wave 0 |
| INFRA-02 | `epoch_cutoff(604800)` returns `int(time.time()) - 604800` | unit | `uv run pytest tests/test_time_utils.py -x` | ❌ Wave 0 |
| INFRA-04 | `get_callsign_history()` uses `asyncio.gather()` not sequential loop | unit (mock) | `uv run pytest tests/test_historical_query.py::test_batch_gather -x` | ❌ Wave 0 |
| ENHANCE-01 | FilterFlights duration filter min/max (already implemented) | unit | `uv run pytest tests/test_filter_flights.py -x` | ✅ verify coverage |
| ENHANCE-02 | time_mode="lookback" uses epoch_cutoff; "datetime" uses explicit range | unit | `uv run pytest tests/test_time_utils.py -x` | ❌ Wave 0 |
| ENHANCE-03 | AllFlights returns error dict when only start_time provided | unit | `uv run pytest tests/test_all_flights.py::test_partial_datetime_error -x` | ❌ Wave 0 |
| ENHANCE-03 | AlisonFlights returns error dict when only end_time provided | unit | `uv run pytest tests/test_alison_flights.py::test_partial_datetime_error -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && uv run pytest tests/test_historical_query.py tests/test_time_utils.py -x`
- **Per wave merge:** `cd backend && uv run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_historical_query.py` — covers INFRA-01, INFRA-04
- [ ] `tests/test_time_utils.py` — covers INFRA-02, ENHANCE-02
- [ ] Add `test_partial_datetime_error` cases to `tests/test_all_flights.py` — covers ENHANCE-03
- [ ] Add `test_partial_datetime_error` cases to `tests/test_alison_flights.py` — covers ENHANCE-03
- [ ] Verify `tests/test_filter_flights.py` covers min/max_duration_minutes — confirm ENHANCE-01

---

## Open Questions

1. **Concurrency cap for asyncio.gather()**
   - What we know: pool_size=10, max_overflow=10 in database.py
   - What's unclear: What is the realistic max callsign count behavioral cubes will receive? Dozens or hundreds?
   - Recommendation: Proceed without a cap for Phase 23; add `asyncio.Semaphore` in Phase 24 if load testing reveals pool exhaustion.

2. **ENHANCE-01 test coverage confirmation**
   - What we know: Duration filter logic exists at filter_flights.py:134-155
   - What's unclear: Does `test_filter_flights.py` actually test min/max_duration_minutes? (Not read fully — only first 60 lines read)
   - Recommendation: Wave 0 task should read `test_filter_flights.py` fully and add duration tests if missing.

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `backend/app/cubes/all_flights.py` — time filter pattern, epoch math (lines 192-205)
- Direct code inspection: `backend/app/cubes/alison_flights.py` — alternative time filter, datetime objects (lines 126-135)
- Direct code inspection: `backend/app/cubes/filter_flights.py` — ENHANCE-01 duration logic confirmed (lines 134-155)
- Direct code inspection: `backend/app/cubes/base.py` — BaseCube abstract class, full_result auto-output
- Direct code inspection: `backend/app/cubes/signal_health_analyzer.py` — asyncio.gather pattern confirmed (imports from signal module)
- Direct code inspection: `backend/app/database.py` — engine config (pool_size=10, max_overflow=10)
- Direct code inspection: `backend/app/schemas/cube.py` — ParamDefinition, ParamType, widget_hint field
- Direct code inspection: `backend/pyproject.toml` — SQLAlchemy 2.0.48, asyncpg 0.30+, pytest-asyncio confirmed
- Direct code inspection: `backend/tests/conftest.py` — mock DB pattern, AsyncMock
- Direct code inspection: `.planning/phases/23-shared-utility-foundation-duration-filter/23-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)
- `.planning/new-cubes/02-behavioral-analysis.md` — downstream consumer shapes (confirms callsign/route as query keys)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified directly from pyproject.toml and existing cube source files
- Architecture: HIGH — based on established patterns in all_flights.py, signal_health_analyzer.py, and locked decisions in CONTEXT.md
- Pitfalls: HIGH — derived from direct reading of database.py pool config and cube execution patterns

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (30 days — stable Python stdlib + locked codebase patterns)
