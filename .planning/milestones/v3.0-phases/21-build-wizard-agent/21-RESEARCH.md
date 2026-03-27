# Phase 21: Build Wizard Agent — Research

**Researched:** 2026-03-25
**Phase:** 21-build-wizard-agent
**Goal:** A new analyst with no existing workflow can use the wizard to describe their analysis idea conversationally, answer guided questions via clickable option cards, see a visual mini-graph preview, and have a complete validated workflow generated and saved — ready to run on the canvas.

## 1. Existing Infrastructure Inventory

### Backend Agent Layer (Phase 18 — ready to use)

| Component | File | What it provides |
|-----------|------|-----------------|
| Gemini client singleton | `backend/app/agents/client.py` | `get_gemini_client()` — async Gemini API access |
| SSE chat endpoint | `backend/app/agents/router.py` | `POST /api/agent/chat` with `_agent_turn_stream()` tool dispatch loop |
| Tool registry | `backend/app/agents/registry.py` | `@agent_tool` decorator, `get_gemini_tool_declarations()` |
| Tool dispatcher | `backend/app/agents/dispatcher.py` | `dispatch_tool()` with retry + ToolContext injection |
| ToolContext | `backend/app/agents/context.py` | Dataclass injected into every tool: `db_session`, `cube_registry`, `workflow_id`, `workflow_graph`, `execution_errors`, `execution_results` |
| Sessions | `backend/app/agents/sessions.py` | In-memory session dict with 30min TTL |
| Schemas | `backend/app/agents/schemas.py` | `AgentChatRequest`, `AgentSSEEvent`, `MissionContext` |
| Skills loader | `backend/app/agents/skills_loader.py` | `get_system_prompt(persona)` loads from `skills/` directory |
| History pruning | `backend/app/agents/context.py` | `prune_history()` at 50k token threshold |

### Cube Expert & Validation (Phase 19 — ready to use)

| Component | File | What it provides |
|-----------|------|-----------------|
| Catalog tools | `backend/app/agents/tools/catalog_tools.py` | `list_cubes_summary`, `get_cube_definition`, `find_cubes_for_task` |
| Validation | `backend/app/agents/validation.py` | `validate_graph(graph, cube_registry)` — returns `ValidationResponse` with issues |
| CubeExpert | `backend/app/agents/cube_expert.py` | Sub-agent for cube lookup reasoning |

### Chat UI (Phase 20 — reuse patterns)

| Component | File | What it provides |
|-----------|------|-----------------|
| ChatPanel | `frontend/src/components/Chat/ChatPanel.tsx` | Right sidebar shell with header, message list, input |
| MessageBubble | `frontend/src/components/Chat/MessageBubble.tsx` | User/agent message rendering |
| ChatInput | `frontend/src/components/Chat/ChatInput.tsx` | Text input with send button |
| DiffProposal | `frontend/src/components/Chat/DiffProposal.tsx` | Structured tool result rendering inline — model for option cards |
| MessageList | `frontend/src/components/Chat/MessageList.tsx` | Scrollable message container |
| ToolCallIndicator | `frontend/src/components/Chat/ToolCallIndicator.tsx` | Tool call display |
| SSE client | `frontend/src/api/agent.ts` | `streamAgentChat()` async generator |
| Agent types | `frontend/src/types/agent.ts` | `AgentSSEEvent`, `ChatMessage`, `AgentDiff` |

### Workflow API (existing)

| Component | File | What it provides |
|-----------|------|-----------------|
| Workflow CRUD | `backend/app/routers/workflows.py` | `POST /api/workflows` creates workflow, returns `WorkflowResponse` with `id` |
| WorkflowGraph schema | `backend/app/schemas/workflow.py` | `WorkflowGraph` (nodes + edges), `WorkflowNode`, `WorkflowEdge`, `WorkflowCreate` |
| Workflow model | `backend/app/models/workflow.py` | SQLAlchemy ORM with JSONB `graph_json` |

### Frontend Routing (existing)

| Component | File | What it provides |
|-----------|------|-----------------|
| Router | `frontend/src/main.tsx` | `createBrowserRouter` with `/`, `/workflow/new`, `/workflow/:id` |
| Dashboard | `frontend/src/pages/DashboardPage.tsx` | Workflow list + "New Workflow" button |
| FlowStore | `frontend/src/store/flowStore.ts` | Zustand store with `serializeGraph`, `deserializeGraph`, `loadWorkflow` |

## 2. Architecture Decisions (from STATE.md + CONTEXT.md)

### Locked Decisions

