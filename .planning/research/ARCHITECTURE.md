# Architecture Research

**Domain:** AI Workflow Agents integrated into FastAPI + React visual dataflow builder
**Researched:** 2026-03-22
**Confidence:** HIGH (based on direct inspection of existing codebase + verified SDK patterns)

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React 18 + Vite)                         │
├──────────────────┬──────────────────────────────┬───────────────────────────┤
│  EditorPage      │  BuildWizardPage (NEW)        │  DashboardPage            │
│  ─────────────── │  ─────────────────────────── │                           │
│  FlowCanvas      │  WizardStep components        │  (unchanged)              │
│  CubeCatalog     │  WizardStore (Zustand, NEW)   │                           │
│  Toolbar         │                               │                           │
│  ResultsDrawer   │                               │                           │
│  ChatPanel (NEW) │                               │                           │
│  AgentOverlay    │                               │                           │
│  (NEW)           │                               │                           │
├──────────────────┴──────────────────────────────┴───────────────────────────┤
│                      Zustand Stores                                           │
│   flowStore (existing)   |  chatStore (NEW)  |  wizardStore (NEW)            │
├─────────────────────────────────────────────────────────────────────────────┤
│                      API Client Layer (existing src/api/)                     │
│           + src/api/agent.ts (NEW) — SSE streaming chat calls                │
└─────────────────────────────────────────────────────────────────────────────┘
                              │ HTTP + SSE
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND                                       │
├────────────────────┬────────────────────────────────────────────────────────┤
│  Existing Routers  │  NEW: app/routers/agent.py                              │
│  ─────────────────│  POST /api/agent/chat          → Canvas/Wizard SSE      │
│  /api/cubes        │  POST /api/agent/validate      → Validation Agent       │
│  /api/workflows    │  POST /api/agent/interpret     → Results Interpreter    │
├────────────────────┴────────────────────────────────────────────────────────┤
│                     NEW: app/agents/ package                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────────┐    │
│  │ base_agent  │  │ canvas_agent │  │ build_agent  │  │ cube_expert    │    │
│  │ (abstract)  │  │ (optimize/   │  │ (wizard      │  │ (sub-agent,    │    │
│  │             │  │  fix/general)│  │  workflow    │  │  called by     │    │
│  │             │  │              │  │  builder)    │  │  others)       │    │
│  └─────────────┘  └──────────────┘  └─────────────┘  └────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  app/agents/tools.py — Internal tool functions (pure Python)        │    │
│  │  • list_cubes_summary()     • get_cube_detail()                     │    │
│  │  • validate_workflow()      • add_node()  • remove_node()           │    │
│  │  • set_param()  • add_edge()  • remove_edge()  • clear_canvas()     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  app/agents/skills/ — System prompt files (plain text)              │    │
│  │  • system_brief.txt  • canvas_agent.txt  • build_agent.txt          │    │
│  │  • cube_expert.txt   • validation_agent.txt  • interpreter.txt      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────────────┤
│  Existing: engine/  cubes/  schemas/  models/  database/  config/            │
│  (NO changes to existing code — agent layer sits above it)                   │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                     Google Gemini API
                     (google-genai SDK, GA as of May 2025)
