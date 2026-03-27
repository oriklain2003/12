---
phase: 19
slug: cube-expert-validation-agent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` |
| **Quick run command** | `cd backend && uv run pytest tests/test_validation.py tests/test_cube_expert.py -x` |
| **Full suite command** | `cd backend && uv run pytest` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/test_validation.py tests/test_cube_expert.py -x`
- **After every plan wave:** Run `cd backend && uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | VALID-01 | unit | `uv run pytest tests/test_validation.py::TestValidation::test_missing_required_param -x` | W0 | pending |
| 19-01-02 | 01 | 1 | VALID-01 | unit | `uv run pytest tests/test_validation.py::TestValidation::test_dangling_source_handle -x` | W0 | pending |
| 19-01-03 | 01 | 1 | VALID-01 | unit | `uv run pytest tests/test_validation.py::TestValidation::test_dangling_target_handle -x` | W0 | pending |
| 19-01-04 | 01 | 1 | VALID-01 | unit | `uv run pytest tests/test_validation.py::TestValidation::test_cycle_detection -x` | W0 | pending |
| 19-01-05 | 01 | 1 | VALID-01 | unit | `uv run pytest tests/test_validation.py::TestValidation::test_type_mismatch_warning -x` | W0 | pending |
| 19-01-06 | 01 | 1 | VALID-01 | unit | `uv run pytest tests/test_validation.py::TestValidation::test_orphan_node_warning -x` | W0 | pending |
| 19-01-07 | 01 | 1 | VALID-01 | unit | `uv run pytest tests/test_validation.py::TestValidation::test_clean_graph_no_issues -x` | W0 | pending |
| 19-01-08 | 01 | 1 | VALID-01 | unit | `uv run pytest tests/test_validation.py::TestValidation::test_full_result_handle_valid -x` | W0 | pending |
| 19-01-09 | 01 | 1 | VALID-02 | unit | covered by test_missing_required_param (message assertions) | W0 | pending |
| 19-01-10 | 01 | 1 | VALID-03 | integration | `uv run pytest tests/test_validation.py::TestValidateEndpoint -x` | W0 | pending |
| 19-02-01 | 02 | 1 | CUBE-01 | unit | `uv run pytest tests/test_agent_infra.py::TestRegistry::test_catalog_tools_registered -x` | Exists | pending |
| 19-02-02 | 02 | 1 | CUBE-02 | unit | `uv run pytest tests/test_cube_expert.py::TestCatalogTools::test_get_cube_definition -x` | W0 | pending |
| 19-02-03 | 02 | 1 | CUBE-03 | unit | `uv run pytest tests/test_cube_expert.py::TestFindCubes -x` | W0 | pending |
| 19-02-04 | 02 | 1 | CUBE-03 | unit | `uv run pytest tests/test_cube_expert.py::TestCubeExpert::test_ask_mocked -x` | W0 | pending |
| 19-03-01 | 03 | 2 | VALID-03 | manual | Click Run on invalid workflow, verify issues panel opens | N/A | pending |
| 19-03-02 | 03 | 2 | VALID-03 | manual | Click Run on valid workflow, verify silent pass-through | N/A | pending |
| 19-03-03 | 03 | 2 | D-07 | manual | Click issue row, verify node highlights on canvas | N/A | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_validation.py` — stubs for VALID-01, VALID-02, VALID-03
- [ ] `backend/tests/test_cube_expert.py` — stubs for CUBE-02, CUBE-03

*(CUBE-01 is partially covered by existing `test_agent_infra.py::TestRegistry::test_catalog_tools_registered`. Extend or add to it.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Issues panel opens on errors, blocks execution | VALID-03, D-06 | Frontend UX requires browser interaction | 1. Create workflow with missing required param. 2. Click Run. 3. Verify issues panel appears, execution does not start. |
| Clean validation silent pass-through | D-08 | Frontend UX requires browser interaction | 1. Create valid workflow. 2. Click Run. 3. Verify execution starts immediately, no dialog/toast. |
| Clicking issue highlights node on canvas | D-07 | Frontend visual behavior | 1. Run validation on invalid workflow. 2. Click issue row. 3. Verify canvas scrolls to and highlights the offending node. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
