# Phase 19: Cube Expert + Validation Agent - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Analysts can run pre-flight validation before executing a workflow and see human-readable explanations of structural issues; agents have a reliable two-tier catalog sub-agent (Cube Expert) to look up cubes. This phase delivers: (1) rule-based structural validation with template explanations, (2) a sync validation endpoint, (3) pre-run validation trigger in the frontend, (4) Cube Expert as an internal sub-agent with its own Gemini call and three catalog tools.

</domain>

<decisions>
## Implementation Decisions

### Validation Rules & Severity
- **D-01:** Two severity levels only: **error** (blocks execution) and **warning** (informational).
- **D-02:** Errors: missing required parameters, dangling input/output handles (sourceHandle/targetHandle not found in cube definition), cycles in the graph.
- **D-03:** Warnings: type mismatches between connected parameters (matches existing app behavior — mismatches allowed with warning per PROJECT.md), orphan nodes (cubes with zero connections).
- **D-04:** Handle validation checks that both sourceHandle and targetHandle exist in the respective cube definitions. Catches stale edges after cube changes.

### Validation Trigger & UX
- **D-05:** Validation runs automatically when the user clicks Run (pre-run only). No standalone Validate button — keeps the UI simple. Matches VALID-03 requirement.
- **D-06:** If errors exist, execution is blocked and the issues panel opens. Warnings do not block execution.
- **D-07:** Issues displayed in a collapsible panel below the canvas (console/terminal style). Each issue shows cube name, parameter name, and explanation. Clicking an issue highlights the relevant node on canvas.
- **D-08:** When validation passes cleanly (zero issues), execution starts immediately with no confirmation dialog or toast. Silent pass-through for the happy path.

### Cube Expert Sub-Agent
- **D-09:** Cube Expert is invoked via a **separate Gemini call** with its own chat turn using `cube_expert.md` skill file. Not direct function calls — dedicated sub-agent reasoning for richer cube selection logic.
- **D-10:** Uses **gemini-2.5-flash** model (per STATE.md architecture decision). Fast and cheap enough for sub-agent calls that happen mid-conversation.
- **D-11:** Three tools available to Cube Expert: `list_cubes_summary` (existing), `get_cube_definition` (existing), and a new `find_cubes_for_task` (keyword search across cube descriptions/params — pure string matching, no LLM).
- **D-12:** Internal only — no `/api/agent/cube-expert` HTTP endpoint. Per STATE.md: "Cube Expert is a Python object, never an HTTP endpoint." Called by Canvas Agent (Phase 20) and Build Agent (Phase 21) internally.
- **D-13:** Sub-agent receives only the task description, not the orchestrator's full history (per STATE.md: "sub-agent receives task description only, not orchestrator full history").

### LLM Role in Validation
- **D-14:** All validation checks are **pure rule-based Python code**. No LLM involvement in structural checking. Fast (<100ms), deterministic, no API cost.
- **D-15:** Human-readable explanations use **pre-written templates** per issue type with cube/param names filled in. e.g., "Cube 'squawk_filter' is missing required input 'flights_data'. Connect a data source to this input." No Gemini call in the validation path.
- **D-16:** Validation endpoint is **sync JSON**: `POST /api/agent/validate` returns a JSON response with issues array. Per STATE.md architecture.

### Claude's Discretion
- Validation rule implementation details (how to traverse the graph, check handle existence)
- `find_cubes_for_task` search algorithm (keyword matching, TF-IDF, or simple substring)
- Cube Expert Python class structure and how it wraps the Gemini call
- Issues panel frontend component design and node highlighting mechanism
- Validation response schema shape

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture Decisions
- `.planning/STATE.md` §Key Decisions (v3.0 Architecture) — locked decisions: two-tier catalog, Cube Expert as Python object, three agent endpoints, sub-agent history isolation, flash model for Cube Expert
- `.planning/REQUIREMENTS.md` §Cube Expert (CUBE-01..03) and §Validation Agent (VALID-01..03) — requirement definitions