```

### Component Responsibilities

| Component | Responsibility | New or Existing |
|-----------|----------------|-----------------|
| `app/routers/agent.py` | HTTP entry points for all agent interactions; owns SSE streaming to client | NEW |
| `app/agents/base_agent.py` | Abstract base: Gemini client init, skill file loading, conversation history management, streaming loop | NEW |
| `app/agents/canvas_agent.py` | Canvas-mode agent: accepts mode (optimize/fix/general) + serialized graph; calls tools, streams diffs back | NEW |
| `app/agents/build_agent.py` | Wizard-mode agent: accepts step context; generates complete workflow graph on final step | NEW |
| `app/agents/cube_expert.py` | Sub-agent: two-tier catalog lookup only; called by canvas/build agents, never directly by router | NEW |
| `app/agents/tools.py` | Pure Python tool functions; take/return plain dicts; no LLM calls; called by agent tool dispatch | NEW |
| `app/agents/skills/` | Plain text system prompt files, one per agent persona | NEW |
| `src/api/agent.ts` | Frontend API client for agent endpoints; handles SSE stream parsing for chat | NEW |
| `src/store/chatStore.ts` | Zustand: message history, streaming state, active mode for ChatPanel | NEW |
| `src/store/wizardStore.ts` | Zustand: wizard step, collected answers, pending graph preview | NEW |
| `src/components/Agent/ChatPanel.tsx` | Collapsible side panel in EditorPage; renders message history + streaming token display | NEW |
| `src/pages/BuildWizardPage.tsx` | Separate route `/workflow/build`; step-by-step wizard with clickable option cards | NEW |
| `CubeRegistry` (existing) | Provides catalog data to tool functions via direct import | UNCHANGED |
| `WorkflowGraph` schema (existing) | Wire format agents produce — already matches what executor and canvas expect | UNCHANGED |
| `flowStore` (existing) | Receives graph mutations from agent via store actions (addCubeNode, addEdge, etc.) | MODIFIED: add `applyAgentDiff()` action |

---

## Recommended Project Structure

```
backend/app/
├── agents/                      # NEW package — all AI agent code
│   ├── __init__.py
│   ├── base_agent.py            # Abstract base class with Gemini client + streaming
│   ├── canvas_agent.py          # Canvas-mode agent (optimize / fix / general)
│   ├── build_agent.py           # Build wizard agent
│   ├── cube_expert.py           # Sub-agent: catalog lookup only
│   ├── validation_agent.py      # Structural validation (can be pure Python, LLM optional)
│   ├── interpreter_agent.py     # Results interpreter
│   ├── tools.py                 # All internal tool functions (pure Python)
│   └── skills/                  # System prompt text files
│       ├── system_brief.txt     # Domain context shared across all agents
│       ├── canvas_agent.txt
│       ├── build_agent.txt
│       ├── cube_expert.txt
│       ├── validation_agent.txt
│       └── interpreter_agent.txt
├── routers/
│   ├── agent.py                 # NEW: /api/agent/* endpoints
│   ├── cubes.py                 # UNCHANGED
│   └── workflows.py             # UNCHANGED
└── ... (rest unchanged)

frontend/src/
├── api/
│   ├── agent.ts                 # NEW: streaming chat client
│   └── ... (existing unchanged)
├── components/
│   ├── Agent/                   # NEW component group
│   │   ├── ChatPanel.tsx        # Collapsible chat sidebar
│   │   ├── ChatPanel.css
│   │   ├── ChatMessage.tsx      # Single message bubble (user / assistant / tool-call)
│   │   ├── ChatModeSelector.tsx # optimize / fix / general tabs
│   │   └── WizardPage/          # Alternatively: top-level pages/
│   │       ├── WizardStep.tsx
│   │       └── OptionCard.tsx
│   └── ... (existing unchanged)
├── pages/
│   ├── BuildWizardPage.tsx      # NEW route /workflow/build
│   ├── EditorPage.tsx           # MODIFIED: add <ChatPanel /> alongside canvas
│   └── ... (existing unchanged)
└── store/
    ├── chatStore.ts             # NEW
    ├── wizardStore.ts           # NEW
    ├── flowStore.ts             # MODIFIED: add applyAgentDiff() action
    └── ... (existing unchanged)
