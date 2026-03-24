# Phase 20: Canvas Agent - Research

**Researched:** 2026-03-24
**Domain:** AI agent chat panel, React sidebar layout, Zustand atomic state mutations, SSE streaming, Gemini tool dispatch
**Confidence:** HIGH — codebase is the primary source; all patterns verified by direct file inspection

## Summary

Phase 20 builds the Canvas Agent: a right-sidebar chat panel in the editor that lets analysts describe workflow changes in natural language and see them applied atomically to the canvas. The backend infrastructure from Phases 18–19 is complete and reusable with minimal extension. The frontend is the larger body of work: ~8 new React components, modifications to EditorPage layout, Toolbar, flowStore, and the agent API client.

The key technical challenge is `applyAgentDiff()` — the Zustand action that atomically merges agent-proposed node/edge/parameter changes into React Flow state while calling `pushSnapshot()` first for undo support. The diff schema, atomic update implementation, and the SSE event rendering pipeline are the highest-risk items.

The backend work is lower risk: add four new `@agent_tool`-decorated functions following the identical pattern already used in `catalog_tools.py`. The existing `POST /api/agent/chat` endpoint, `_agent_turn_stream()` loop, session management, and `ToolContext` are all reused without modification.

**Primary recommendation:** Implement in three logical waves — (1) backend canvas tools, (2) flowStore additions + `applyAgentDiff()`, (3) ChatPanel UI components wired to the agent SSE endpoint.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Right sidebar panel in the editor. CubeCatalog stays on the left, chat panel on the right, canvas in the middle. Both sidebars can be open simultaneously — canvas shrinks between them.
**D-02:** Panel is resizable via a drag handle on its left edge. Default width ~320px.
**D-03:** Toggled via a toolbar button (chat icon in the Toolbar, next to Run/Save) AND a keyboard shortcut (Ctrl+Shift+A). Button may show a badge when agent has suggestions.
**D-04:** Panel auto-opens in Fix mode when a workflow execution finishes with errors.

**D-05:** Three-segment toggle control at the top of the chat panel header: Optimize | Fix | General. Always visible, one click to switch. The active segment is the mode badge.
**D-06:** Fix mode auto-activates (and panel auto-opens) when execution errors occur. Initial prompt: "I see errors in [cube] — want me to diagnose?"
**D-07:** Shared conversation history across all three modes. Switching modes changes the system prompt context sent to Gemini but does NOT clear the chat. One session ID per conversation, not per mode.

**D-08:** Agent proposes changes via inline text summary in the chat — structured list of additions, removals, modifications with Apply/Reject buttons. No visual canvas preview.
**D-09:** One diff at a time. Agent proposes one atomic set, user accepts or rejects, then agent can propose another.
**D-10:** On Apply: `pushSnapshot()` called first, then `applyAgentDiff()` executes the atomic canvas mutation. "Discard Agent Changes" reloads last saved workflow from server. Both Ctrl+Z undo and server reload available.
**D-11:** `propose_graph_diff` tool output includes structural changes (add/remove nodes, add/remove edges) AND parameter value updates on existing nodes.

**D-12:** Canvas Agent has four tools: `read_workflow_graph`, `propose_graph_diff`, `read_execution_errors`, `read_execution_results`.
**D-13:** Full workflow graph is serialized into the context of every Gemini request.
**D-14:** Canvas Agent uses `gemini-2.5-flash` model. Cube Expert sub-agent called internally when needed.

### Claude's Discretion