### Phase 18 Infrastructure (built, ready to use)
- `backend/app/agents/registry.py` — `@agent_tool` decorator, `RegisteredTool`, `get_gemini_tool_declarations()`
- `backend/app/agents/dispatcher.py` — `dispatch_tool()` with retry and ToolContext injection
- `backend/app/agents/context.py` — `ToolContext` dataclass, `prune_history()`, `estimate_tokens()`
- `backend/app/agents/tools/catalog_tools.py` — existing `list_cubes_summary` and `get_cube_definition` implementations (functional, not stubs)
- `backend/app/agents/skills/cube_expert.md` — Cube Expert persona skill file
- `backend/app/agents/skills/validation_agent.md` — Validation Agent persona skill file
- `backend/app/agents/router.py` — SSE chat endpoint pattern, Gemini tool declaration building
- `backend/app/agents/sessions.py` — session management pattern
- `backend/app/agents/client.py` — Gemini client singleton
- `backend/app/agents/schemas.py` — AgentChatRequest, AgentSSEEvent schemas

### Existing Patterns for Validation
- `backend/app/engine/executor.py` — `topological_sort()` already detects cycles via Kahn's algorithm
- `backend/app/schemas/cube.py` — `ParamDefinition` with `required`, `type`, `accepts_full_result` fields; `CubeDefinition` with `inputs`/`outputs`
- `backend/app/schemas/workflow.py` — `WorkflowGraph`, `WorkflowNode` (with `cube_id`, `params`), `WorkflowEdge` (with `sourceHandle`/`targetHandle`)
- `backend/app/engine/registry.py` — `CubeRegistry` with `.catalog()` and `.get()` for cube lookup

### Frontend Integration Points
- `backend/app/routers/workflows.py` — existing Run endpoint that validation must gate

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `catalog_tools.py`: Both `list_cubes_summary` and `get_cube_definition` are fully implemented and working — Phase 19 extends with `find_cubes_for_task`, not rewrites
- `topological_sort()`: Cycle detection already works — validation can call this directly rather than reimplementing
- `CubeRegistry.get(cube_id)` + `.definition.inputs/.outputs`: Direct access to param definitions for handle and required-param validation
- `@agent_tool` decorator: New `find_cubes_for_task` tool registers the same way as existing catalog tools
- `ToolContext`: Provides `cube_registry` access — all validation checks can use it
- Gemini client singleton + tool dispatch loop in `router.py`: Pattern for Cube Expert's own Gemini call

### Established Patterns
- Tool registration via `@agent_tool` decorator in `tools/` directory
- Skill files as markdown in `skills/` directory, loaded at startup
- Sync endpoints alongside SSE endpoints in the agent router
- Pydantic models for all API contracts in `schemas.py`

### Integration Points
- `backend/app/agents/router.py` — add `POST /api/agent/validate` sync endpoint
- `backend/app/agents/tools/` — add `find_cubes_for_task` tool (new file or extend `catalog_tools.py`)
- `backend/app/agents/` — add Cube Expert sub-agent class (wraps Gemini call with skill file + tools)
- `backend/app/routers/workflows.py` — frontend calls validate before run (or validation is called from within run endpoint)
- Frontend: new issues panel component below canvas, node highlighting on issue click

</code_context>

<specifics>
## Specific Ideas

- User chose separate Gemini call for Cube Expert (not direct tool calls) — wants richer reasoning about which cube fits a use case, even at the cost of an extra LLM round-trip
- Validation is intentionally LLM-free — rule-based checks + template explanations for speed and determinism
- Issues panel should feel like a console/terminal below the canvas, not a modal dialog
- Clicking an issue should highlight the relevant node on canvas (visual navigation)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 19-cube-expert-validation-agent*
*Context gathered: 2026-03-24*
