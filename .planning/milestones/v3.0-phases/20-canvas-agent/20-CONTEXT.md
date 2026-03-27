# Phase 20: Canvas Agent - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Analysts working in the editor can open a chat panel, describe what they want to change, and see the agent apply diffs to the canvas — without breaking existing node connections or workflow state. This phase delivers: (1) a collapsible right-sidebar chat panel with three modes, (2) Canvas Agent backend with graph-aware tools, (3) structured diff proposal and atomic canvas application via `applyAgentDiff()`, (4) SSE streaming of agent responses into the chat UI.

</domain>

<decisions>
## Implementation Decisions

### Chat Panel Layout
- **D-01:** Right sidebar panel in the editor. CubeCatalog stays on the left, chat panel on the right, canvas in the middle. Both sidebars can be open simultaneously — canvas shrinks between them.
- **D-02:** Panel is resizable via a drag handle on its left edge. Default width ~320px.
- **D-03:** Toggled via a toolbar button (chat icon in the Toolbar, next to Run/Save) AND a keyboard shortcut (Ctrl+Shift+A). Button may show a badge when agent has suggestions.
- **D-04:** Panel auto-opens in Fix mode when a workflow execution finishes with errors. Most proactive behavior — the agent surfaces itself when relevant.

### Mode Switching UX
- **D-05:** Three-segment toggle control at the top of the chat panel header: Optimize | Fix | General. Always visible, one click to switch. The active segment is the mode badge (satisfies CANVAS-02 "visible mode badge").
- **D-06:** Fix mode auto-activates (and panel auto-opens) when execution errors occur. The agent should show an initial prompt like "I see errors in [cube] — want me to diagnose?"
- **D-07:** Shared conversation history across all three modes. Switching modes changes the system prompt context sent to Gemini but does NOT clear the chat. One session ID per conversation, not per mode.

### Diff Preview & Apply
- **D-08:** Agent proposes changes via an inline text summary in the chat — a structured list of additions, removals, and modifications with Apply/Reject buttons below. No visual canvas preview or side-by-side diff.
- **D-09:** One diff at a time. Agent proposes one atomic set of changes, user accepts or rejects, then agent can propose another. No queued/batched diffs.
- **D-10:** On Apply: `pushSnapshot()` is called first (for Ctrl+Z undo), then `applyAgentDiff()` executes the atomic canvas mutation. Additionally, a "Discard Agent Changes" option is available that reloads the last saved workflow from the server (satisfies SC-4). Belt and suspenders: both Ctrl+Z undo and server reload available.
- **D-11:** The `propose_graph_diff` tool output includes structural changes (add/remove nodes, add/remove edges) AND parameter value updates on existing nodes. Full editing power across all three modes.

### Agent Tools & Context
- **D-12:** Canvas Agent has four tools beyond Cube Expert access:
  1. `read_workflow_graph` — returns current canvas state (nodes, edges, params)
  2. `propose_graph_diff` — structured diff output (add/remove nodes+edges, update params) rendered as inline summary with Apply/Reject in chat
  3. `read_execution_errors` — returns error messages from last workflow run (critical for Fix mode)
  4. `read_execution_results` — returns summarized results (row count, sample rows, columns) from last run, capped at store limit. Agent should communicate to the user that results shown are limited.
- **D-13:** Full workflow graph is serialized into the context of every Gemini request, so the agent always has an up-to-date view of the canvas without needing to call `read_workflow_graph` explicitly. The tool still exists for explicit re-reads if the graph changed mid-conversation (e.g., after user manually edits while chatting).
- **D-14:** Canvas Agent uses `gemini-2.5-flash` model (per STATE.md architecture decision). Cube Expert sub-agent is called internally when the agent needs to look up cube definitions or find cubes for a task.

### Claude's Discretion
- Chat panel open/close animation style and CSS implementation
- Drag handle resize implementation details
- Keyboard shortcut key binding (Ctrl+Shift+A suggested but flexible)
- SSE event rendering in chat messages (text streaming, tool call indicators, thinking display)
- `propose_graph_diff` JSON schema structure (as long as it supports add/remove nodes, add/remove edges, update params)
- How the "initial prompt" in Fix mode auto-open is generated (pre-written template vs. Gemini call)
- Chat input component design (textarea, send button, Enter behavior)
- Message bubble styling and agent/user visual distinction

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture Decisions
- `.planning/STATE.md` §Key Decisions (v3.0 Architecture) — locked decisions: `applyAgentDiff()` with `pushSnapshot()`, flash model for Canvas Agent, manual tool dispatch, two-tier catalog, agent layer isolation, SSE disconnect detection
- `.planning/REQUIREMENTS.md` §Canvas Agent (CANVAS-01..07) — requirement definitions and success criteria
- `.planning/ROADMAP.md` §Phase 20 — success criteria SC-1 through SC-5

