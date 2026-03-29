---
phase: 23
slug: shared-utility-foundation-duration-filter
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `backend/pyproject.toml` (pytest section) |
| **Quick run command** | `cd backend && uv run pytest tests/ -x -q --timeout=30` |
| **Full suite command** | `cd backend && uv run pytest tests/ -v --timeout=60` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/ -x -q --timeout=30`
- **After every plan wave:** Run `cd backend && uv run pytest tests/ -v --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 23-01-01 | 01 | 1 | INFRA-01 | unit | `uv run pytest tests/test_historical_query.py -v` | ❌ W0 | ⬜ pending |
| 23-01-02 | 01 | 1 | INFRA-02 | unit | `uv run pytest tests/test_epoch_helpers.py -v` | ❌ W0 | ⬜ pending |
| 23-01-03 | 01 | 1 | INFRA-04 | unit | `uv run pytest tests/test_datetime_toggle.py -v` | ❌ W0 | ⬜ pending |
| 23-02-01 | 02 | 2 | ENHANCE-02 | unit | `uv run pytest tests/test_partial_datetime.py -v` | ❌ W0 | ⬜ pending |
| 23-02-02 | 02 | 2 | ENHANCE-03 | unit | `uv run pytest tests/test_datetime_toggle_cubes.py -v` | ❌ W0 | ⬜ pending |
| 23-03-01 | 03 | 2 | ENHANCE-01 | unit | `uv run pytest tests/test_filter_flights.py -v -k duration` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_historical_query.py` — stubs for INFRA-01 (get_callsign_history, get_route_history, batch gather)
- [ ] `tests/test_epoch_helpers.py` — stubs for INFRA-02 (epoch_cutoff)
- [ ] `tests/test_datetime_toggle.py` — stubs for INFRA-04 (time_mode toggle)
- [ ] `tests/test_partial_datetime.py` — stubs for ENHANCE-02 (partial datetime validation)
- [ ] `tests/test_datetime_toggle_cubes.py` — stubs for ENHANCE-03 (toggle param on historical cubes)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Duration filter visible in UI | ENHANCE-01 | Frontend rendering | Place FilterFlights cube, verify min/max duration params appear |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
