---
phase: 19-cube-expert-validation-agent
plan: 01
subsystem: backend/agents
tags: [validation, fastapi, pydantic, tdd, pure-python]
dependency_graph:
  requires: []
  provides: [POST /api/agent/validate, validate_graph, ValidationIssue, ValidationRequest, ValidationResponse]
  affects: [backend/app/agents/router.py, backend/app/agents/schemas.py]
tech_stack:
  added: []
  patterns: [rule-based validator, TDD red-green, sync FastAPI endpoint, mock registry for tests]
key_files:
  created:
    - backend/app/agents/validation.py
    - backend/tests/test_validation.py
  modified:
    - backend/app/agents/schemas.py
    - backend/app/agents/router.py
decisions:
  - Cycle check returns early — other rules are meaningless in cyclic graphs, so returning a single cycle issue avoids misleading cascading errors
  - __full_result__ special handle is exempted from dangling_source_handle check (it's a valid convention, not a param name)
  - validate_graph is a regular (non-async) function — no I/O, purely in-memory; async def endpoint wraps it per FastAPI convention
  - ValidationResponse.has_errors is a @property (not a field) so it computes dynamically and is excluded from JSON serialization
metrics:
  duration: ~15 minutes
  completed: "2026-03-24"
  tasks_completed: 2
  files_changed: 4
  tests_added: 15
---

# Phase 19 Plan 01: Rule-Based Workflow Validation Engine Summary

Rule-based graph validator implementing 7 structural checks (cycle, unknown_cube, missing_required_param, dangling handles, type_mismatch, orphan_node) with Pydantic schemas, sync FastAPI endpoint, and 15 TDD tests covering all rules.

## What Was Built

### backend/app/agents/validation.py (new)

`validate_graph(graph, registry) -> ValidationResponse` — pure Python, no LLM, no DB. Runs 7 checks in order:

1. **cycle** — `topological_sort()` raises ValueError; returns early with single cycle error
2. **unknown_cube** — node references unregistered cube_id; flags and skips further checks for that node
3. **missing_required_param** — required input not connected and not manually set
4. **dangling_source_handle** — edge sourceHandle not in cube outputs (`__full_result__` always exempt)
5. **dangling_target_handle** — edge targetHandle not in cube inputs
6. **type_mismatch** — connected params have different ParamType values (warning, not error)
7. **orphan_node** — node with zero edges in multi-node graph (warning, not error)

### backend/app/agents/schemas.py (modified)

Three new Pydantic models appended after `MissionContext`:
- `ValidationIssue` — severity, node_id, cube_name, param_name, message, rule
- `ValidationRequest` — wraps `WorkflowGraph`
- `ValidationResponse` — issues list + `has_errors` property

### backend/app/agents/router.py (modified)

```python
@router.post("/validate", response_model=ValidationResponse)
async def validate_workflow(body: ValidationRequest) -> ValidationResponse:
```

Sync endpoint — no DB dependency, no LLM calls. Returns JSON with issues array.

### backend/tests/test_validation.py (new)

15 tests across 2 classes:
- `TestValidation` (12 tests): one per rule + satisfied variants + has_errors property
- `TestValidateEndpoint` (3 tests): httpx ASGI integration tests

## Task Commits

| Task | Description | Commit |
|------|-------------|--------|
| RED  | Failing tests for all 11 behaviors | 74aa0a9 |
| Task 1 GREEN | validation.py + schemas.py | fc545ea |
| Task 2 | Router endpoint + integration tests | fd66480 |

## Deviations from Plan

None — plan executed exactly as written. All 15 acceptance criteria satisfied.

## Known Stubs

None. The validation engine is fully functional — all 7 rules produce concrete issue objects.

## Self-Check: PASSED

- `backend/app/agents/validation.py` — exists, contains `validate_graph`, all 7 rules
- `backend/app/agents/schemas.py` — contains `ValidationIssue`, `ValidationRequest`, `ValidationResponse`
- `backend/app/agents/router.py` — contains `@router.post("/validate"` and `validate_graph(body.graph, cube_registry)`
- `backend/tests/test_validation.py` — contains all required test methods (15 tests pass)
- Commits 74aa0a9, fc545ea, fd66480 verified in git log