- Chat panel open/close animation style and CSS implementation
- Drag handle resize implementation details
- Keyboard shortcut key binding (Ctrl+Shift+A suggested but flexible)
- SSE event rendering in chat messages (text streaming, tool call indicators, thinking display)
- `propose_graph_diff` JSON schema structure (as long as it supports add/remove nodes, add/remove edges, update params)
- How the "initial prompt" in Fix mode auto-open is generated (pre-written template vs. Gemini call)
- Chat input component design (textarea, send button, Enter behavior)
- Message bubble styling and agent/user visual distinction

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CANVAS-01 | Chat panel UI component integrated into editor page | Layout contract in 20-UI-SPEC.md; mirrors CubeCatalog pattern on right side of `.app__body` flex container |
| CANVAS-02 | Mode switching (optimize / error-fix / general) with visible mode indicator | Three-segment ModeToggle component; active segment uses `var(--color-accent)` background; shares session per D-07 |
| CANVAS-03 | Canvas context — agent reads current workflow graph state | `read_workflow_graph` tool + full graph serialized into every Gemini request body per D-13; uses existing `serializeGraph()` |
| CANVAS-04 | Optimize mode — suggest faster/simpler cube configurations | System prompt context injection via mode; agent calls existing catalog tools + proposes diff |
| CANVAS-05 | Error-fix mode — read cube errors from last run, diagnose pipeline failures | `read_execution_errors` tool reads from `executionStatus` in flowStore (already populated by workflow SSE stream); auto-open panel on error |
| CANVAS-06 | General mode — find cubes, suggest edits, answer questions | General persona mode; agent uses existing catalog tools (list_cubes_summary, get_cube_definition, find_cubes_for_task) |
| CANVAS-07 | `applyAgentDiff()` Zustand action for atomic canvas updates with snapshot | Calls `pushSnapshot()` first; batch-sets nodes+edges+params in single `set()` call; `deserializeGraph()` handles cubeDef lookup |

</phase_requirements>

---

## Standard Stack

### Core (all already in use — no new installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@xyflow/react` | existing | React Flow canvas nodes/edges | Already project standard; `applyNodeChanges`/`applyEdgeChanges` for atomic updates |
| `zustand` | existing | State management | `flowStore.ts` already owns all canvas state; chat state extends same store or sibling |
| `sse_starlette` | existing | Backend SSE streaming | Already used in `router.py` for agent chat |
| `google-genai>=1.68.0` | existing | Gemini API client | v3.0 architecture decision; `gemini-2.5-flash` for Canvas Agent |
| `pydantic` | existing | Backend schemas | All request/response models |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sonner` | existing | Toast notifications | Confirm "Changes applied to canvas" — already imported in EditorPage |
| `crypto.randomUUID()` | browser built-in | Node ID generation in `applyAgentDiff` | Same pattern as `addCubeNode` |

**Installation:** No new packages required for this phase.

---

## Architecture Patterns

### Recommended Project Structure

```
backend/app/agents/tools/
├── catalog_tools.py         # existing — list_cubes, get_cube_def, find_cubes
└── canvas_tools.py          # NEW — read_workflow_graph, propose_graph_diff,
                             #        read_execution_errors, read_execution_results

backend/app/agents/skills/
├── canvas_agent.md          # existing — extend with mode instructions

frontend/src/components/Chat/
├── ChatPanel.tsx            # NEW — right sidebar shell with drag handle
├── ChatPanel.css            # NEW — panel layout, left-edge gradient, resize
├── ModeToggle.tsx           # NEW — three-segment Optimize/Fix/General
├── MessageList.tsx          # NEW — scrollable message thread
├── MessageBubble.tsx        # NEW — single message with streaming cursor
├── DiffProposal.tsx         # NEW — structured diff with Apply/Reject buttons
├── ChatInput.tsx            # NEW — textarea + send button
└── ToolCallIndicator.tsx    # NEW — inline spinner during tool dispatch

frontend/src/api/
└── agent.ts                 # MODIFIED — add streamAgentChat() SSE function

frontend/src/store/
└── flowStore.ts             # MODIFIED — add applyAgentDiff(), chat panel state
```

### Pattern 1: `@agent_tool` Decorator for New Canvas Tools

**What:** Register canvas-specific tool functions using the existing decorator pattern in `registry.py`. The dispatcher automatically picks up all registered tools.

**When to use:** All four canvas tools (`read_workflow_graph`, `propose_graph_diff`, `read_execution_errors`, `read_execution_results`).

```python
# Source: backend/app/agents/tools/catalog_tools.py (existing pattern)
from app.agents.context import ToolContext
from app.agents.registry import agent_tool

@agent_tool(
    name="read_workflow_graph",
    description="Return the current workflow graph state (nodes, edges, parameter values). The graph is also included in every request context.",
    parameters_schema={"type": "object", "properties": {}},
)
async def read_workflow_graph(ctx: ToolContext) -> dict:
    # ctx.workflow_id is available — but graph comes from request body context injection
    # This tool re-reads from context; workflow_graph injected in tool_context extension
    ...
