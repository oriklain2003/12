---
phase: 20-canvas-agent
plan: 01
subsystem: backend/agents
tags: [canvas-agent, tools, sse, context, schema]
provides: [canvas-tools, extended-tool-context, extended-agent-schema]
affects:
  - backend/app/agents/context.py
  - backend/app/agents/schemas.py
  - backend/app/agents/router.py
  - backend/app/agents/tools/canvas_tools.py
tech-stack:
  added: []
  patterns: [agent-tool-decorator, tool-context-injection]
key-files:
  created:
    - backend/app/agents/tools/canvas_tools.py
    - backend/tests/test_canvas_agent.py
  modified:
    - backend/app/agents/context.py
    - backend/app/agents/schemas.py
    - backend/app/agents/router.py
    - backend/app/agents/tools/__init__.py
key-decisions:
  - "propose_graph_diff schema kept flat (no $defs/$ref) for Gemini compatibility"
  - "position_x/position_y restructured to position:{x,y} in propose_graph_diff for React Flow"
  - "mode prefix prepended to effective_message in router, not system prompt"
  - "canvas_tools imported in tools/__init__.py to guarantee registration at startup"
patterns-established: [flat-gemini-schema, canvas-context-injection]
duration: "15min"
completed: 2026-03-25
requirements: [CANVAS-03, CANVAS-05]
---

# Phase 20 Plan 01: Canvas Agent Tools and Context Extension Summary

**Four canvas @agent_tool functions registered with extended ToolContext/AgentChatRequest carrying workflow_graph, execution_errors, execution_results, and mode from HTTP request body through to tool functions.**

## Performance

- **Duration:** 15 minutes
- **Tasks:** 2 completed
- **Files modified:** 6

## Accomplishments

- Extended `ToolContext` with `workflow_graph`, `execution_errors`, `execution_results` fields
- Extended `AgentChatRequest` with same three fields plus `mode: str = "general"`
- Router wires all canvas context fields into ToolContext; mode prefix injected into effective_message
- Created `read_workflow_graph`, `propose_graph_diff`, `read_execution_errors`, `read_execution_results` tools
- `propose_graph_diff` uses flat schema (no `$defs`/`$ref`) and restructures `position_x/y` to nested `position: {x, y}`
- `read_execution_results` summarizes to `{row_count, columns, sample_rows[:3], truncated}` — prevents context bloat
- All 4 tools registered and discoverable via `get_all_tools()`; 8 unit tests passing

## Task Commits

1. **Task 1: Extend ToolContext, AgentChatRequest, and router** - `fa0e09b`
2. **Task 2: Create canvas_tools.py + unit tests** - `f2ccbb8`

## Files Created/Modified

- `backend/app/agents/context.py` - Added 3 canvas context fields to ToolContext dataclass
- `backend/app/agents/schemas.py` - Added 4 canvas fields to AgentChatRequest
- `backend/app/agents/router.py` - Wires canvas fields into ToolContext; adds mode prefix logic
- `backend/app/agents/tools/canvas_tools.py` - Four @agent_tool functions for canvas operations
- `backend/app/agents/tools/__init__.py` - Imports canvas_tools for auto-registration
- `backend/tests/test_canvas_agent.py` - 8 unit tests covering all tools and edge cases

## Decisions & Deviations

**Decisions:**
- `propose_graph_diff` uses flat Gemini-compatible schema with no `$defs`/`$ref`
- `position_x`/`position_y` are flat Gemini parameters restructured to `position: {x, y}` for React Flow
- Mode prefix added to `effective_message` string (not system prompt) to avoid contaminating persona skills

**Deviations:** None - plan executed exactly as written.

## Known Stubs

None - all tools return correct data or error dicts; no placeholder values.

## Next Phase Readiness

Plan 20-02 (frontend chat panel, applyAgentDiff Zustand action) can proceed. Backend tool contract is complete:
- `POST /api/agent/chat` accepts `workflow_graph`, `execution_errors`, `execution_results`, `mode` in body
- All four canvas tools registered and tested
- ToolContext carries canvas fields to all tool functions
