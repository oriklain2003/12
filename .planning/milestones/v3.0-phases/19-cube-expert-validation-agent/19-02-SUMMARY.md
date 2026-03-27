---
phase: 19-cube-expert-validation-agent
plan: "02"
subsystem: backend/agents
tags: [cube-expert, sub-agent, gemini, tool-registry, tdd]
dependency_graph:
  requires:
    - 18-04 (agent infrastructure — client, skills_loader, registry, dispatcher, context)
    - 19-01 (validation schemas — CubeDefinition types referenced in tests)
  provides:
    - find_cubes_for_task keyword-search tool (catalog_tools.py)
    - CubeExpert sub-agent class (cube_expert.py)
  affects:
    - 19-03 (validation agent — will use CubeExpert.ask())
    - 20-xx (canvas agent — will instantiate CubeExpert for cube selection)
tech_stack:
  added: []
  patterns:
    - TDD (RED→GREEN for both tasks)
    - Agent tool decorator pattern (@agent_tool)
    - Non-streaming Gemini tool dispatch loop (adapted from router.py)
    - unittest.mock AsyncMock for Gemini API mocking
key_files:
  created:
    - backend/app/agents/cube_expert.py
    - backend/tests/test_cube_expert.py
  modified:
    - backend/app/agents/tools/catalog_tools.py
decisions:
  - "find_cubes_for_task uses keyword frequency scoring (count of keywords present in haystack) — simple, no external deps, fast enough for <100 cubes"
  - "CubeExpert uses non-streaming generate_content (not generate_content_stream) — sub-agent result consumed programmatically, not streamed to browser"
  - "TestCubeExpert uses module-level patches (app.agents.cube_expert.X) to intercept Gemini client, skills_loader, and dispatch_tool"
metrics:
  duration_minutes: 20
  completed_date: "2026-03-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 19 Plan 02: Cube Expert Sub-Agent — Summary

**One-liner:** CubeExpert Python class wrapping a dedicated gemini-2.5-flash call with cube_expert persona and keyword-search find_cubes_for_task tool (11 TDD tests, all mocked).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | find_cubes_for_task tool + tests | 538f0c1 | catalog_tools.py, test_cube_expert.py |
| 2 | CubeExpert class + mocked Gemini tests | ea21279 | cube_expert.py, test_cube_expert.py |

## What Was Built

### find_cubes_for_task tool (catalog_tools.py)

Appended to the existing two-tool catalog module as a third `@agent_tool`. Performs case-insensitive keyword scoring across `cube_id`, `name`, and `description` fields of every registered cube. Returns results ranked by keyword hit count, capped by the `limit` parameter (default 5). Handles missing registry gracefully with `{"error": "Cube registry not available"}`.

### CubeExpert class (cube_expert.py)

A standalone Python class with a single `async def ask(task, ctx)` method. Design constraints honored:

- **No HTTP endpoint** (per D-12) — pure Python object, no `@router` or `APIRouter`
- **Task string only** (per D-13) — history built fresh from the task string, no orchestrator context passed in
- **gemini-2.5-flash** (per D-10) — uses `settings.gemini_flash_model`
- **cube_expert persona** — calls `get_system_prompt("cube_expert")`
- **Non-streaming dispatch loop** — uses `client.aio.models.generate_content` (not streaming), dispatches tool calls via `dispatch_tool`, loops up to 10 rounds

### Tests (test_cube_expert.py)

11 tests across two test classes:

- `TestFindCubes` (5 tests): keyword_match, no_match, limit, ranked order, no_registry
- `TestCubeExpert` (6 tests): text_response, tool_call_dispatch, empty_response, flash_model_used, cube_expert_persona, task_isolation (D-13 verified)

All tests use mocked dependencies — no real Gemini API calls, no database.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `pytest.ANY` used in test — `unittest.mock.ANY` required**
- **Found during:** Task 2 GREEN run
- **Issue:** Test used `pytest.ANY` which does not exist in pytest; `unittest.mock.ANY` is the correct sentinel
- **Fix:** Added `ANY` to the `from unittest.mock import ...` import and replaced `pytest.ANY` with `ANY`
- **Files modified:** `backend/tests/test_cube_expert.py`
- **Commit:** ea21279 (included in Task 2 commit)

### Out-of-Scope Pre-existing Failures

`tests/test_all_flights.py::test_cube_inputs` fails due to upstream changes to `all_flights.py` (airport field added to cube inputs but not yet reflected in test expectations). Pre-existing before this plan; logged to deferred items — not caused by plan 02 changes.

## Known Stubs

None — all functionality is fully wired. `find_cubes_for_task` searches the live `CubeRegistry` and `CubeExpert.ask()` makes real Gemini calls (mocked only in tests).

## Self-Check

Files created/modified:
- `backend/app/agents/cube_expert.py` — created
- `backend/app/agents/tools/catalog_tools.py` — modified (find_cubes_for_task appended)
- `backend/tests/test_cube_expert.py` — created

Commits:
- 538f0c1 — feat(19-02): add find_cubes_for_task tool and TestFindCubes tests
- ea21279 — feat(19-02): implement CubeExpert sub-agent class with TDD tests