```

### Structure Rationale

- **`app/agents/` package:** Isolates all LLM code. The existing `routers/`, `engine/`, `cubes/` packages need zero changes. Agents import from existing packages (registry, schemas) but existing packages never import from agents — one-way dependency.
- **`skills/` subdirectory:** System prompts as plain `.txt` files (not Python strings) so they can be edited without touching code. Loaded once at agent init.
- **`tools.py` as a flat module:** All tool functions in one file at first. They call existing engine/registry code directly — no HTTP round-trips. Split into submodules only if the file exceeds ~400 lines.
- **`src/components/Agent/`:** Keeps agent UI components grouped. ChatPanel is a sibling of the canvas area, not inside FlowCanvas, to avoid React Flow event capture conflicts.
- **`applyAgentDiff()` on flowStore:** Single new action that takes an `AgentDiff` (list of typed mutations) and applies them atomically. Keeps agent-driven mutations on the same code path as user-driven mutations (pushSnapshot, isDirty, etc.).

---

## Architectural Patterns

### Pattern 1: Tool Dispatch via Python Dict (not LLM function-calling protocol)

**What:** Agents interpret LLM output that contains `<tool>name</tool><args>{...}</args>` XML tags (or a simple JSON envelope), then call the corresponding Python function directly. No LangChain, no framework.

**When to use:** When you have a small, stable tool set (8-12 functions) and want zero framework overhead. Gemini also supports native function calling declarations — either approach works, but the manual dispatch is simpler to debug.

**Trade-offs:** Pro: explicit, no magic, easy to test. Con: must parse LLM output yourself (but Gemini's function-call response format is clean JSON).

**Recommended approach:** Use Gemini's native function calling (`tools=` parameter), which returns structured `FunctionCall` objects instead of requiring XML parsing. The agent receives a `FunctionCall`, dispatches to `tools.py`, injects the result back as `FunctionResponse`, then continues the conversation.

```python
# app/agents/tools.py
def list_cubes_summary() -> list[dict]:
    """Returns [{cube_id, name, category, description}] for all registered cubes."""
    return [
        {"cube_id": c.cube_id, "name": c.name,
         "category": c.category, "description": c.description}
        for c in registry.all()
    ]

def get_cube_detail(cube_id: str) -> dict | None:
    """Returns full CubeDefinition dict for a specific cube_id."""
    cube = registry.get(cube_id)
    return cube.definition.model_dump() if cube else None

def build_workflow_graph(nodes: list[dict], edges: list[dict]) -> dict:
    """Validates and returns a WorkflowGraph-compatible dict. Raises on invalid."""
    graph = WorkflowGraph.model_validate({"nodes": nodes, "edges": edges})
    return graph.model_dump()
```

### Pattern 2: Stateless Agent Endpoints with Client-Side History

**What:** Every `/api/agent/chat` request carries the full conversation history in the request body. The backend is stateless — no server-side session. The frontend (chatStore) owns the history.

**When to use:** Always for this project. No auth, single user per workflow, history fits in context window (Gemini 1.5 Pro: 1M tokens; typical workflow chat: < 20K tokens).

**Trade-offs:** Pro: no server-side session storage, trivially scalable, simple to implement. Con: request payload grows with conversation length. Mitigate by capping history at last N turns (20 turns recommended) before sending.

```python
# app/routers/agent.py
class ChatRequest(BaseModel):
    mode: Literal["optimize", "fix", "general", "build"]
    graph: WorkflowGraph | None = None        # current canvas state
    history: list[dict]                        # [{role, parts}] — from client
    message: str                               # latest user message
    execution_results: dict | None = None      # for interpreter mode

@router.post("/api/agent/chat")
async def chat(body: ChatRequest) -> EventSourceResponse:
    agent = CanvasAgent(mode=body.mode)
    return EventSourceResponse(
        agent.stream(body.message, body.history, body.graph, body.execution_results)
    )
```

### Pattern 3: Sub-Agent as Direct Python Call (not HTTP)

**What:** The CubeExpert sub-agent is instantiated and called as a plain Python object from within CanvasAgent or BuildAgent — not via an HTTP endpoint.

**When to use:** When the sub-agent is always subordinate, never user-facing, and lives in the same process. Avoids latency of an HTTP round-trip and simplifies error handling.

**Trade-offs:** Pro: zero overhead, shared process, simpler stack traces. Con: tight coupling between orchestrator and sub-agent (acceptable here since CubeExpert is a stable, bounded component).

```python
# app/agents/canvas_agent.py
class CanvasAgent(BaseAgent):
    def __init__(self, mode: str):
        super().__init__(skill_file="canvas_agent.txt")
        self._cube_expert = CubeExpert()   # instantiated here, not injected

    async def _handle_tool_call(self, fn_call) -> str:
        if fn_call.name == "find_cubes_for_task":
            return await self._cube_expert.find(fn_call.args["task"])
        return await dispatch_tool(fn_call)   # route to tools.py
