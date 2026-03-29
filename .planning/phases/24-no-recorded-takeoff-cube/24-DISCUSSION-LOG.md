# Phase 24: No Recorded Takeoff Cube - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 24-no-recorded-takeoff-cube
**Areas discussed:** Deviation score formula, Track data source, Output schema shape, Historical context usage

---

## Deviation Score Formula

| Option | Description | Selected |
|--------|-------------|----------|
| Proportional to altitude | Score scales with how far above threshold the first point is (300ft=0.3, 10000ft=0.9, 35000ft=1.0) | |
| Binary 0 or 1 | Score is 1.0 if flagged, 0.0 if not | ✓ |
| You decide | Claude picks best formula | |

**User's choice:** Binary 0 or 1
**Notes:** User confirmed all input flights appear in output (clean = 0.0, flagged = 1.0). Binary scoring is the standard for ALL v4.0 behavioral cubes (Phases 25-26 follow same pattern).

---

## Track Data Source

| Option | Description | Selected |
|--------|-------------|----------|
| research.normal_tracks | Cleaned track points with alt column, ordered by timestamp | ✓ |
| public.positions | Raw ADS-B data with alt_baro, higher volume, noisier | |
| You decide | Claude picks based on data quality | |

**User's choice:** research.normal_tracks
**Notes:** Cube accepts both full_result and direct flight_ids input (like DarkFlightDetector). Single batch query with IN clause — one DB round-trip.

---

## Output Schema Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Full upstream passthrough | Each row includes all upstream flight metadata plus behavioral fields | ✓ |
| Minimal — behavioral fields only | Only flight_id + flag + deviation_score + diagnostic | |
| You decide | Claude determines | |

**User's choice:** Full upstream passthrough
**Notes:** Boolean flag uses cube-specific name (`no_recorded_takeoff`, not generic `is_anomaly`). Single `results` output param (one list of dicts). No split outputs.

---

## Historical Context Usage

| Option | Description | Selected |
|--------|-------------|----------|
| No track data for flight | 'insufficient history' = flight_id has zero normal_tracks rows | ✓ |
| Too few track points | 'insufficient history' = flight has < N track points | |

**User's choice:** No track data = insufficient history

| Option | Description | Selected |
|--------|-------------|----------|
| No historical_query.py needed | Purely track-point lookup | |
| Use for context enrichment | Call get_callsign_history() to add typical first altitude | ✓ |

**User's choice:** Use historical_query.py for context enrichment — compute typical_first_alt_ft (median/mean first-track-point altitude from historical flights). Enrichment applies to flagged flights only.

---

## Claude's Discretion

- How to compute typical_first_alt_ft (mean vs median)
- Internal query structure for first track point extraction
- Handling callsigns with no historical data
- Category assignment (ANALYSIS)

## Deferred Ideas

None — discussion stayed within phase scope
