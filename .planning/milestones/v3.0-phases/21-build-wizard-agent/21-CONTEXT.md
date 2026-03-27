# Phase 21: Build Wizard Agent - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

A new analyst with no existing workflow can use the wizard to describe their analysis idea in a conversational flow with an LLM, answer guided questions via clickable option cards (with free-text fallback), see a visual mini-graph preview of the planned workflow, and have a complete, validated workflow generated and saved — ready to run on the canvas without manual parameter editing.

</domain>

<decisions>
## Implementation Decisions

### Wizard Page & Navigation
- **D-01:** Dedicated `/wizard` route with a new `WizardPage` component. Full-screen focused experience, separate from the editor.
- **D-02:** Dashboard shows two buttons: "Build with Wizard" (routes to `/wizard`) and "Blank Canvas" (routes to `/workflow/new`). Decision happens on the dashboard, not inside the wizard.
- **D-03:** After generation, the workflow is saved via API (POST /api/workflows) and the analyst is redirected to `/workflow/:id` with the saved workflow loaded on the canvas.

### Conversational Flow (not fixed steps)
- **D-04:** The wizard is a **conversational chat interface** driven by the LLM, NOT a fixed multi-step form. The LLM asks clarifying questions, uses tools to present structured options, and drives the flow dynamically based on the analyst's idea.
- **D-05:** Conversation starts with both: a text input for typing analysis ideas freely AND suggested mission type cards below. Analyst can type freely or click a card to kickstart the conversation.
- **D-06:** LLM presents structured options mid-conversation via a `present_options` tool that renders clickable cards inline in the chat. Clicking a card sends the selection as a message back to the LLM.
- **D-07:** The `present_options` tool has a `multi_select` flag — LLM controls whether each question is single-select or multi-select (e.g., "pick filters" allows multi-select, "pick data source" is single-select).
- **D-08:** Every option card set also includes a free-text input — the analyst can always type a custom answer instead of picking a card. The LLM interprets the free text and continues.

### Intent Preview
- **D-09:** Intent preview renders as a **visual mini-graph** showing cube nodes and connections (simplified node graph, not full React Flow canvas). Displayed inline in the chat with "Build This" and "Adjust" buttons.
- **D-10:** Clicking "Adjust" continues the conversation — the LLM asks what to change, updates the plan, and shows a new preview. No restart.

### Generation & Delivery
- **D-11:** LLM calls a `generate_workflow` tool that produces the full WorkflowGraph JSON. Backend validates with `validate_graph()`, saves via POST /api/workflows, returns the workflow ID. Frontend receives a `workflow_created` SSE event and redirects to `/workflow/:id`.
- **D-12:** If validation fails, errors are fed back to the LLM as tool results. The LLM auto-fixes and retries (up to 2 attempts). If still failing, errors are shown to the analyst with a "Try again" option.
- **D-13:** The `generate_workflow` tool includes a `name` field derived from the mission description (e.g., "Squawk 7700 in Jordan FIR"). Analyst can rename later from the editor.
- **D-14:** Mission description and analysis intent from the conversation are saved to the workflow metadata JSONB — accessible to the Results Interpreter (Phase 22).

### Claude's Discretion
- Wizard page layout and styling (consistent with existing dark theme)
- Chat UI component reuse from Phase 20 ChatPanel vs. new wizard-specific chat component
- `present_options` tool schema structure (card title, description, icon fields)
- Mini-graph preview component implementation (SVG, canvas, or simplified React Flow)
- How the LLM determines when enough information has been gathered to show a preview
- Build Agent skill file content (conversation flow guidance, when to present options vs. ask open questions)
- Node positioning algorithm for the generated workflow graph (auto-layout)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture Decisions
- `.planning/STATE.md` §Key Decisions (v3.0 Architecture) — locked decisions: `gemini-2.5-pro` for Build Agent, clickable option cards, two-tier catalog, manual tool dispatch, mission context in JSONB, `validate_graph()` pre-delivery
- `.planning/REQUIREMENTS.md` §Build Agent (BUILD-01..05) — requirement definitions and success criteria
- `.planning/ROADMAP.md` §Phase 21 — success criteria SC-1 through SC-5