```

### Pattern 4: Agent Diff Applied to Zustand Store

**What:** When an agent wants to modify the canvas, it returns a structured diff (`AgentDiff`) — a list of typed mutations (`add_node`, `remove_node`, `set_param`, `add_edge`). The frontend applies this through a single `applyAgentDiff()` action on the flowStore.

**When to use:** Always for canvas mutations from agents. Never have the agent return a raw WorkflowGraph and replace the entire canvas — this loses undo history and confuses the user.

**Trade-offs:** Pro: preserves undo/redo stack, marks isDirty correctly, keeps mutations on the same code path as user interactions. Con: requires defining an AgentDiff type contract.

```typescript
// src/store/flowStore.ts — new action
applyAgentDiff: (diff: AgentDiff) => {
  get().pushSnapshot();   // enables Ctrl+Z to undo agent changes
  for (const op of diff.operations) {
    if (op.type === 'add_node')    get().addCubeNode(op.cube_id, op.position);
    if (op.type === 'remove_node') get().removeNode(op.node_id);
    if (op.type === 'set_param')   get().updateNodeParam(op.node_id, op.param, op.value);
    // ...
  }
  set({ isDirty: true });
}
```

### Pattern 5: SSE for Agent Streaming (reuses existing sse-starlette)

**What:** Agent responses stream as SSE events — same mechanism as workflow execution. Text tokens arrive as `data: {"type":"token","content":"..."}` events. Tool calls arrive as `data: {"type":"tool_call","name":"..."}` events. A final `data: {"type":"diff","operations":[...]}` event carries canvas mutations.

**When to use:** All agent chat interactions. The existing `EventSourceResponse` from `sse-starlette` handles this — same import used in `routers/workflows.py`.

**Trade-offs:** Pro: reuses infrastructure, nginx-compatible (same `proxy_buffering off` config), no new dependencies. Con: SSE is one-way; the client cannot interrupt mid-stream (acceptable for chat).

---

## Data Flow

### Canvas Agent Chat Flow

```
User types message in ChatPanel
    ↓
chatStore.sendMessage(message, mode)
    ↓
api/agent.ts: POST /api/agent/chat (with history + serialized graph)
    ↓ SSE stream opens
app/routers/agent.py: ChatRequest validated
    ↓
CanvasAgent.stream(message, history, graph)
    ↓
Gemini API call (with system prompt + tools declared)
    ↓
[token stream] → SSE "token" events → chatStore.appendToken()
    ↓
[FunctionCall] → tools.py dispatch → result injected back
    ↓
[AgentDiff] → SSE "diff" event → flowStore.applyAgentDiff()
    ↓ stream closes
chatStore.finalizeMessage()
```

### Build Wizard Flow

```
User lands on /workflow/build
    ↓
BuildWizardPage renders Step 1 (mission type)
    ↓
User clicks option card → wizardStore.setAnswer(step, answer)
    ↓ (after each step)
api/agent.ts: POST /api/agent/chat (mode="build", history of choices)
    ↓ SSE
BuildAgent streams next question OR final workflow
    ↓ (final step)
SSE "diff" event with complete workflow graph
    ↓
flowStore.applyAgentDiff() populates canvas
    ↓
React Router navigates to /workflow/new (canvas now pre-populated)
```

### Validation Agent Flow (synchronous, no streaming)

```
User clicks Run
    ↓
Toolbar triggers validation BEFORE calling existing run SSE
    ↓
POST /api/agent/validate (graph only, no history)
    ↓
validation_agent.py runs structural checks (pure Python, no LLM)
    ↓
Returns ValidationResult: {valid: bool, issues: [{node_id, severity, message}]}
    ↓
If issues: show inline warnings on CubeNode (existing status indicator mechanism)
If valid: proceed to existing workflow execution SSE
```

### State Management

```
chatStore
    ├── messages: ChatMessage[]      (streamed in real-time)
    ├── isStreaming: boolean
    ├── activeMode: "optimize"|"fix"|"general"
    └── sendMessage() → calls api/agent.ts, pipes SSE to store

wizardStore
    ├── currentStep: number
    ├── answers: Record<step, string>
    ├── isStreaming: boolean
    └── submitStep() → calls api/agent.ts, advances step or finalizes

flowStore (existing + new action)
    └── applyAgentDiff(diff: AgentDiff) → NEW action