1. **D-01:** Dedicated `/wizard` route with `WizardPage` component — full-screen focused experience
2. **D-02:** Dashboard shows two buttons: "Build with Wizard" and "Blank Canvas"
3. **D-03:** After generation, workflow saved via `POST /api/workflows`, redirect to `/workflow/:id`
4. **D-04:** Conversational chat interface driven by LLM, NOT fixed multi-step form
5. **D-05:** Conversation starts with text input AND suggested mission type cards
6. **D-06:** LLM presents options via `present_options` tool — renders clickable cards inline
7. **D-07:** `present_options` has `multi_select` flag — LLM controls single vs multi-select
8. **D-08:** Every option card set includes free-text input fallback
9. **D-09:** Intent preview as visual mini-graph showing cube nodes and connections
10. **D-10:** "Adjust" continues conversation (no restart)
11. **D-11:** LLM calls `generate_workflow` tool → backend validates + saves → SSE `workflow_created` event → redirect
12. **D-12:** Auto-fix on validation failure (up to 2 retries), then show errors
13. **D-13:** Auto-name from mission description
14. **D-14:** Mission description + analysis intent saved to workflow metadata JSONB

### Model Selection

- Build Agent uses `gemini-2.5-pro` (reasoning depth) — per STATE.md key decision
- Canvas Agent uses `gemini-2.5-pro` — per router.py line 79

### Key Constraint: Persona-Based Routing

The existing `/api/agent/chat` endpoint routes by `persona` field in `AgentChatRequest`. The wizard can reuse this endpoint with `persona: "build_agent"`. The model selection in `_agent_turn_stream` needs to handle the build_agent persona → pro model.

## 3. Technical Analysis

### 3.1 Backend: Wizard Tools (3 new tools)

**Tool 1: `present_options`**

The LLM calls this to present structured choices to the analyst. The tool itself is a pass-through — it formats the options and returns them. The frontend renders them as clickable cards.

Schema design:
```python
@agent_tool(
    name="present_options",
    description="Present clickable option cards to the analyst. Use for structured choices during wizard flow.",
    parameters_schema={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question being asked"},
            "options": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["id", "title"],
                },
            },
            "multi_select": {"type": "boolean", "description": "Allow multiple selections"},
        },
        "required": ["question", "options"],
    },
)
```

The tool returns the options as-is — the actual selection happens client-side. When the user clicks a card, the selection is sent back as a regular chat message (e.g., "I selected: Squawk Analysis").

**Tool 2: `show_intent_preview`**

The LLM calls this when enough information has been gathered. Returns a structured graph preview that the frontend renders as a mini-graph.

Schema:
```python
@agent_tool(
    name="show_intent_preview",
    description="Show a visual preview of the planned workflow before building it.",
    parameters_schema={
        "type": "object",
        "properties": {
            "mission_name": {"type": "string"},
            "mission_description": {"type": "string"},
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "cube_id": {"type": "string"},
                        "label": {"type": "string"},
                        "key_params": {"type": "object"},
                    },
                    "required": ["cube_id", "label"],
                },
            },
            "connections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "from_cube": {"type": "string"},
                        "from_output": {"type": "string"},
                        "to_cube": {"type": "string"},
                        "to_input": {"type": "string"},
                    },
                    "required": ["from_cube", "to_cube"],
                },
            },
        },
        "required": ["mission_name", "nodes", "connections"],
    },
)
```

**Tool 3: `generate_workflow`**

The main generation tool. LLM produces the full WorkflowGraph JSON. Backend:
1. Validates with `validate_graph()`
2. If validation fails, returns errors to LLM for auto-fix (up to 2 retries)
3. If valid, creates workflow via `POST /api/workflows` logic (direct DB call)
4. Saves mission context to metadata JSONB
5. Returns `{workflow_id, workflow_name}` — frontend receives via SSE and redirects

Schema:
```python
@agent_tool(
    name="generate_workflow",
    description="Generate and save a complete workflow from the wizard conversation.",
    parameters_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Workflow name from mission"},
            "mission_description": {"type": "string"},
            "analysis_intent": {"type": "string"},
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "cube_id": {"type": "string"},
                        "position": {
                            "type": "object",
                            "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
                        },
                        "params": {"type": "object"},
                    },
                    "required": ["id", "cube_id", "position"],
                },
            },
            "edges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                        "sourceHandle": {"type": "string"},
                        "targetHandle": {"type": "string"},
                    },
                    "required": ["id", "source", "target"],
                },
            },
        },
        "required": ["name", "nodes", "edges"],
    },
)
```

### 3.2 Node Positioning Algorithm

Generated workflows need sensible auto-layout. Simple approach:
- Topological sort determines order
- Place nodes in columns by topological depth (x = depth * 300)
- Stack nodes at same depth vertically (y = index * 200)
- This gives a left-to-right flow matching the existing canvas convention

### 3.3 Frontend: WizardPage Component

The wizard page is a full-screen conversational UI. Key differences from ChatPanel:
- Full-screen (not sidebar)
- Has initial state with mission type cards + text input
- Renders option cards inline from `present_options` tool results
- Renders mini-graph preview from `show_intent_preview` tool results
- Has "Build This" / "Adjust" buttons on preview
- Redirects to `/workflow/:id` after generation

