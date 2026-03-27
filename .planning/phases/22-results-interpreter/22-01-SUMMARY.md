---
phase: 22
plan: "01"
subsystem: backend-agents
tags: [results-interpreter, sse, gemini, skill-files, interpreter-tools]
dependency_graph:
  requires: [21-01, 18-04]
  provides: [interpret-endpoint, interpreter-tools, results-interpreter-skill]
  affects: [backend/app/agents/router.py, backend/app/agents/schemas.py]
tech_stack:
  added: []
  patterns: [agent_tool-decorator, one-shot-sse, BFS-upstream-walk]
key_files:
  created:
    - backend/app/agents/tools/interpreter_tools.py
    - backend/app/agents/skills/results_followup.md
  modified:
    - backend/app/agents/schemas.py
    - backend/app/agents/tools/__init__.py
    - backend/app/agents/skills/results_interpreter.md
    - backend/app/agents/router.py
decisions:
  - "One-shot SSE endpoint with empty history — no session management for interpret calls"
  - "Mission context fetched from DB JSONB (graph_json.metadata.mission) on each interpret call"
  - "results_interpreter uses flash model (not pro) — appropriate for summarization not reasoning"
  - "read_cube_results returns sample_rows[:10] for follow-up detail; _summarize_selected_cube caps at [:3] for one-shot prompt to avoid LLM context bloat"
metrics:
  duration_minutes: 12
  completed_date: "2026-03-27"
  tasks_completed: 2
  files_changed: 6
---

# Phase 22 Plan 01: Backend Results Interpreter Infrastructure Summary

Backend infrastructure for the Results Interpreter: SSE interpret endpoint, BFS pipeline walk tools, expanded cube-type-framing skill file, and follow-up agent persona.

## What Was Built

### InterpretRequest schema (schemas.py)

Added `InterpretRequest` Pydantic model with fields `workflow_id`, `workflow_graph`, `execution_results`, `selected_cube_id` (required), `cube_name` (required), `cube_category` (default "unknown").

### Interpreter tools (interpreter_tools.py)

Two new `@agent_tool` decorated tools:

**`read_pipeline_summary`** — BFS upstream walk from a node ID using `edge["target"] == current` pattern, collects `cube_id` for each visited node, reverses the chain, returns `{"pipeline": "source -> filter -> analysis", "cube_count": N}`.

**`read_cube_results`** — Fetches results for a specific node from `ctx.execution_results`, handles both dict-with-rows and list formats, returns `sample_rows[:10]`, includes `available_node_ids` in error response for debugging.

### Expanded results_interpreter.md

Replaced stub 4-line skill with full expanded content covering:
- Cube-Type Framing by category (data_source, filter/squawk, filter/geo, analysis, aggregation, unknown)
- Empty Results guidance with actionable next steps per cube type (per D-12)
- Pipeline Context narration pattern (per D-10)
- Mission Context grounding with example (per D-08)
- Interpretation style rules: flowing narrative, 2-4 paragraphs, no bullet dumps

### results_followup.md skill (new)

New persona for conversational drill-down after the initial interpretation. References `read_cube_results` and `read_pipeline_summary` tools, stays focused on results, directs workflow modifications to Canvas Agent.

### POST /api/agent/interpret endpoint (router.py)

One-shot SSE endpoint that:
1. Fetches mission context from DB via `_get_mission_context` (queries `Workflow.graph_json.metadata.mission`)
2. Summarizes selected cube results capped at 3 rows via `_summarize_selected_cube`
3. Walks upstream pipeline via `_build_pipeline_str` (same BFS logic as interpreter tool)
4. Builds structured LLM message via `_build_interpret_message` (cube + result + pipeline + mission)
5. Streams via `_agent_turn_stream` with `persona="results_interpreter"` and empty history (no session)

## Decisions Made

- **One-shot SSE, no session**: Each interpret call is independent — no history accumulation. Follow-up chat uses the separate `results_followup` persona via the existing `/api/agent/chat` endpoint.
- **Mission context from DB**: Even if `workflow_graph` is passed in the body, mission context is fetched fresh from the DB on each call to ensure it reflects the saved state.
- **Flash model for interpreter**: `results_interpreter` is not in `pro_personas` set — it uses `gemini-flash` since summarization does not require deep reasoning.
- **Cap discrepancy is intentional**: `_summarize_selected_cube` uses `rows[:3]` (compact one-shot prompt), while `read_cube_results` tool uses `rows[:10]` (for follow-up detail questions).

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files created/modified:
- FOUND: /Users/oriklain/work/five/tracer/12-flow/backend/app/agents/tools/interpreter_tools.py
- FOUND: /Users/oriklain/work/five/tracer/12-flow/backend/app/agents/skills/results_followup.md
- FOUND: /Users/oriklain/work/five/tracer/12-flow/backend/app/agents/schemas.py (InterpretRequest class present)
- FOUND: /Users/oriklain/work/five/tracer/12-flow/backend/app/agents/skills/results_interpreter.md (Cube-Type Framing present)
- FOUND: /Users/oriklain/work/five/tracer/12-flow/backend/app/agents/router.py (interpret endpoint present)

Commits:
- FOUND: 11e7bcb (Task 1)
- FOUND: c7f8547 (Task 2)