```

**Key insight:** `ToolContext` currently carries `db_session`, `cube_registry`, and `workflow_id`. The graph payload needs to be passed at request time (per D-13). Extend `ToolContext` to optionally carry `workflow_graph: dict | None = None` and `execution_errors: dict | None = None`.

### Pattern 2: `applyAgentDiff()` Zustand Action

**What:** Atomic canvas mutation from agent diff payload. Calls `pushSnapshot()` first, then applies all changes in a single `set()` call.

**When to use:** When user clicks "Apply Changes" in the DiffProposal component.

```typescript
// Source: flowStore.ts — extending existing pushSnapshot() + set() pattern
applyAgentDiff: (diff: AgentDiff) => {
  get().pushSnapshot();           // save pre-apply state for Ctrl+Z
  const { nodes, edges, catalog } = get();

  // Process node additions
  const addedNodes: CubeFlowNode[] = (diff.add_nodes ?? []).map(n => {
    const cubeDef = catalog.find(c => c.cube_id === n.cube_id);
    // cubeDef guaranteed by agent (per skill rules); warn and skip if absent
    if (!cubeDef) { console.warn(...); return null; }
    return { id: n.id ?? crypto.randomUUID(), type: 'cube', position: n.position, data: { cube_id: n.cube_id, cubeDef, params: n.params ?? {} } };
  }).filter(Boolean) as CubeFlowNode[];

  // Process node removals
  const removeIds = new Set(diff.remove_node_ids ?? []);

  // Process param updates on existing nodes
  const updatedNodes = nodes
    .filter(n => !removeIds.has(n.id))
    .map(n => {
      const update = (diff.update_params ?? []).find(u => u.node_id === n.id);
      if (!update) return n;
      return { ...n, data: { ...n.data, params: { ...n.data.params, ...update.params } } };
    });

  // Process edge additions/removals
  const removeEdgeIds = new Set(diff.remove_edge_ids ?? []);
  const keptEdges = edges.filter(e => !removeEdgeIds.has(e.id));
  const addedEdges: Edge[] = (diff.add_edges ?? []).map(e => ({
    id: e.id ?? crypto.randomUUID(), source: e.source, target: e.target,
    sourceHandle: e.source_handle ?? null, targetHandle: e.target_handle ?? null,
    type: 'straight',
  }));

  set({
    nodes: [...updatedNodes, ...addedNodes],
    edges: [...keptEdges, ...addedEdges],
    isDirty: true,
  });
},
```

### Pattern 3: SSE Client-Side Streaming for Chat

**What:** EventSource-like SSE consumer for the agent chat endpoint. The existing workflow SSE hook (`useWorkflowSSE`) is the model. Agent chat uses `fetch` + `ReadableStream` for POST requests (EventSource only supports GET).

**When to use:** ChatInput sends message → calls `streamAgentChat()` → renders events into MessageList.

```typescript
// Source: pattern derived from existing useWorkflowSSE.ts
// agent.ts — add alongside existing validateWorkflow()
export async function* streamAgentChat(
  message: string,
  sessionId: string | null,
  workflowId: string | null,
  workflowGraph: WorkflowGraph | null,
  mode: AgentMode,
): AsyncGenerator<AgentSSEEvent> {
  const response = await fetch('/api/agent/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, persona: 'canvas_agent', workflow_id: workflowId, workflow_graph: workflowGraph, mode }),
  });
  // parse SSE stream line-by-line
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      if (line.startsWith('data:')) {
        try { yield JSON.parse(line.slice(5).trim()); } catch { /* skip malformed */ }
      }
    }
  }
}
```

### Pattern 4: `propose_graph_diff` JSON Schema

**What:** The structured diff payload returned by the agent tool and rendered by `DiffProposal.tsx`.

```typescript
// Flat schema — avoids Gemini nested $defs rejection (per registry.py note)
interface AgentDiff {
  add_nodes?: Array<{ id?: string; cube_id: string; position: { x: number; y: number }; params?: Record<string, unknown>; label?: string }>;
  remove_node_ids?: string[];
  update_params?: Array<{ node_id: string; params: Record<string, unknown> }>;
  add_edges?: Array<{ id?: string; source: string; target: string; source_handle?: string; target_handle?: string }>;
  remove_edge_ids?: string[];
  summary?: string;  // human-readable summary for DiffProposal header
}
```

The tool returns this as a dict. The `summary` field is displayed as the "Proposed Changes" header text in the DiffProposal block.

### Pattern 5: `ToolContext` Extension for Canvas Tools

**What:** `ToolContext` needs two new optional fields to carry canvas-specific request data into tool functions.

```python
# Source: backend/app/agents/context.py — extend existing dataclass
@dataclass
class ToolContext:
    db_session: Any
    cube_registry: Any
    workflow_id: str | None = None
    workflow_graph: dict | None = None      # NEW — serialized graph for read_workflow_graph
    execution_errors: dict | None = None    # NEW — errors from last run for read_execution_errors
    execution_results: dict | None = None   # NEW — results summary for read_execution_results