### Phase 18 Infrastructure (built, ready to use)
- `backend/app/agents/router.py` — SSE chat endpoint pattern, `_agent_turn_stream()` tool dispatch loop
- `backend/app/agents/client.py` — Gemini client singleton
- `backend/app/agents/registry.py` — `@agent_tool` decorator, `RegisteredTool`, `get_gemini_tool_declarations()`
- `backend/app/agents/dispatcher.py` — `dispatch_tool()` with retry and ToolContext injection
- `backend/app/agents/context.py` — `ToolContext` dataclass, `prune_history()`, `estimate_tokens()`
- `backend/app/agents/sessions.py` — session management (in-memory dict, 30min TTL)
- `backend/app/agents/schemas.py` — `AgentChatRequest`, `AgentSSEEvent` schemas

### Phase 19 Cube Expert & Validation (built, ready to use)
- `backend/app/agents/cube_expert.py` — CubeExpert sub-agent (internal, called by Build Agent for cube lookup)
- `backend/app/agents/tools/catalog_tools.py` — `list_cubes_summary`, `get_cube_definition`, `find_cubes_for_task`
- `backend/app/agents/validation.py` — `validate_graph()` for pre-delivery validation
- `backend/app/agents/skills/build_agent.md` — Build Agent persona skill file (exists, needs expansion)

### Phase 20 Chat UI (built, potential reuse)
- `frontend/src/components/Chat/ChatPanel.tsx` — chat panel with SSE streaming, message rendering
- `frontend/src/components/Chat/MessageBubble.tsx` — message bubble component
- `frontend/src/components/Chat/ChatInput.tsx` — chat input component
- `frontend/src/components/Chat/DiffProposal.tsx` — inline tool result rendering pattern (model for option cards)
- `frontend/src/api/agent.ts` — agent API client with SSE support

### Frontend Routing
- `frontend/src/main.tsx` — `createBrowserRouter` with existing routes (`/`, `/workflow/new`, `/workflow/:id`)
- `frontend/src/pages/DashboardPage.tsx` — dashboard with workflow list and "New Workflow" button
- `frontend/src/pages/EditorPage.tsx` — editor page layout

### Workflow API
- `backend/app/routers/workflows.py` — POST /api/workflows for creating workflows
- `backend/app/schemas/workflow.py` — `WorkflowGraph`, `WorkflowNode`, `WorkflowEdge` schemas
- `backend/app/models/workflow.py` — Workflow ORM model with JSONB metadata

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ChatPanel` + `MessageBubble` + `ChatInput` from Phase 20: Chat UI components that can be adapted or reused for the wizard conversation. The wizard chat has similar needs (SSE streaming, message rendering) but adds option cards and mini-graph preview.
- `DiffProposal` component: Pattern for rendering structured tool results inline in chat messages — model for option card and preview rendering.
- `_agent_turn_stream()` in `router.py`: Complete SSE streaming loop with tool dispatch — wizard endpoint reuses this with build-agent persona and tools.
- `validate_graph()`: Pre-delivery validation — called inside the `generate_workflow` tool before saving.
- `CubeExpert` sub-agent: Build Agent calls this internally to look up cubes during conversation.
- `@agent_tool` decorator: New wizard tools (`present_options`, `show_intent_preview`, `generate_workflow`) register the same way.

### Established Patterns
- SSE chat endpoint with typed events (text, tool_call, tool_result, done)
- Server-side sessions with 30min TTL
- Tool dispatch via `dispatch_tool()` with ToolContext injection
- React Router `createBrowserRouter` for page routing
- Dark theme with CSS variables and glass effects

### Integration Points
- `frontend/src/main.tsx`: Add `/wizard` route with new `WizardPage` component
- `frontend/src/pages/DashboardPage.tsx`: Change "New Workflow" button to show two options (Wizard / Blank Canvas)
- `backend/app/agents/router.py`: The existing `/api/agent/chat` endpoint handles persona-based routing — Build Agent is a persona, may reuse or add wizard-specific endpoint
- `backend/app/agents/tools/`: Add wizard-specific tool files (`present_options`, `show_intent_preview`, `generate_workflow`)
- `backend/app/agents/skills/build_agent.md`: Expand with conversation flow guidance

</code_context>

<specifics>
## Specific Ideas

- The wizard is fundamentally **conversational**, not a fixed form — the LLM drives the flow and decides what questions to ask based on the analyst's input
- Option cards are rendered inline in the chat via tool calls, not as separate UI regions
- Every option card set has a free-text input fallback — the analyst is never forced to only pick from cards
- Mini-graph preview is the preferred preview style — shows actual cube nodes and connections visually
- "Adjust" on preview continues the chat rather than restarting
- LLM auto-fixes validation failures (up to 2 retries) before surfacing errors to the analyst
- Workflow is auto-named from the mission description

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 21-build-wizard-agent*
*Context gathered: 2026-03-25*
