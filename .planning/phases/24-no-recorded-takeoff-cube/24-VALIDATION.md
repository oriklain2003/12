---
phase: 24
slug: no-recorded-takeoff-cube
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && uv run pytest tests/test_no_recorded_takeoff.py -x -q` |
| **Full suite command** | `cd backend && uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/test_no_recorded_takeoff.py -x -q`
- **After every plan wave:** Run `cd backend && uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 24-01-01 | 01 | 1 | INFRA-03 | unit | `uv run pytest tests/test_no_recorded_takeoff.py::test_full_result_input -x` | ❌ W0 | ⬜ pending |
| 24-01-02 | 01 | 1 | DETECT-01 | unit | `uv run pytest tests/test_no_recorded_takeoff.py::test_flags_high_altitude -x` | ❌ W0 | ⬜ pending |
| 24-01-03 | 01 | 1 | DETECT-05 | unit | `uv run pytest tests/test_no_recorded_takeoff.py::test_deviation_score -x` | ❌ W0 | ⬜ pending |
| 24-01-04 | 01 | 1 | DETECT-06 | unit | `uv run pytest tests/test_no_recorded_takeoff.py::test_diagnostic_states -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_no_recorded_takeoff.py` — stubs for INFRA-03, DETECT-01, DETECT-05, DETECT-06

*Existing test infrastructure (pytest, conftest) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cube appears in canvas sidebar | INFRA-03 | Requires running frontend | Place cube on canvas, verify it shows under ANALYSIS category |
| Full workflow chain works | DETECT-01 | E2E with real DB | Connect AllFlights → NoRecordedTakeoff → Run workflow |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
