---
phase: 15-cube-unit-tests-and-integration-tests-for-current-and-future-cubes
plan: 06
subsystem: signal-detection-tests
tags: [testing, signal, kalman, rule-based, unit-tests]
dependency_graph:
  requires: []
  provides: [signal-module-test-coverage]
  affects: [backend/app/signal/rule_based.py, backend/app/signal/kalman.py]
tech_stack:
  added: []
  patterns: [pytest-asyncio, unittest.mock.patch, synthetic-trajectory-data]
key_files:
  created:
    - backend/tests/test_signal_rule_based.py
    - backend/tests/test_signal_kalman.py
  modified: []
decisions: []
metrics:
  duration: ~3min
  completed: "2026-03-09"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 40
---

# Phase 15 Plan 06: Signal Detection Module Tests Summary

40 unit tests across 2 files covering both signal detection modules (rule-based scoring/classification and Kalman filter anomaly detection) with synthetic trajectory data and mocked async DB access.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rule-based signal module tests | 8f0aa6d | backend/tests/test_signal_rule_based.py |
| 2 | Kalman signal module tests | 26cbbc1 | backend/tests/test_signal_kalman.py |

## What Was Built

### test_signal_rule_based.py (444 lines, 16 tests)

**Pure function tests (12 tests):**
- `score_event`: jamming scenario (NACp=0, NIC=0, gps_ok_before, good RSSI, low seen_pos -> jam>=6), spoofing scenario (alt divergence >2000ft + NIC<7 -> spf>=4), transponder_off passthrough, normal healthy indicators (low scores), coverage hole detection
- `classify_event`: gps_jamming (jam>=6), gps_jamming moderate (jam>=4 > cov), gps_spoofing (spf>=4), coverage_hole (cov>=2 > jam), probable_jamming (jam>=2), ambiguous (low scores), transponder_off (gap_detection source)

**Async tests (4 tests):**
- `detect_integrity_events_async`: mocked DB returning integrity degradation rows, verified event structure fields
- `detect_integrity_events_async` (empty): empty DB result returns empty list
- `detect_transponder_shutdowns_async`: mocked DB with transponder gap rows, verified gap_detection category and zero scores
- `build_coverage_baseline_async`: mocked DB coverage stats, verified baseline dict structure and is_coverage_hole logic

### test_signal_kalman.py (466 lines, 24 tests)

**Pure function tests (21 tests):**
- `haversine_km`: known TLV-Jerusalem distance (~50km), same point (0km), antipodal (~20000km)
- `latlon_to_enu`: same point (0,0), east offset (~111km at equator), north offset (~111km)
- `kalman_filter`: smooth trajectory (no flags), jump trajectory (sudden 100km shift -> flagged), too few positions (empty)
- `detect_position_jumps`: jump >55.56km within 30s (detected), smooth trajectory (none), large dt >30s (ignored)
- `detect_altitude_divergence`: baro vs geom >1000ft (detected, severe flag at >2000ft), consistent altitudes (none), missing data (skipped)
- `physics_cross_validation`: normal consistent sensors (low confidence), anomalous sensors with large GS-TAS/alt/heading/vrate divergences (high confidence)
- `classify_flight`: normal (no evidence), gps_spoofing (multiple corroborating signals), anomalous (single strong indicator), empty kalman (normal)

**Async tests (3 tests):**
- `classify_flight_async`: mocked DB with smooth trajectory, verified classification=normal and result structure
- `classify_flight_async` (empty): no positions, verified n_positions=0 and classification=normal
- `fetch_positions_async`: mocked DB, verified position dict keys and values

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

```
40 passed in 0.21s
```

All 40 tests pass. Both test files exceed the 100-line minimum (444 and 466 lines respectively).

## Self-Check: PASSED

- FOUND: backend/tests/test_signal_rule_based.py (444 lines)
- FOUND: backend/tests/test_signal_kalman.py (466 lines)
- FOUND: commit 8f0aa6d (task 1)
- FOUND: commit 26cbbc1 (task 2)