```

These are populated from the `AgentChatRequest` body extension and injected in `router.py` before calling `_agent_turn_stream()`.

### Pattern 6: `AgentChatRequest` Schema Extension

The existing schema must accept the canvas-specific fields:

```python
class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    persona: str = Field("canvas_agent")
    workflow_id: str | None = None
    workflow_graph: dict | None = None       # NEW — current canvas serialized graph
    execution_errors: dict | None = None     # NEW — errors from last run
    execution_results: dict | None = None    # NEW — summarized results
    mode: str = Field("general")             # NEW — "optimize" | "fix" | "general"
```

### Pattern 7: Auto-Open Fix Mode

**What:** `useEffect` in EditorPage (or ChatPanel) watches `executionStatus` from flowStore. When execution finishes with any error-status nodes, it fires `setChatPanelOpen(true)` and `setChatPanelMode('fix')` and injects the pre-written template message.

```typescript
// Triggered after execution stops AND errors are present
useEffect(() => {
  if (!isRunning && Object.values(executionStatus).some(s => s.status === 'error')) {
    const errorCount = Object.values(executionStatus).filter(s => s.status === 'error').length;
    setChatPanelOpen(true);
    setChatPanelMode('fix');
    // Inject initial agent message (pre-written, no Gemini call)
    addChatMessage({
      role: 'agent',
      content: `I see errors in ${errorCount} cube(s) from the last run. Want me to diagnose the issues and suggest a fix?`,
      type: 'auto_fix_prompt',
    });
  }
}, [isRunning]);
```

### Anti-Patterns to Avoid

- **Incremental diff application:** Never apply nodes first then edges — partial state causes React Flow to render incomplete connections. Always single `set()` call.
- **Clearing chat history on mode switch:** Per D-07, switching modes must NOT clear messages. Only the system prompt context changes for the next Gemini call.
- **Using EventSource for the agent chat:** EventSource is GET-only. Must use `fetch` + `ReadableStream` for POST SSE. The existing `useWorkflowSSE` uses this correctly.
- **Inlining all cube definitions in system prompt:** Per architecture decision (two-tier catalog) — never do this. Agent calls `list_cubes_summary` first.
- **Calling `google-generativeai`:** Deprecated. Only use `google-genai>=1.68.0` as required by v3.0 architecture.
- **Synchronous Gemini calls:** All Gemini calls must use `client.aio` async interface per architecture decision.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE streaming backend | Custom async generator | `sse_starlette.EventSourceResponse` + `_agent_turn_stream()` | Already implemented and tested in `router.py` |
| Tool dispatch | New dispatch mechanism | Existing `dispatch_tool()` in `dispatcher.py` | Handles retry, ToolContext injection |
| Conversation history | Custom session logic | `get_or_create_session()` + `update_session()` | 30-min TTL cleanup already running |
| History pruning | Manual slice | `prune_history()` from `context.py` | 50k token threshold already tuned |
| Graph serialization | Custom JSON transform | `serializeGraph()` / `deserializeGraph()` from `flowStore.ts` | Both functions tested and handle edge cases |
| Undo snapshot | Manual history push | `pushSnapshot()` from `flowStore.ts` | Already wired to undo/redo; caps at 50 entries |
| Canvas state batch update | Incremental node mutations | Single Zustand `set()` with all changes | React re-renders once; avoids partial broken state |

**Key insight:** The agent infrastructure from Phases 18–19 covers the entire backend communication layer. This phase is primarily a React UI build with a thin backend tool layer.

---

## Common Pitfalls

### Pitfall 1: `propose_graph_diff` Nested Schema Rejection by Gemini

**What goes wrong:** Gemini rejects tool declarations with nested `$defs` or `$ref` in the JSON Schema. Complex nested objects in `parameters_schema` cause silent Gemini API errors.

**Why it happens:** Gemini's tool schema parser is stricter than standard JSON Schema. Nested object definitions using `$defs`/`$ref` patterns are not supported.

**How to avoid:** Keep the `parameters_schema` for `propose_graph_diff` flat. Use `type: object` with simple `properties` only. The diff payload's array items should be described inline, not as `$ref` references.

**Warning signs:** Gemini returns an empty response or errors when the Canvas Agent tries to call `propose_graph_diff`.

### Pitfall 2: Partial Canvas State from Non-Atomic Diff Application

**What goes wrong:** Agent adds nodes but fails before adding edges → canvas shows disconnected nodes with no connections. User sees broken state.

**Why it happens:** Two separate Zustand `set()` calls — first for nodes, then for edges — causes two React renders.

**How to avoid:** `applyAgentDiff()` MUST collect all node additions, node removals, edge additions, edge removals, and param updates, then apply them in a single `set({ nodes: ..., edges: ... })` call.

**Warning signs:** During testing, applying a diff shows nodes first then edges snap in a frame later.

### Pitfall 3: cubeDef Not Found After Agent Adds Node

**What goes wrong:** `applyAgentDiff()` creates a new node but the `cubeDef` lookup fails because the agent used a cube_id that doesn't exist in the catalog.

**Why it happens:** Agent hallucinated a cube name despite the skill rule "never suggest cubes that don't exist." Can still happen with low-frequency cube IDs.

**How to avoid:** In `applyAgentDiff()`, if `catalog.find(c => c.cube_id === n.cube_id)` returns undefined, skip that node with a console.warn and show a toast to the user: "Agent suggested unknown cube: {cube_id}". Never crash.

**Warning signs:** Canvas shows "ghost" nodes with no visible content after applying diff.

### Pitfall 4: Session ID Not Carried Across Chat Turns

**What goes wrong:** Every message starts a new session. Agent has no memory of previous turns. Context resets.

**Why it happens:** Frontend doesn't capture the `session` SSE event (first event from backend) and passes `null` session_id on subsequent messages.

**How to avoid:** On first SSE event of type `session`, capture `session_id` in component state. Pass it in every subsequent `streamAgentChat()` call for this conversation.

**Warning signs:** Agent responds as if seeing the workflow for the first time on every message.

### Pitfall 5: Auto-Open Fix Mode Fires on Every Re-Render

**What goes wrong:** Panel opens repeatedly during execution, disrupting user workflow.

**Why it happens:** `useEffect` watching `executionStatus` fires every time any status changes, including during execution (when cubes transition through `pending` → `running` → `done`).

**How to avoid:** Gate the auto-open logic on the transition from `isRunning: true` to `isRunning: false`. Use a `useRef` to track whether auto-open has already fired for this execution run. Reset the ref when `isRunning` becomes `true`.

**Warning signs:** Panel flashes open multiple times during a single workflow execution.

### Pitfall 6: Mode Affecting Session History

**What goes wrong:** Switching from Fix to Optimize clears chat history (common naive implementation).

**Why it happens:** Dev treats mode like a conversation context reset.

**How to avoid:** Per D-07, mode is only a `mode` field sent in each request body. Chat messages, session_id, and conversation history are unchanged. The system prompt changes server-side based on the `mode` field; the session history remains.

---

## Code Examples

Verified patterns from existing codebase:

### Extending ToolContext

```python
# Source: backend/app/agents/context.py — current dataclass
@dataclass
class ToolContext:
    db_session: Any
    cube_registry: Any
    workflow_id: str | None = None
    # Add these for canvas tools:
    workflow_graph: dict | None = None
    execution_errors: dict | None = None
    execution_results: dict | None = None
