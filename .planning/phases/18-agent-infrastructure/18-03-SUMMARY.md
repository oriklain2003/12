---
phase: 18-agent-infrastructure
plan: 03
subsystem: api
tags: [agents, tool-registry, dispatcher, gemini, context-management]

# Dependency graph
requires:
  - phase: 18-agent-infrastructure
    provides: agents package scaffolding from plan 01/02

provides:
  - Tool registry with @agent_tool decorator-based registration
  - Tool dispatcher with retry and error-as-result handling
  - ToolContext dataclass carrying db_session, cube_registry, workflow_id
  - History pruning logic at 50k token threshold
  - Two placeholder catalog tools for Phase 19 (list_cubes_summary, get_cube_definition)

affects: [19-cube-expert, 20-canvas-agent, 21-build-wizard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Decorator-based tool registration via @agent_tool — mirrors CubeRegistry auto-discovery pattern"
    - "Error-as-result pattern — tool failures return {error: str} dict, never raise, so Gemini can reason about failures"
    - "Context injection — ToolContext passed as first arg to every tool function by dispatcher"
    - "Flat JSON Schema for Gemini tool declarations — no nested $defs to avoid schema rejection"
    - "History pruning at 50k token threshold — drops oldest non-system turns first"

key-files:
  created:
    - backend/app/agents/context.py
    - backend/app/agents/registry.py
    - backend/app/agents/dispatcher.py
    - backend/app/agents/tools/__init__.py
    - backend/app/agents/tools/catalog_tools.py
  modified: []

key-decisions:
  - "Registry keeps tool fn references in module-level dict; conversion to google.genai types happens in router to keep registry google-free"
  - "MAX_RETRIES=1 in dispatcher — retry once on transient errors, then return error dict"
  - "PRUNE_THRESHOLD_TOKENS=50_000 constant; estimate_tokens returns token count (chars//4)"
  - "catalog_tools.py is placeholder — Phase 19 will add full cube lookup logic"

patterns-established:
  - "agent_tool decorator: register async fn with name, description, flat JSON schema"
  - "dispatch_tool(name, args, ctx): lookup -> inject ctx -> retry -> error dict"
  - "prune_history(history, system_prompt_turns=1): drop oldest turns while > 50k tokens"

requirements-completed: [INFRA-05, INFRA-06]

# Metrics
duration: 2min
completed: 2026-03-24
---

# Phase 18 Plan 03: Tool Registry, Dispatcher, Context Management Summary

**Decorator-based tool registry with retry dispatcher and ToolContext injection; two placeholder catalog tools ready for Phase 19.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T14:10:17Z
- **Completed:** 2026-03-24T14:12:23Z
- **Tasks:** 2 of 2
- **Files modified:** 5

## Accomplishments

- Built `@agent_tool` decorator that registers async functions in module-level dict keyed by tool name; mirrors existing CubeRegistry pattern
- Built `dispatch_tool()` with MAX_RETRIES=1 retry loop and error-as-result return (never raises) so Gemini can reason about failures
- Built `ToolContext` dataclass + `prune_history()` with 50k token threshold; drops oldest non-system turns to prevent context explosion

## Task Commits

1. **Task 1: ToolContext and history pruning** - `5fa456f` (feat)
2. **Task 2: Tool registry, dispatcher, catalog tools** - `c193a6d` (feat)

## Files Created/Modified

- `backend/app/agents/context.py` - ToolContext dataclass, estimate_tokens(), prune_history(), PRUNE_THRESHOLD_TOKENS
- `backend/app/agents/registry.py` - @agent_tool decorator, RegisteredTool dataclass, get_tool(), get_all_tools(), get_gemini_tool_declarations(), get_all_tool_declarations()
- `backend/app/agents/dispatcher.py` - dispatch_tool() with retry and error-as-result
- `backend/app/agents/tools/__init__.py` - Package init (import tool modules here to trigger registration)
- `backend/app/agents/tools/catalog_tools.py` - list_cubes_summary and get_cube_definition placeholder tools registered via @agent_tool

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- `catalog_tools.py::list_cubes_summary` and `get_cube_definition` — placeholder implementations. Phase 19 (Cube Expert) will add full filtering, caching, and richer output. Both are intentional stubs as documented in plan.
