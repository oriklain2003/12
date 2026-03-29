# Phase 23: Shared Utility Foundation + Duration Filter - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Shared infrastructure for all v4.0 behavioral cubes: historical query utilities (`get_callsign_history()`, `get_route_history()`), epoch helpers (`epoch_cutoff()`), datetime/lookback toggle parameter, partial datetime validation, and batch asyncio.gather() pattern. Also confirms FilterFlights duration filtering (ENHANCE-01) is already complete.

</domain>

<decisions>
## Implementation Decisions

### Datetime/Lookback Toggle
- **D-01:** Claude's discretion on toggle mechanism — choose between explicit `time_mode` param or auto-detect from filled inputs, whichever fits existing cube patterns best
- **D-02:** Default lookback period is **7 days** — consistent with AllFlights default (604800s)
- **D-03:** Claude's discretion on time format — choose between epoch seconds or ISO 8601 based on existing codebase patterns (AllFlights uses epoch seconds, DB stores bigint epochs)

### Historical Query Module
- **D-04:** `get_callsign_history()` and `get_route_history()` return **flight metadata rows** — same shape as AllFlights output (list of dicts with flight_id, callsign, first_seen_ts, last_seen_ts, lat/lon, etc.). Downstream cubes extract what they need.
- **D-05:** Module location: **`backend/app/cubes/utils/`** — new utils subpackage inside cubes directory
- **D-06:** Utility handles **deduplication internally** — takes a list of callsigns, deduplicates, runs one query per unique callsign via asyncio.gather(), returns results keyed by callsign

### Duration Filter
- **D-07:** ENHANCE-01 is **already satisfied** — FilterFlights has working min/max_duration_minutes params with Tier 1 metadata-based logic (filter_flights.py:134-155). No changes needed.

### Partial Datetime Validation
- **D-08:** Validation applies to **all cubes with datetime params** — retrofit AllFlights and AlisonFlights, not just new behavioral cubes. Consistent behavior across the board.
- **D-09:** Error surfaces as **cube output error field** — return an 'error' key in the output dict with a descriptive message. No exception raising. Frontend shows it in results panel.

### Claude's Discretion
- Toggle mechanism (D-01): Claude picks explicit param vs auto-detect
- Time format (D-03): Claude picks epoch vs ISO 8601 based on codebase patterns
- `epoch_cutoff()` helper API design
- Internal structure of the utils subpackage (single file vs multiple)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Cube Infrastructure
- `.planning/REQUIREMENTS.md` — INFRA-01, INFRA-02, INFRA-04, ENHANCE-01, ENHANCE-02, ENHANCE-03 definitions
- `.planning/ROADMAP.md` — Phase 23 success criteria (4 items)

### Existing Implementations
- `backend/app/cubes/filter_flights.py` — Duration filter already implemented (lines 69-79 params, 134-155 logic). ENHANCE-01 reference.
- `backend/app/cubes/all_flights.py` — Epoch-based time filtering pattern (time_range_seconds, start_time, end_time). Lines 58-80 for params, 194-205 for query logic.
- `backend/app/cubes/alison_flights.py` — Alternative time filtering pattern using datetime objects
- `backend/app/cubes/signal_health_analyzer.py` — lookback_hours pattern (line 176, 225-236)
- `backend/app/cubes/base.py` — BaseCube abstract class

### Behavioral Cube Specs
- `.planning/new-cubes/02-behavioral-analysis.md` — Behavioral analysis cube designs that will consume these shared utilities
- `.planning/STATE.md` — Research flags for Phase 25 (threshold calibration) and Phase 26 (check registry design)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseCube` (base.py): Abstract base with auto full_result output — all new cubes extend this
- `point_in_polygon()` (all_flights.py): Shared ray-casting utility already imported by filter_flights
- `engine` (database.py): Async SQLAlchemy engine used by all cubes for DB connections

### Established Patterns
- Time filtering: AllFlights uses `time_range_seconds` (relative) with `start_time`/`end_time` (absolute epoch strings) override
- DB queries: Raw SQL via `sqlalchemy.text()` with async connections (`async with engine.connect()`)
- Cube params: `ParamDefinition` with `widget_hint` for frontend rendering (e.g., `"datetime"`, `"relative_time"`)
- No shared utility modules exist yet — each cube has inline query logic

### Integration Points
- New `cubes/utils/` package will be imported by Phases 24-26 behavioral cubes
- AllFlights and AlisonFlights need partial datetime validation retrofit
- CubeRegistry auto-discovers cubes in `cubes/` directory — utils subpackage should not contain BaseCube subclasses

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 23-shared-utility-foundation-duration-filter*
*Context gathered: 2026-03-29*