```

### Canvas Tool: read_execution_errors

```python
# Source: pattern from backend/app/agents/tools/catalog_tools.py
@agent_tool(
    name="read_execution_errors",
    description="Return error messages from the last workflow execution for each failed cube.",
    parameters_schema={"type": "object", "properties": {}},
)
async def read_execution_errors(ctx: ToolContext) -> dict:
    if ctx.execution_errors is None:
        return {"error": "No execution errors available. Run the workflow first."}
    return {"execution_errors": ctx.execution_errors}
```

### Router: Passing Graph Context

```python
# Source: backend/app/agents/router.py — extend existing tool_context building
tool_context = ToolContext(
    db_session=db,
    cube_registry=cube_registry,
    workflow_id=body.workflow_id,
    workflow_graph=body.workflow_graph,          # NEW
    execution_errors=body.execution_errors,      # NEW
    execution_results=body.execution_results,    # NEW
)
```

### Chat State in flowStore

```typescript
// Source: frontend/src/store/flowStore.ts — add to FlowState interface
// Chat panel state
chatPanelOpen: boolean;
chatPanelMode: 'optimize' | 'fix' | 'general';
chatMessages: ChatMessage[];
chatSessionId: string | null;
pendingDiff: AgentDiff | null;

// Chat actions
setChatPanelOpen: (open: boolean) => void;
setChatPanelMode: (mode: 'optimize' | 'fix' | 'general') => void;
addChatMessage: (msg: ChatMessage) => void;
setChatSessionId: (id: string | null) => void;
setPendingDiff: (diff: AgentDiff | null) => void;
applyAgentDiff: (diff: AgentDiff) => void;
```

### EditorPage Layout Addition

```tsx
// Source: frontend/src/pages/EditorPage.tsx — current layout
// Current:
<div className="app__body">
  <CubeCatalog />
  <div className="app__canvas-area">
    ...
  </div>
