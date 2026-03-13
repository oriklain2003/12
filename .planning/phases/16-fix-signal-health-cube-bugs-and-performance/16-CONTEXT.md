# Phase 16: Fix Signal Health Cube Bugs and Performance - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the performance issues and bugs documented in `docs/signal_health_analysis.md` across the signal health detection system (`signal_health_analyzer.py`, `rule_based.py`, `kalman.py`). Do NOT touch `scripts/detect_batch.py` or any CLI scripts.

</domain>

<decisions>
## Implementation Decisions

### Batch query migration
- Replace per-hex query functions with batch-only equivalents (`WHERE hex = ANY(:hexes)`)
- No dual per-hex/batch — single batch implementation that works for 1 hex or many
- Batch functions return `dict[str, list[dict]]` keyed by hex, partitioned in Python after fetch
- `_analyze_hex()` loop replaced by bulk fetch → in-memory fan-out pattern (as described in analysis doc section 2)

### CLI script compatibility
- Do NOT modify `scripts/detect_batch.py`, `scripts/detect_rule_based.py`, or `scripts/detect_kalman.py`
- These scripts are separate from the cube system and will remain as-is
- If signature differences exist between scripts and `app.signal.*` modules, that's acceptable — scripts import their own local functions

### Coverage baseline startup behavior
- Load coverage baseline at app startup via FastAPI lifespan hook (background, non-blocking)
- Lookback window: 48 hours (not 7 or 30 days)
- No TTL refresh or periodic updates — load once at startup, stays in memory
- Log progress during build (start, cell count, duration)
- Requests before baseline is ready use whatever is available (empty dict if still building)

### Default lookback for detection queries
- Default `lookback_hours` should be 24 hours (1 day), not the current value
- Users want to see flights from the last day by default
- Still configurable via cube input parameter

### Code quality
- Code must be clean and readable — prioritize clarity over cleverness
- Avoid unnecessary abstractions, deep nesting, or overly compact patterns

### Claude's Discretion
- Event loop blocking fix: offload CPU-bound Kalman/physics to `run_in_executor` as needed
- `_serialize_datetimes()` removal/optimization — serialize only what the API returns
- `n_severe_alt_div` restoration in `kalman_event_from_result()`
- Redundant `fetch_time_range_async()` cleanup inside `classify_flight_async()`
- Exact batch query chunking strategy (e.g., 200-hex chunks for positions)
- Test updates to match new batch signatures

</decisions>

<specifics>
## Specific Ideas

- The analysis doc (`docs/signal_health_analysis.md`) has exact code examples for the batch migration — use these as reference
- Batch pattern: 3 total queries regardless of hex count (integrity, shutdowns, positions) instead of 4×N
- Coverage baseline logging should show something like "Building coverage baseline..." → "Coverage baseline ready: X cells in Y seconds"

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/detect_batch.py`: Contains the batch SQL patterns (`fetch_positions_batch`, `detect_integrity_batch`, `detect_shutdowns_batch`) that should be ported to async
- `backend/app/signal/rule_based.py`: `score_event()` and `classify_event()` signatures are correct (dict-based, Phase 14 decision) — no changes needed
- `backend/app/signal/kalman.py`: Pure computation functions (`kalman_filter`, `detect_position_jumps`, `detect_altitude_divergence`, `physics_cross_validation`) are correct — just need `run_in_executor` wrapping
- `backend/app/database.py`: Async SQLAlchemy engine already available

### Established Patterns
- All cube DB access uses `async with engine.connect()` + `text()` queries
- Cube inputs/outputs defined via `CubeDefinition` with typed `ParamDefinition`
- `BaseCube.execute()` returns dict of output param values

### Integration Points
- `backend/app/main.py`: FastAPI app — add lifespan hook for baseline pre-warm
- `backend/app/cubes/signal_health_analyzer.py`: Main orchestrator to restructure
- `backend/app/signal/rule_based.py`: Add batch async functions, modify baseline caching
- `backend/app/signal/kalman.py`: Add batch positions fetch, wrap CPU work in executor

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-fix-signal-health-cube-bugs-and-performance*
*Context gathered: 2026-03-13*
