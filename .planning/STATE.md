---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: AI Workflow Agents
status: completed
last_updated: "2026-03-27T14:27:24.822Z"
last_activity: 2026-03-27
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 16
  completed_plans: 16
---

# Project State: Project 12

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-22)

**Core value:** Users can build and run custom flight analysis pipelines visually — now assisted by AI agents that help create, edit, optimize, and debug workflows
**Current focus:** Phase 22 — results-interpreter

## Current Milestone

**v3.0:** Roadmap defined — AI Workflow Agents (Phases 18-22)

Status: Roadmap complete — 5 phases, 28 requirements mapped
Last activity: 2026-03-27

### Phase Overview

| Phase | Name | Requirements | Status |
|-------|------|-------------|--------|
| 18 | Agent Infrastructure | INFRA-01 through INFRA-07 | Complete (4/4 plans) |
| 19 | Cube Expert + Validation Agent | CUBE-01..03, VALID-01..03 | Complete (3/3 plans, human-verify approved) |
| 20 | Canvas Agent | CANVAS-01 through CANVAS-07 | Not started |
| 21 | Build Wizard Agent | BUILD-01 through BUILD-05 | Complete (3/3 plans, skill rewrite applied) |
| 22 | Results Interpreter | RESULT-01 through RESULT-03 | Complete (2/2 plans, bug-fix applied) |

### Current Position

Phase: 22
Plan: Not started

## Previous Milestones

**v2.0:** In Progress — Advanced Flight Analysis Cubes (phases 11-17, 6/7 complete, phase 13 deferred)

**v1.0:** Shipped 2026-03-06
10 phases, 23 plans, 55 requirements satisfied (53 full, 2 partial).
See `.planning/MILESTONES.md` for details.

## Accumulated Context

### Tech Debt (from v1.0 audit)

- Orphaned `GET /api/workflows/{id}/run/stream` route (no frontend caller)
- `execute_graph()` dead production code in executor.py
- AllFlights/GetAnomalies SQL `LIMIT 5000` inconsistent with global 10,000 cap
- BACK-08 requirement text describes removed endpoint
- No VERIFICATION.md files for any phase (0/10)

### Key Decisions (v3.0 Architecture — from research)