**Component structure:**
```
WizardPage
├── WizardHeader (brand + "Back to Dashboard" link)
├── WizardChat (central chat area — reuses message patterns)
│   ├── WizardWelcome (initial state: text input + mission type cards)
│   ├── MessageBubble (reusable from Phase 20)
│   ├── OptionCards (new — renders present_options tool results)
│   ├── MiniGraph (new — renders show_intent_preview tool results)
│   └── WizardInput (text input — similar to ChatInput)
└── (no sidebar, no toolbar, no canvas)
```

### 3.4 SSE Client Extension

The existing `streamAgentChat()` in `frontend/src/api/agent.ts` hardcodes `persona: 'canvas_agent'`. The wizard needs `persona: 'build_agent'`. Options:
- **Best:** Make persona a parameter of `streamAgentChat()` — minimal change, backwards compatible
- The wizard also doesn't need `workflow_graph`, `execution_errors`, `execution_results` — these can be null

### 3.5 New SSE Event Type: `workflow_created`

After `generate_workflow` succeeds, the backend needs to emit a special SSE event that the frontend intercepts to trigger redirect. This can be done by:
- Returning `{workflow_id, workflow_name, status: "created"}` from the tool
- Frontend detects `tool_result` with `name: "generate_workflow"` and `result.status === "created"` → triggers redirect

This avoids adding a new SSE event type — reuses existing `tool_result` event.

### 3.6 Dashboard Changes

Current dashboard has one "New Workflow" button. Change to two:
- "Build with Wizard" → navigates to `/wizard`
- "Blank Canvas" → navigates to `/workflow/new`

Minimal CSS change — add a second button next to existing one.

### 3.7 Build Agent Skill File

The existing `build_agent.md` is minimal (16 lines). Needs expansion with:
- Detailed conversation flow guidance
- When to call `list_cubes_summary` and `get_cube_definition`
- When to present options vs ask open questions
- When enough info has been gathered to show preview
- Graph generation rules (must call `get_cube_definition` for every cube before generating)
- Parameter filling strategy

### 3.8 Model Selection in Router

Current router selects model based on persona:
```python
model_name = settings.gemini_pro_model if persona == "canvas_agent" else settings.gemini_flash_model
```

Build agent also needs pro model. Update to:
```python
pro_personas = {"canvas_agent", "build_agent"}
model_name = settings.gemini_pro_model if persona in pro_personas else settings.gemini_flash_model
```

## 4. Risk Analysis

### Risk 1: LLM Hallucinating Cube Names/Parameters
**Mitigation:** Skill file instructs LLM to always call `get_cube_definition()` before referencing any cube in the graph. `generate_workflow` tool validates via `validate_graph()` before saving.

### Risk 2: Invalid Edge Connections
**Mitigation:** `validate_graph()` catches dangling handles, type mismatches, missing required params. Auto-retry feeds errors back to LLM (up to 2 attempts).

### Risk 3: Context Window Exhaustion
**Mitigation:** Existing `prune_history()` at 50k tokens. Wizard conversations are shorter than canvas agent sessions (3-5 questions vs ongoing editing).

### Risk 4: Mini-Graph Rendering Complexity
**Mitigation:** Use simple SVG with circles/rectangles + lines. No need for full React Flow — the preview is read-only and simplified.

## 5. Dependencies

### Python Packages
No new Python packages needed. All infrastructure exists.

### Frontend Packages
No new packages needed. React Router, Zustand, existing CSS patterns sufficient.

## 6. Testing Strategy

### Backend Tests
- Unit test for each wizard tool (`present_options`, `show_intent_preview`, `generate_workflow`)
- Integration test: `generate_workflow` with valid graph → workflow created in DB
- Integration test: `generate_workflow` with invalid graph → validation errors returned

### Frontend Tests
- Manual verification: wizard page renders, options clickable, preview shows, redirect works

## 7. Validation Architecture

### Requirement Coverage

| Requirement | Implementation |
|-------------|---------------|
| BUILD-01 | WizardPage with OptionCards component, present_options tool |
| BUILD-02 | Build Agent skill file drives 3-5 questions via present_options |
| BUILD-03 | generate_workflow tool produces full WorkflowGraph JSON |
| BUILD-04 | show_intent_preview tool + MiniGraph component |
| BUILD-05 | generate_workflow validates + saves + redirects to canvas |

### Verification Criteria
1. `/wizard` route loads WizardPage
2. Dashboard shows "Build with Wizard" and "Blank Canvas" buttons
3. Clicking mission type card sends message to build agent
4. Agent responds with option cards via present_options tool
5. Clicking option card sends selection as message
6. Agent shows mini-graph preview after gathering info
7. "Build This" triggers generate_workflow tool
8. Valid workflow saved, redirect to `/workflow/:id`
9. Invalid workflow triggers auto-fix, then error display
10. Mission context saved in workflow metadata

## RESEARCH COMPLETE
