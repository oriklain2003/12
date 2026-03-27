# Phase 18: Agent Infrastructure - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the foundational Gemini LLM layer that all agents (Phases 19-22) build on: async client, SSE streaming with real-time tool/thinking visibility, tool dispatch, skill files, context management with server-side sessions, and mission persistence. This phase delivers no user-facing agent features — only the infrastructure that downstream phases consume.

</domain>

<decisions>
## Implementation Decisions

### Skill File Design
- **D-01:** One markdown file per agent persona in `backend/app/agents/skills/` — e.g., `canvas_agent.md`, `build_agent.md`, `cube_expert.md`, `validation_agent.md`, `results_interpreter.md`
- **D-02:** System brief is a separate hand-written `system_brief.md` file describing Tracer 42 domain context (database schema, cube ecosystem, analyst workflow). Injected at the top of every agent prompt. Updated manually when cubes change.
- **D-03:** Skill files loaded once at FastAPI lifespan startup and cached in memory. Requires server restart to pick up prompt changes (acceptable; uvicorn --reload handles dev).

### Tool Dispatch API
- **D-04:** Decorator-based tool registration — `@agent_tool(name='...', description='...')` on plain async functions. A registry collects them at import time, similar to FastAPI route discovery.
- **D-05:** Tool input schemas defined as Pydantic models. Auto-converted to Gemini's JSON schema format. Validates input before execution.
- **D-06:** On tool failure: retry once for transient errors, then return the error message to the LLM as the tool result so Gemini can reason about it.
- **D-07:** Tool functions receive an injected `ToolContext` dataclass containing `db_session`, `cube_registry`, `workflow_id`, etc. Passed by the dispatcher, not imported globally.

### Context & History Management
- **D-08:** Server-side sessions stored in an in-memory dict keyed by session_id. Frontend sends session_id + new message each turn (NOT full message array). This departs from the research assumption of client-carried history.
- **D-09:** 30-minute TTL on sessions with periodic background cleanup to prevent memory leaks from abandoned conversations.
- **D-10:** Token counting uses approximate char-based estimation (~4 chars per token). Good enough for the 50k threshold.
- **D-11:** History pruning: drop oldest user/assistant turn pairs first, always keep system prompt + recent turns. Tool results from old turns are the first to go (biggest token consumers).

### SSE Streaming
- **D-12:** Real-time streaming of agent thinking and tool execution to the client. The SSE stream uses typed events: `text` (streaming tokens), `tool_call` (tool name + args being invoked), `tool_result` (output from tool), `thinking` (model reasoning if available), `done` (turn complete). Frontend renders each event type differently.
- **D-13:** SSE disconnect detection: check `await request.is_disconnected()` before each yield (from research decision).

### Config & API Key
- **D-14:** `GEMINI_API_KEY` added to the existing `Settings` class in `config.py`, loaded from `.env` alongside `DATABASE_URL`. Consistent with existing pattern.
- **D-15:** Model names configurable via Settings with defaults: `gemini_flash_model='gemini-2.5-flash'`, `gemini_pro_model='gemini-2.5-pro'`. Changeable via env vars without code changes.
- **D-16:** Simple retry with exponential backoff (up to 2 retries) on transient Gemini errors (429, 503). No client-side rate limiting.

### Claude's Discretion
- Tool dispatch implementation details (decorator internals, registry data structures)
- Pydantic-to-Gemini schema conversion approach
- Session cleanup background task implementation
- SSE event serialization format (JSON structure within each event type)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture Decisions (from v3.0 research)
- `.planning/STATE.md` §Key Decisions (v3.0 Architecture) — locked architecture decisions including async-only Gemini calls, manual tool dispatch, two-tier catalog, agent layer isolation
- `.planning/REQUIREMENTS.md` §Agent Infrastructure — INFRA-01 through INFRA-07 requirement definitions

### Existing Patterns
- `backend/app/routers/workflows.py` — existing SSE streaming pattern with `sse_starlette.EventSourceResponse`
- `backend/app/engine/registry.py` — CubeRegistry auto-discovery pattern (model for tool registry)
- `backend/app/engine/executor.py` — `stream_graph()` existing SSE generator pattern
- `backend/app/config.py` — Settings class pattern for new config fields
- `backend/app/main.py` — lifespan hook pattern for startup initialization
- `backend/app/schemas/workflow.py` — WorkflowGraph schema (agents will read/generate this)
- `backend/app/models/workflow.py` — Workflow ORM model (mission persistence target, JSONB metadata)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `sse_starlette.EventSourceResponse` — already a dependency, used for workflow execution streaming. Agent SSE endpoint can follow the same pattern with typed events.
- `CubeRegistry` — auto-discovery pattern via `pkgutil.iter_modules`. Tool registry can follow a similar decorator + collection approach.
- `Settings` (pydantic-settings) — existing config pattern. Adding `gemini_api_key`, model names, and session TTL follows the established convention.
- `WorkflowGraph` Pydantic model — agents will generate and validate these schemas.

### Established Patterns
- All async with `asyncpg` — Gemini calls must use `client.aio` to not block the event loop
- SSE via `sse_starlette` with `ServerSentEvent` — existing pattern for typed events
- Router-based organization — new `backend/app/routers/agent.py` for agent endpoints
- Pydantic models for all API contracts — tool schemas follow naturally

### Integration Points
- `backend/app/main.py` lifespan — skill file loading, session cleanup task startup, Gemini client initialization
- `backend/app/main.py` router inclusion — `app.include_router(agent_router)`
- `backend/app/engine/registry.py` — tools need access to `registry.catalog()` and `registry.get()`
- `backend/app/models/workflow.py` — mission context persistence in workflow JSONB metadata

</code_context>

<specifics>
## Specific Ideas

- User specifically wants agent thinking and tool execution streamed to the client in real time — this is a core UX requirement, not optional
- Server-side sessions (in-memory dict + TTL) chosen over client-carried history — simpler frontend, server manages state

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 18-agent-infrastructure*
*Context gathered: 2026-03-24*
