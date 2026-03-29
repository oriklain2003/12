# Phase 23: Shared Utility Foundation + Duration Filter - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 23-shared-utility-foundation-duration-filter
**Areas discussed:** Datetime/lookback toggle UX, Historical query module design, Duration filter status, Partial datetime validation

---

## Datetime/Lookback Toggle UX

| Option | Description | Selected |
|--------|-------------|----------|
| Single mode param | One STRING param like time_mode = 'range' \| 'lookback'. Explicit, easy to validate. | |
| Auto-detect from inputs | Infer mode from which params are filled. Simpler but ambiguous if both set. | |
| You decide | Claude picks the approach that fits best with existing patterns. | ✓ |

**User's choice:** You decide
**Notes:** Claude has discretion on toggle mechanism.

| Option | Description | Selected |
|--------|-------------|----------|
| 30 days | Good baseline depth vs query performance. Matches STATE.md research flag. | |
| 90 days | Deeper baseline, matches behavioral-analysis.md spec. Heavier queries. | |
| 7 days | Fast queries, consistent with AllFlights default (604800s). | ✓ |

**User's choice:** 7 days
**Notes:** User prefers consistency with existing AllFlights default.

| Option | Description | Selected |
|--------|-------------|----------|
| Epoch seconds | Consistent with AllFlights and DB schema (bigint epochs). No timezone ambiguity. | |
| ISO 8601 strings | Human-readable, requires parsing. New pattern in codebase. | |
| You decide | Claude picks based on existing patterns. | ✓ |

**User's choice:** You decide
**Notes:** Claude has discretion on time format.

---

## Historical Query Module Design

| Option | Description | Selected |
|--------|-------------|----------|
| Flight metadata rows | Return list of flight_metadata dicts, same shape as AllFlights output. | ✓ |
| Pre-aggregated stats | Return pre-computed stats (count, avg departure time, centroid). | |
| Both: raw + stats | Return dict with 'flights' and 'stats'. Most flexible but more complex. | |

**User's choice:** Flight metadata rows
**Notes:** Consistent pattern — downstream cubes extract what they need.

| Option | Description | Selected |
|--------|-------------|----------|
| backend/app/cubes/utils/ | New utils subpackage inside cubes/. Close to consumers. | ✓ |
| backend/app/engine/ | Alongside executor.py and registry.py. | |
| You decide | Claude picks based on conventions. | |

**User's choice:** backend/app/cubes/utils/
**Notes:** None.

| Option | Description | Selected |
|--------|-------------|----------|
| Utility deduplicates | Takes list, deduplicates internally, gathers, returns keyed by callsign. | ✓ |
| Cubes handle dedup | Utility is single-callsign async. Cubes responsible for dedup and gather. | |
| You decide | Claude picks. | |

**User's choice:** Utility deduplicates
**Notes:** None.

---

## Duration Filter Status

| Option | Description | Selected |
|--------|-------------|----------|
| Already done | Existing implementation at filter_flights.py:134-155 is correct. Mark ENHANCE-01 satisfied. | ✓ |
| Needs review/changes | May need improvements or integration with new datetime/lookback toggle. | |
| Reimplement with shared utils | Move duration logic into shared utility module for reuse. | |

**User's choice:** Already done
**Notes:** ENHANCE-01 is satisfied by existing code. No changes needed.

---

## Partial Datetime Validation

| Option | Description | Selected |
|--------|-------------|----------|
| All cubes with datetime | Retrofit AllFlights and AlisonFlights too. Consistent behavior. | ✓ |
| New cubes only | Only new behavioral cubes. Less risk of breaking existing workflows. | |
| You decide | Claude decides based on impact. | |

**User's choice:** All cubes with datetime
**Notes:** User wants consistent validation across the board.

| Option | Description | Selected |
|--------|-------------|----------|
| Cube output error field | Return 'error' key in output dict. Frontend shows in results panel. | ✓ |
| Raise Python exception | ValueError caught by executor, surfaced via SSE. Stops entire workflow. | |
| You decide | Claude picks. | |

**User's choice:** Cube output error field
**Notes:** Non-disruptive error surfacing preferred.

---

## Claude's Discretion

- Toggle mechanism (explicit param vs auto-detect)
- Time format (epoch seconds vs ISO 8601)
- epoch_cutoff() helper API design
- Utils subpackage internal structure

## Deferred Ideas

None.
