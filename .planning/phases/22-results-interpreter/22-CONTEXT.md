# Phase 22: Results Interpreter - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

After a workflow executes, analysts can click "Interpret Results" on the selected cube's results and receive a streaming AI interpretation — grounded in their stated mission context (from the Build Wizard) or a cube-type-aware flight-analysis framing when no mission exists. A dedicated follow-up agent allows conversational drill-down into the interpretation with tool-calling access to fetch specific cube results.

</domain>

<decisions>
## Implementation Decisions

### Trigger & Placement
- **D-01:** "Interpret Results" button appears in the ResultsDrawer header, next to the existing "Close" button. Only visible when results are showing.
- **D-02:** Interpretation is manual only — analyst must click the button. No auto-trigger after execution. Keeps Gemini costs down and respects analyst autonomy.
- **D-03:** The button interprets the currently-selected cube's results (not the whole workflow). Analyst can switch cubes and interpret each independently.

### Interpretation Display
- **D-04:** Interpretation renders as a collapsible inline panel within the ResultsDrawer, positioned above the table/map area. Analyst sees interpretation alongside their data without navigating away.
- **D-05:** Interpretation streams in token-by-token via SSE (reuses Phase 18 infrastructure). Shows a loading indicator while streaming. This means the endpoint is SSE-based, NOT the sync `POST /api/agent/interpret` originally planned in STATE.md.
- **D-06:** The interpreter itself is one-shot (no multi-turn conversation). After the interpretation renders, a "Discuss results" link/button is shown below it.
- **D-07:** "Discuss results" opens a **dedicated follow-up agent** — a separate persona that receives the interpretation summary as context and has tool-calling access to fetch specific cube results on demand (e.g., `read_cube_results(cube_id)`). This is NOT the Canvas Agent — it's a focused results Q&A agent.

### Mission Context Depth
- **D-08:** When a workflow has mission context (created via Build Wizard), the interpreter references the mission intent AND compares results against it. E.g., "You were looking for squawk 7700 in Jordan FIR — 3 flights matched. 2 were emergency descents, 1 was a false alarm."
- **D-09:** When no mission context exists (blank canvas workflow), the interpreter uses **cube-type-aware framing** — tailored language based on which cube produced the results. Signal health cube → anomaly language, squawk filter → emergency code language, area filter → geographic language.

### Scope of Analysis
- **D-10:** The interpreter receives the selected cube's results PLUS a pipeline summary showing the upstream path (e.g., "alison_flights → squawk_filter → area_spatial_filter"). Enables references like "after filtering 200 flights down to 3."
- **D-11:** Interpretation is a flowing narrative summary — not bulleted findings or a structured report. Concise paragraph(s) that summarize the results in context.
- **D-12:** Empty results (0 rows) are handled by the interpreter — it explains possible reasons based on the cube type and parameters, with actionable guidance (e.g., "try expanding the date range or checking a different FIR").

### Claude's Discretion
- SSE event format for interpretation streaming (can reuse existing `text`/`done` event types)
- Interpretation panel CSS styling and collapse/expand animation
- Pipeline summary construction (how to walk the graph upstream from the selected cube)
- Follow-up agent persona details and skill file content
- `read_cube_results` tool implementation for the follow-up agent
- How the interpretation summary is passed to the follow-up agent (session context injection vs. system prompt)
- Loading indicator design during streaming

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Results Interpreter (RESULT-01, RESULT-02, RESULT-03) — requirement definitions
- `.planning/ROADMAP.md` §Phase 22 — success criteria SC-1 through SC-3

### Architecture Decisions
- `.planning/STATE.md` §Key Decisions (v3.0 Architecture) — locked decisions: SSE streaming, manual tool dispatch, server-side sessions, agent layer isolation, two-tier catalog
- `.planning/phases/18-agent-infrastructure/18-CONTEXT.md` — infrastructure decisions (SSE events, tool dispatch, sessions, context management)