</div>

// Modified:
<div className="app__body">
  <CubeCatalog />
  <div className="app__canvas-area">
    ...
  </div>
  <ChatPanel />   {/* added — flex sibling, right of canvas area */}
</div>
```

### System Prompt Mode Injection

```python
# Source: backend/app/agents/router.py _agent_turn_stream()
# Canvas agent uses one skill file; mode context prepended to the message
# or injected as a system prompt prefix depending on implementation choice.
# Simplest approach: prepend mode to user message context, keeping skill file unchanged.
# E.g.: "[Mode: Fix] User message..."
# Or: system prompt loaded from canvas_agent.md + mode-specific section appended.
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `google-generativeai` (deprecated) | `google-genai>=1.68.0` | Must use new package |
| `types.Part.from_function_call(id=...)` | `types.Part.from_function_call(name=..., args=...)` — no `id` param | Discovered 2026-03-24 per STATE.md |
| EventSource for POST SSE | `fetch` + `ReadableStream` | EventSource is GET-only |

---

## Open Questions

1. **Mode injection approach — system prompt vs. message prefix**
   - What we know: Canvas Agent skill file (`canvas_agent.md`) already covers all three modes; `_agent_turn_stream()` takes `persona` which maps to a skill file
   - What's unclear: Should mode be injected as a system prompt suffix or as a per-message context prefix?
   - Recommendation: Inject as a per-message context prefix (e.g., appended to message before passing to `_agent_turn_stream()`). Simpler, no skill file splitting required. Single skill file for the whole Canvas Agent persona.

2. **`read_execution_results` data structure**
   - What we know: `results` in flowStore is `Record<string, { rows: unknown[]; truncated: boolean }>`. Per D-12 and D-14, summarize to `{cube, result_count, sample[3 rows], columns}`.
   - What's unclear: Where does summarization happen — in the tool function or at serialization time in the frontend?
   - Recommendation: Summarize in the backend tool function (`read_execution_results`) after receiving the full results from the request body. This keeps frontend simple (pass raw results) and puts summarization logic server-side.