```

---

## Integration Points

### New vs. Existing: What Changes

| Component | Status | Change Description |
|-----------|--------|--------------------|
| `app/routers/agent.py` | NEW | Entirely new file; registered in `main.py` with `app.include_router(agent_router)` |
| `app/main.py` | MODIFIED | Add `from app.routers.agent import router as agent_router` + `app.include_router(agent_router)` |
| `app/config.py` | MODIFIED | Add `GEMINI_API_KEY: str` to Settings (load from `.env`) |
| `pyproject.toml` | MODIFIED | Add `google-genai>=1.0.0` dependency |
| `app/engine/registry.py` | UNCHANGED | Tool functions import `registry` directly |
| `app/schemas/workflow.py` | UNCHANGED | `WorkflowGraph` is the wire format agents produce |
| `frontend/src/main.tsx` | MODIFIED | Add `/workflow/build` route pointing to BuildWizardPage |
| `frontend/src/pages/EditorPage.tsx` | MODIFIED | Add `<ChatPanel />` alongside the canvas area |
| `frontend/src/store/flowStore.ts` | MODIFIED | Add `applyAgentDiff()` action and `AgentDiff` type |
| All other existing files | UNCHANGED | No modifications required |

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Google Gemini API | `google-genai` Python SDK (GA, May 2025). Use `client.aio.models.generate_content_stream()` for async streaming. | Replace deprecated `google-generativeai`; new package is `google-genai`. API key from env. |
| PostgreSQL (existing) | UNCHANGED | Agents never query the DB directly — they call tool functions which may call existing cube logic |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `agent.py` router ↔ `canvas_agent.py` | Direct Python instantiation | Agents are not FastAPI dependencies; instantiated per-request |
| `canvas_agent.py` ↔ `cube_expert.py` | Direct Python instantiation (sub-agent pattern) | CubeExpert is never exposed as an HTTP endpoint |
| `agents/tools.py` ↔ `engine/registry.py` | Direct import: `from app.engine.registry import registry` | One-way dependency; registry never imports agents |
| `agents/tools.py` ↔ `schemas/workflow.py` | Direct import for validation | AgentDiff operations validate against existing WorkflowGraph schema |
| Frontend `chatStore` ↔ `flowStore` | Both are Zustand stores; `chatStore.onDiff()` calls `flowStore.applyAgentDiff()` directly | No React context needed; cross-store calls via `useFlowStore.getState()` |
| Frontend `ChatPanel` ↔ `FlowCanvas` | No direct coupling | ChatPanel is a sibling in EditorPage layout, not nested inside ReactFlowProvider |

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-5 concurrent users | Current design: stateless, in-process agents. No changes needed. |
| 10-50 concurrent users | Gemini API rate limits become relevant. Add per-IP request queuing in the router. Gemini's async client handles concurrent requests well. |
| 100+ concurrent users | Server-side conversation history storage (Redis) replaces client-carried history. Agent endpoints move to a separate process/service. |

### Scaling Priorities

1. **First bottleneck:** Gemini API rate limits (requests/minute per project). Fix with exponential backoff + optional queue.
2. **Second bottleneck:** Large conversation histories in request bodies. Fix with server-side session store (Redis) at ~50 concurrent users.

---

## Anti-Patterns

### Anti-Pattern 1: Agent Router Calling Workflow Execution

**What people do:** Have the Build Agent trigger `POST /api/workflows/{id}/run` to validate the workflow it created.

**Why it's wrong:** Creates a recursive HTTP call (router calling router within the same process), complicates error handling, and the Validation Agent covers this use case with direct Python calls.

**Do this instead:** The Build Agent calls `tools.validate_workflow(graph)` directly. The router never calls other routers.

### Anti-Pattern 2: Replacing Canvas State Instead of Diffing

**What people do:** Agent returns a complete new WorkflowGraph; frontend does `flowStore.setState({ nodes: newNodes, edges: newEdges })`.

**Why it's wrong:** Destroys the undo/redo history stack, loses user's manual position adjustments, and makes it impossible to undo agent changes. Users lose trust quickly.

**Do this instead:** Agent returns `AgentDiff` (typed mutation list). Frontend applies via `applyAgentDiff()` which calls `pushSnapshot()` first.

### Anti-Pattern 3: Storing Conversation History Server-Side Per Request

**What people do:** Generate a session ID, store history in a dict or Redis, have client send only the session ID.

**Why it's wrong:** Adds stateful infrastructure for a feature that doesn't need it. Histories are small (< 20K tokens for typical chat). Client-carried history is simpler, more debuggable, and trivially scalable.

**Do this instead:** Client sends `history: [{role, parts}]` in every request. Server truncates to last 20 turns before sending to Gemini.

### Anti-Pattern 4: Using `google-generativeai` (Deprecated)

**What people do:** `pip install google-generativeai` (old SDK, familiar from training data).

**Why it's wrong:** Deprecated; support ended November 30, 2025. Will not receive bug fixes or new model support.

**Do this instead:** `pip install google-genai` (new unified SDK, GA May 2025). The async API is `client.aio.models.generate_content_stream(...)`.

### Anti-Pattern 5: Building LangChain/LlamaIndex into This Project

**What people do:** Add a full orchestration framework because "that's how you do agents."

**Why it's wrong:** The tool set is small (< 15 functions), fixed, and internal. Framework overhead (abstraction layers, prompt templates, chain of thought wrappers) adds complexity without benefit. When the LLM misbehaves, you want direct access to the prompt and tool dispatch — not 4 layers of framework abstraction.

**Do this instead:** Direct Gemini SDK calls with Gemini's native function calling. Tool dispatch is a 20-line Python switch. Total agent infrastructure: ~500 lines of clear, debuggable Python.

---

## Build Order (Dependency-Aware)

This ordering ensures each step is independently testable before the next builds on it.

| Order | Component | Depends On | Notes |
|-------|-----------|------------|-------|
| 1 | `app/agents/skills/` text files + `app/config.py` GEMINI_API_KEY | Nothing | Zero-risk, sets up prerequisites |
| 2 | `app/agents/tools.py` | Existing registry + schemas | Pure Python, fully testable without LLM |
| 3 | `app/agents/base_agent.py` | `google-genai` SDK, skills files | Core streaming loop; test with a simple ping prompt |
| 4 | `app/agents/cube_expert.py` | base_agent + tools | Sub-agent; test independently with catalog queries |
| 5 | `app/agents/validation_agent.py` | tools.py only (no LLM needed) | Purely structural checks; fastest to ship |
| 6 | `app/routers/agent.py` + main.py registration | All agents | Wire agents to HTTP; integration test with curl/httpx |
| 7 | `src/api/agent.ts` + `chatStore.ts` | router/agent endpoint | Frontend SSE client + store |
| 8 | `src/components/Agent/ChatPanel.tsx` | chatStore, flowStore.applyAgentDiff | UI; wire to EditorPage |
| 9 | `app/agents/canvas_agent.py` | base_agent + cube_expert + tools | Full canvas agent with tool dispatch |
| 10 | `flowStore.applyAgentDiff()` | Existing flowStore | New store action; enables canvas mutations from chat |
| 11 | `app/agents/build_agent.py` | base_agent + cube_expert | Build wizard agent |
| 12 | `src/store/wizardStore.ts` + `BuildWizardPage.tsx` | build_agent endpoint | Wizard UI and route |
| 13 | `app/agents/interpreter_agent.py` | base_agent | Results interpreter; needs real execution results to test |

---

## Sources

- [google-genai Python SDK (GitHub)](https://github.com/googleapis/python-genai) — MEDIUM confidence (official repo, GA May 2025)
- [Google Gen AI SDK documentation](https://googleapis.github.io/python-genai/) — MEDIUM confidence
- [google-generativeai deprecation notice](https://github.com/google-gemini/deprecated-generative-ai-python) — HIGH confidence (official deprecation)
- [Multi-agent orchestration patterns (DEV Community)](https://dev.to/nebulagg/multi-agent-orchestration-a-guide-to-patterns-that-work-1h81) — LOW confidence (community, used for pattern validation only)
- [LLM tool calling patterns (fast.io)](https://fast.io/resources/llm-tool-calling/) — LOW confidence (used for validation)
- Existing codebase inspection — HIGH confidence (direct read of `engine/registry.py`, `engine/executor.py`, `routers/workflows.py`, `store/flowStore.ts`, `pages/EditorPage.tsx`, `schemas/cube.py`, `pyproject.toml`)

---

*Architecture research for: AI Workflow Agents integration into 12-flow (FastAPI + React visual dataflow builder)*
*Researched: 2026-03-22*
