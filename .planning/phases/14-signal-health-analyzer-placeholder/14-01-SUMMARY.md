---
phase: 14-signal-health-analyzer-placeholder
plan: 01
subsystem: analysis
tags: [gps-anomaly, signal-health, rule-based, async, sqlalchemy, numpy, scipy]

# Dependency graph
requires:
  - phase: 12-area-spatial-filter
    provides: async SQLAlchemy engine pattern used for DB-touching async functions
provides:
  - Async rule-based GPS anomaly detection module (app.signal.rule_based)
  - detect_integrity_events_async: version-aware NACp/NIC degradation CTE query
  - detect_transponder_shutdowns_async: mid-flight gap detection >5 min
  - score_event: 16-point jam/cov/spf evidence scoring
  - classify_event: category classification from scored event dict
  - get_coverage_baseline: cached 0.5-degree grid baseline (1-hour TTL)
  - numpy + scipy dependencies added to pyproject.toml
affects: [14-02, 14-03, signal_health_analyzer_cube]

# Tech tracking
tech-stack:
  added: [numpy>=2.4.2, scipy>=1.17.1]
  patterns:
    - async SQLAlchemy engine.connect() for raw SQL queries in standalone modules
    - Module-level TTL cache pattern for expensive baseline queries
    - ISO 8601 serialization of datetime objects before returning event dicts

key-files:
  created:
    - backend/app/signal/__init__.py
    - backend/app/signal/rule_based.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock

key-decisions:
  - "score_event returns augmented event dict (not tuple) — plan API spec requires scored dict for classify_event to consume"
  - "classify_event accepts scored event dict (not raw score ints) — enables transponder_off passthrough without re-scoring"
  - "7-day default lookback for coverage baseline (vs 30-day in CLI script) — per RESEARCH.md recommendation for interactive cube latency"
  - "1-hour TTL module-level cache for coverage baseline — avoids repeated heavy queries on every cube execution"

patterns-established:
  - "Async signal module pattern: each DB-touching function acquires its own async with engine.connect() connection"
  - "Event dict ISO serialization: all datetime fields converted to .isoformat() strings before return to enable JSON serialization downstream"

requirements-completed: [SHA-RULE, SHA-DEPS]

# Metrics
duration: 6min
completed: 2026-03-09
---

# Phase 14 Plan 01: Signal Health Analyzer — Rule-Based Detection Module Summary

**Async GPS anomaly detection ported from psycopg CLI to SQLAlchemy async: integrity events, transponder shutdowns, 16-point scoring, coverage baseline with TTL cache**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-08T21:59:29Z
- **Completed:** 2026-03-09T22:05:19Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Ported 850-line psycopg CLI script to async SQLAlchemy module with all detection logic preserved verbatim
- Added numpy and scipy dependencies to pyproject.toml via `uv add`
- Created `app.signal` package with full public API for Plan 03 orchestration
- Coverage baseline uses 7-day default with 1-hour TTL module-level cache

## Task Commits

1. **Task 1: Add numpy/scipy deps + create signal package** - `b3535ce` (chore)
2. **Task 2: Port rule-based detection to async module** - `0306501` (feat)

## Files Created/Modified
- `backend/app/signal/__init__.py` - Empty package marker
- `backend/app/signal/rule_based.py` - 526-line async detection module with all 5 public API functions
- `backend/pyproject.toml` - Added numpy>=2.4.2 and scipy>=1.17.1 dependencies
- `backend/uv.lock` - Updated with resolved numpy and scipy packages

## Decisions Made
- `score_event` returns an augmented copy of the event dict (not a raw tuple) — the plan's public API has `classify_event(scored_event) -> str` which requires the scored dict to determine source type and scores
- `classify_event` accepts the scored event dict: it short-circuits to `transponder_off` for `gap_detection` source events without re-scoring, matching the original script's behavior where shutdowns bypass the scoring/classification pipeline
- 7-day lookback default for `get_coverage_baseline` (vs 30-day in CLI) per RESEARCH.md recommendation — 30-day queries are too slow for interactive cube execution
- 1-hour TTL module-level cache keeps the baseline fresh without rebuilding on every workflow run

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None — numpy was already installed as an indirect dependency so uv add resolved instantly for numpy; scipy downloaded ~19MB.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `app.signal.rule_based` module is ready to be imported by `SignalHealthAnalyzerCube` in Plan 03
- Public API is fully importable: `from app.signal.rule_based import get_coverage_baseline, detect_integrity_events_async, detect_transponder_shutdowns_async, score_event, classify_event`
- numpy and scipy available for Kalman filter implementation in future plans

## Self-Check: PASSED

All files present and all commits verified on disk.

---
*Phase: 14-signal-health-analyzer-placeholder*
*Completed: 2026-03-09*