3. **Drag-resize implementation for panel**
   - What we know: D-02 specifies a drag handle on the left edge; no third-party library
   - What's unclear: Whether to use `mousedown`/`mousemove` events or CSS `resize: horizontal`
   - Recommendation: Manual `mousedown`/`mousemove` event handler attached to the handle div. Store panel width in component state (not flowStore — it's transient UI state). Pattern matches how other custom drag implementations work in the codebase.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 20 is a code-only change. All required runtimes (Python 3.12+, Node.js, pnpm, uv) and external services (Gemini API, FastAPI backend) are already in use and verified by Phase 18–19 completion.

---

## Validation Architecture

> `workflow.nyquist_validation` key is absent from `.planning/config.json` — treated as enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (backend), no frontend test framework detected |
| Config file | `backend/pyproject.toml` (inferred from `uv run pytest`) |
| Quick run command | `cd backend && uv run pytest tests/test_canvas_agent.py -x` |
| Full suite command | `cd backend && uv run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CANVAS-03 | `read_workflow_graph` returns serialized graph | unit | `uv run pytest tests/test_canvas_agent.py::TestCanvasTools::test_read_workflow_graph -x` | ❌ Wave 0 |
| CANVAS-05 | `read_execution_errors` returns errors when present / error when absent | unit | `uv run pytest tests/test_canvas_agent.py::TestCanvasTools::test_read_execution_errors -x` | ❌ Wave 0 |
| CANVAS-07 | `applyAgentDiff` applies atomic add/remove/update | manual | Manual: apply diff, verify nodes+edges render correctly | N/A |
| CANVAS-07 | `applyAgentDiff` calls `pushSnapshot` before applying | unit | `uv run pytest tests/test_canvas_agent.py::TestCanvasDiff -x` | ❌ Wave 0 |
| CANVAS-01/02 | Chat panel opens/closes, mode toggle works | manual | Manual: open editor, toggle panel, switch modes | N/A |
| CANVAS-04/05/06 | Agent responds in correct mode context | manual | Manual: send message in each mode, verify response relevance | N/A |

### Sampling Rate

- **Per task commit:** `cd backend && uv run pytest tests/test_canvas_agent.py -x`
- **Per wave merge:** `cd backend && uv run pytest`
- **Phase gate:** Full backend suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_canvas_agent.py` — covers CANVAS-03, CANVAS-05, CANVAS-07 (backend tools)
- [ ] Fixtures: `make_workflow_graph()` helper (serialized graph dict), `make_execution_errors()` helper

*(No new test framework install needed — pytest is already in use)*

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — all findings verified by reading actual source files:
  - `backend/app/agents/router.py` — `_agent_turn_stream()`, `ToolContext` building, session management
  - `backend/app/agents/registry.py` — `@agent_tool` decorator pattern, schema constraints
  - `backend/app/agents/context.py` — `ToolContext` dataclass, `prune_history()`
  - `backend/app/agents/schemas.py` — `AgentChatRequest`, `AgentSSEEvent`
  - `backend/app/agents/sessions.py` — `get_or_create_session()`, `update_session()`
  - `backend/app/agents/tools/catalog_tools.py` — `@agent_tool` implementation examples
  - `frontend/src/store/flowStore.ts` — `pushSnapshot()`, `applyNodeChanges()`, `serializeGraph()`, `deserializeGraph()`, state interface
  - `frontend/src/pages/EditorPage.tsx` — layout structure, `app__body` flex container
  - `frontend/src/App.css` — `.app__body { display: flex }`, `.app__canvas-area { flex: 1 }`
  - `.planning/STATE.md` — locked architecture decisions (google-genai version, manual tool dispatch, applyAgentDiff pattern, SSE disconnect detection)
  - `.planning/phases/20-canvas-agent/20-CONTEXT.md` — all 14 implementation decisions
  - `.planning/phases/20-canvas-agent/20-UI-SPEC.md` — complete UI design contract

### Secondary (MEDIUM confidence)
- `backend/tests/test_agent_infra.py`, `test_validation.py` — confirmed pytest patterns for new test file structure

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use, verified in package files
- Architecture patterns: HIGH — derived directly from existing working code patterns
- Pitfalls: HIGH for backend (discovered in Phase 18 notes in STATE.md); MEDIUM for frontend (React Flow batch update behavior is documented in xyflow docs but not yet exercised in this codebase)
- UI spec: HIGH — 20-UI-SPEC.md is fully specified and checker-verified

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (stable stack — no fast-moving dependencies)