- **2026-03-22:** Agent layer is one-way: `app/agents/` imports from existing packages (CubeRegistry, WorkflowGraph schema, sse-starlette) but existing packages never import from agents
- **2026-03-22:** All agents are stateless — conversation history is client-carried in the POST body; no server-side session store
- **2026-03-22:** Cube Expert is a Python object, never an HTTP endpoint — instantiated inside Canvas and Build agents
- **2026-03-22:** `google-genai>=1.68.0` required (v1.67.0 has typing-extensions bug); `google-generativeai` is deprecated and must not be used
- **2026-03-22:** Use `gemini-2.5-flash` for Canvas Agent and Cube Expert (latency), `gemini-2.5-pro` for Build Agent (reasoning depth)
- **2026-03-22:** `client.aio.models.generate_content_stream()` exclusively in async handlers — synchronous Gemini calls block event loop and break concurrent SSE workflow streams
- **2026-03-22:** Manual tool dispatch pattern (not automatic function calling + streaming) — Gemini `tool_config: ANY` for tool turns, then stream final text response
- **2026-03-22:** Two-tier catalog: `browse_catalog()` returns summaries only; `get_cube_definition(cube_name)` loads one cube on demand — never inline all definitions in system prompt
- **2026-03-22:** `applyAgentDiff()` Zustand action for atomic canvas mutations — calls `pushSnapshot()` first; never patch nodes incrementally
- **2026-03-22:** SSE disconnect detection: add `await request.is_disconnected()` before each `yield` — existing workflow SSE does not do this
- **2026-03-22:** Build Wizard uses clickable option cards only — no free text for cube selection; prevents LLM hallucination on analyst input
- **2026-03-22:** History pruning at 50k tokens; sub-agent (Cube Expert) receives task description only, not orchestrator full history
- **2026-03-22:** Three agent HTTP endpoints: `POST /api/agent/chat` (SSE), `POST /api/agent/validate` (sync), `POST /api/agent/interpret` (sync)
- **2026-03-24:** `types.Part.from_function_call/from_function_response` in google-genai 1.68.0 do not accept `id` parameter — used `name`+`args` only in router tool dispatch loop
- **2026-03-24:** Session ID sent as first SSE event (type=session) for frontend capture and reuse across turns
- **2026-03-24:** Agent lifespan init is conditional on `GEMINI_API_KEY` — graceful degradation when key absent; raises `RuntimeError` at request time
- **2026-03-24:** validate_graph cycle check returns early — other rules are meaningless in cyclic graphs; single cycle error prevents misleading cascading errors
- **2026-03-24:** __full_result__ sourceHandle is always exempt from dangling_source_handle check — it's a valid runtime convention, not a param name
- **2026-03-24:** IssuesPanel placed inside ReactFlowProvider in EditorPage — required for useReactFlow fitView hook to work within the panel
- **2026-03-24:** handleRun uses finally block for setIsValidating(false) — Run button always re-enables on network error; execution proceeds on validation failure (graceful degradation)
- **2026-03-24:** useRef(false) guard prevents auto-open Fix mode from firing more than once per failed run; resets when isRunning flips true (new run start)
- **2026-03-24:** Ctrl+Shift+A keyboard shortcut for chat panel placed before isInputField guard — works even when focus is inside textarea or input fields
- **2026-03-25:** Wizard tools (present_options, show_intent_preview) are intentionally pass-through — they return LLM-supplied data as structured dicts for frontend rendering; no DB interaction needed
- **2026-03-25:** generate_workflow returns validation_failed dict (not exception) so LLM can read errors and self-correct; retry logic is guided by skill file (up to 2 retries)
- **2026-03-25:** pro_personas set pattern in router.py allows future personas to opt into gemini-2.5-pro without changing conditional logic; build_agent added alongside canvas_agent
- **2026-03-25:** WizardChatMessage extends ChatMessage with toolData field in wizard.ts — isolated from shared agent.ts types to avoid polluting the canvas agent type surface
- **2026-03-25:** WizardPage uses useState not Zustand — wizard session state (messages, sessionId, isStreaming) is fully isolated from canvas flowStore
- **2026-03-25:** Dashboard "New Workflow" split into "Build with Wizard" (accent, /wizard) + "Blank Canvas" (glass, /workflow/new) per UI-SPEC D-02
- **2026-03-27:** results_interpreter is one-shot SSE with empty history — no session management; follow-up uses results_followup persona via /api/agent/chat
- **2026-03-27:** results_interpreter uses flash model — summarization does not require pro-level reasoning depth; flash sufficient for cube-type framing and narrative generation
- **2026-03-27:** chatPersona added to flowStore — EditorPage listens for open-results-followup event, sets persona in store; ChatInput reads it on each send; ChatPanel shows "Q&A" title when persona is results_followup; clearChat resets persona

### Critical Risks (from research)

1. **LLM hallucinating parameter handle IDs** — Force `get_cube_definition` calls before edge generation; validate every generated graph against live catalog via Pydantic + WorkflowExecutor before delivering to frontend
2. **Context explosion** — Never pass raw cube execution results to agents; summarize to `{cube, result_count, sample[3 rows], columns}`; prune history at 50k tokens
3. **Blocking event loop** — All LLM calls must use `client.aio` async interface exclusively

### Research Flags for Planning

- **Phase 20 (Canvas Agent):** Verify `applyAgentDiff` interaction with React Flow v12+ handle validation — confirm batch node+edge insertion in single Zustand update renders correctly. Run `/gsd:research-phase 20` during planning.
- All other phases: Standard patterns, skip research.

### Roadmap Evolution

- **2026-03-22:** v3.0 milestone started; requirements defined (28 requirements, 6 categories)
- **2026-03-22:** v3.0 roadmap created — 5 phases (18-22), 28/28 requirements mapped

---
*Last session: 2026-03-27 — Phase 22 Plan 02 complete. Frontend integration for Results Interpreter: renderMarkdown shared util extracted, streamInterpret SSE client added, InterpretPanel component with streaming/dismiss/discuss, ResultsDrawer wired with interpret button. Bug fix applied post-verification: chatPersona added to flowStore, EditorPage event listener, ChatInput persona passthrough, ChatPanel Q&A title. v3.0 milestone complete — all 5 agent phases done.*