### Phase 18 Infrastructure (built, ready to use)
- `backend/app/agents/router.py` — SSE chat endpoint pattern, `_agent_turn_stream()` tool dispatch loop, Gemini tool declaration building
- `backend/app/agents/client.py` — Gemini client singleton
- `backend/app/agents/registry.py` — `@agent_tool` decorator, `RegisteredTool`, `get_gemini_tool_declarations()`
- `backend/app/agents/dispatcher.py` — `dispatch_tool()` with retry and ToolContext injection
- `backend/app/agents/context.py` — `ToolContext` dataclass, `prune_history()`, `estimate_tokens()`
- `backend/app/agents/sessions.py` — session management (in-memory dict, 30min TTL)
- `backend/app/agents/schemas.py` — AgentChatRequest, AgentSSEEvent schemas
- `backend/app/agents/skills_loader.py` — skill file loading at startup

### Phase 19 Cube Expert (built, ready to use)
- `backend/app/agents/cube_expert.py` — CubeExpert sub-agent class with Gemini call + tools
- `backend/app/agents/tools/catalog_tools.py` — `list_cubes_summary`, `get_cube_definition`, `find_cubes_for_task`
- `backend/app/agents/skills/cube_expert.md` — Cube Expert persona skill file
- `backend/app/agents/validation.py` — `validate_graph()` for pre-run checks

### Frontend Patterns
- `frontend/src/pages/EditorPage.tsx` — editor layout (Toolbar, CubeCatalog, FlowCanvas, IssuesPanel, ResultsDrawer)
- `frontend/src/store/flowStore.ts` — Zustand store with `pushSnapshot()`, `serializeGraph()`, `deserializeGraph()`, node/edge actions, execution state, validation state
- `frontend/src/components/Validation/IssuesPanel.tsx` — collapsible panel pattern with useReactFlow integration (model for chat panel placement)
- `frontend/src/components/Toolbar/Toolbar.tsx` — toolbar button pattern (add chat toggle button here)
- `frontend/src/api/agent.ts` — existing agent API client (validation endpoint, extend with chat SSE)
- `frontend/src/components/Sidebar/CubeCatalog.tsx` — left sidebar pattern (chat panel mirrors this on the right)

### Existing Canvas Skills
- `backend/app/agents/skills/canvas_agent.md` — Canvas Agent persona skill file (created in Phase 18)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_agent_turn_stream()` in `router.py`: Complete SSE streaming loop with tool dispatch — Canvas Agent endpoint reuses this with canvas-specific persona and tools
- `pushSnapshot()` in flowStore: Undo history snapshot — called before `applyAgentDiff()` per STATE.md decision
- `serializeGraph()` / `deserializeGraph()`: Graph serialization already implemented — used for sending graph to agent and applying diffs back
- `IssuesPanel`: Collapsible panel below canvas inside ReactFlowProvider — pattern for chat panel positioning
- `CubeCatalog` sidebar: Left sidebar pattern with open/close state — chat panel mirrors on right side
- `AgentChatRequest` / `AgentSSEEvent` schemas: Existing request/response types for agent SSE endpoint
- Session management (`get_or_create_session`, `update_session`): Server-side session with TTL already works

### Established Patterns
- Zustand store for all canvas state — chat panel state (open/closed, mode, messages) should live in flowStore or a dedicated chatStore
- SSE via `sse_starlette` with typed events (text, tool_call, tool_result, done)
- Router-based organization — Canvas Agent tools go in `backend/app/agents/tools/`
- CSS variables for dark theme — chat panel follows existing glass/dark theme patterns

### Integration Points
- `EditorPage.tsx`: Add ChatPanel component alongside existing layout (right of canvas area)
- `Toolbar.tsx`: Add chat toggle button
- `flowStore.ts`: Add `applyAgentDiff()` action, possibly chat-related state (or separate store)
- `backend/app/agents/router.py`: The existing `/api/agent/chat` endpoint already handles persona-based routing — Canvas Agent is a persona, not a separate endpoint
- `backend/app/agents/tools/`: Add canvas-specific tool files (read_workflow_graph, propose_graph_diff, read_execution_errors, read_execution_results)

</code_context>

<specifics>
## Specific Ideas

- User wants the most proactive agent behavior: panel auto-opens in Fix mode when errors occur, with an initial diagnostic prompt
- Full graph sent every turn — the agent should never be "blind" to the current canvas state
- Results tool should make clear to the user that displayed results are capped at the store limit (not all execution results)
- One diff at a time keeps things safe and atomic — no complex multi-diff queuing
- Both Ctrl+Z undo and server reload available for discarding agent changes — belt and suspenders approach

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 20-canvas-agent*
*Context gathered: 2026-03-24*