### Phase 18 Infrastructure (built, ready to use)
- `backend/app/agents/router.py` — SSE chat endpoint, `_agent_turn_stream()` tool dispatch loop
- `backend/app/agents/client.py` — Gemini client singleton
- `backend/app/agents/registry.py` — `@agent_tool` decorator, tool declarations
- `backend/app/agents/dispatcher.py` — `dispatch_tool()` with ToolContext injection
- `backend/app/agents/context.py` — `ToolContext` dataclass, `prune_history()`
- `backend/app/agents/sessions.py` — session management (in-memory dict, 30min TTL)
- `backend/app/agents/schemas.py` — `AgentChatRequest`, `AgentSSEEvent` schemas
- `backend/app/agents/skills_loader.py` — skill file loading at startup

### Phase 19 Validation (built, ready to use)
- `backend/app/agents/validation.py` — `validate_graph()` for structural checks

### Phase 20 Canvas Agent (built, patterns to reference)
- `backend/app/agents/tools/canvas_tools.py` — `read_execution_results` tool (pattern for reading cube results)
- `frontend/src/components/Chat/` — chat UI components (MessageBubble, ChatInput patterns)
- `frontend/src/api/agent.ts` — agent API client with SSE support

### Phase 21 Build Wizard (built, mission context source)
- `backend/app/agents/tools/wizard_tools.py` — `generate_workflow` tool (saves mission to metadata JSONB)

### Results Display (built, integration target)
- `frontend/src/components/Results/ResultsDrawer.tsx` — drawer component, header area where button will be added
- `frontend/src/components/Results/ResultsTable.tsx` — table component
- `frontend/src/store/flowStore.ts` — `results`, `executionStatus`, `workflowId`, `selectedResultNodeId` state

### Existing Skill File
- `backend/app/agents/skills/results_interpreter.md` — existing skill file (basic, needs expansion)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_agent_turn_stream()` in `router.py`: Complete SSE streaming loop with tool dispatch — interpreter endpoint can reuse this with results-interpreter persona
- `read_execution_results` tool in `canvas_tools.py`: Already reads summarized results (row count, sample rows, columns) — pattern for building the interpretation context
- `ResultsDrawer` component: Has a header section with title + close button — interpretation button slots in naturally
- `agent.ts` API client: SSE streaming support already built for Canvas Agent chat — can be extended for interpret endpoint
- `MessageBubble` component: Pattern for rendering streamed text — may be reused for the interpretation panel

### Established Patterns
- SSE chat endpoint with typed events (text, tool_call, tool_result, done)
- Server-side sessions with 30min TTL
- Tool dispatch via `dispatch_tool()` with ToolContext injection
- Zustand store for execution state (`results`, `executionStatus`, `selectedResultNodeId`)
- Dark theme with CSS variables

### Integration Points
- `ResultsDrawer.tsx` header: Add "Interpret Results" button
- `ResultsDrawer.tsx` content: Add collapsible interpretation panel above table
- `backend/app/agents/router.py`: Add SSE interpretation endpoint
- `backend/app/agents/tools/`: Add interpretation tools (read pipeline summary, read cube results)
- `backend/app/agents/skills/results_interpreter.md`: Expand with cube-type-aware framing guidance
- `frontend/src/store/flowStore.ts`: Add interpretation state (loading, content, follow-up session)
- `frontend/src/api/agent.ts`: Add interpret API call

</code_context>

<specifics>
## Specific Ideas

- The follow-up agent is a dedicated persona (not Canvas Agent) because it needs the interpretation summary as grounding context and tool access to fetch specific cube results by ID
- Cube-type-aware framing means the skill file should include framing templates per cube category (signal health → anomaly language, squawk filter → emergency code language, area filter → geographic language, data source → collection scope language)
- Pipeline summary walks the graph upstream from the selected cube to show the data journey (which source, which filters, which analysis steps preceded)
- Empty results get LLM interpretation too — the interpreter explains possible reasons based on cube type and parameters, not just "no results found"

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 22-results-interpreter*
*Context gathered: 2026-03-26*
