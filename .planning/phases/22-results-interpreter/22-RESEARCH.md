# Phase 22: Results Interpreter - Research

**Researched:** 2026-03-26
**Domain:** AI agent integration, SSE streaming, React inline panel, workflow metadata
**Confidence:** HIGH

## Summary

Phase 22 adds a one-shot AI interpretation layer to the existing results drawer, plus a follow-up conversational agent for drill-down. All infrastructure is already built in Phases 18-21. The new work is: one new SSE endpoint (`POST /api/agent/interpret`), two new backend tools (`read_pipeline_summary`, `read_cube_results`), one new persona skill file (`results_interpreter.md` expansion), an inline panel component in `ResultsDrawer`, and a follow-up agent persona (`results_followup`).

The critical architectural insight is that the interpreter is NOT a chat endpoint — it is a one-shot SSE stream triggered by a button click, with no history management. The follow-up agent IS a chat endpoint reusing `POST /api/agent/chat` with a new `results_followup` persona and pre-seeded context injected as the first user message. Both reuse `_agent_turn_stream()` unchanged.

Mission context lives in `graph_json.metadata.mission` (JSONB, set by `generate_workflow` tool). For workflows created via the Build Wizard this contains `description`, `analysis_intent`, and `created_by: "build_wizard"`. Blank-canvas workflows have no `metadata.mission` key — the interpreter detects absence and falls back to cube-type-aware framing.

**Primary recommendation:** Add `POST /api/agent/interpret` as an SSE endpoint (reusing `_agent_turn_stream`), add `read_pipeline_summary` and `read_cube_results` tools scoped to the `results_interpreter` persona, expand the skill file with cube-type framing templates, and build the interpretation panel as local React state in `ResultsDrawer` with no Zustand changes except for the follow-up session ID.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Trigger & Placement**
- D-01: "Interpret Results" button appears in the ResultsDrawer header, next to the existing "Close" button. Only visible when results are showing.
- D-02: Interpretation is manual only — analyst must click the button. No auto-trigger after execution.
- D-03: The button interprets the currently-selected cube's results (not the whole workflow). Analyst can switch cubes and interpret each independently.

**Interpretation Display**
- D-04: Interpretation renders as a collapsible inline panel within the ResultsDrawer, positioned above the table/map area. Analyst sees interpretation alongside their data without navigating away.
- D-05: Interpretation streams in token-by-token via SSE (reuses Phase 18 infrastructure). Shows a loading indicator while streaming. The endpoint is SSE-based, NOT a sync POST.
- D-06: The interpreter itself is one-shot (no multi-turn conversation). After the interpretation renders, a "Discuss results" link/button is shown below it.
- D-07: "Discuss results" opens a dedicated follow-up agent — a separate persona that receives the interpretation summary as context and has tool-calling access to fetch specific cube results on demand (e.g., `read_cube_results(cube_id)`). This is NOT the Canvas Agent — it's a focused results Q&A agent.

**Mission Context Depth**
- D-08: When a workflow has mission context (created via Build Wizard), the interpreter references the mission intent AND compares results against it.
- D-09: When no mission context exists (blank canvas workflow), the interpreter uses cube-type-aware framing — tailored language based on which cube produced the results.

**Scope of Analysis**
- D-10: The interpreter receives the selected cube's results PLUS a pipeline summary showing the upstream path. Enables references like "after filtering 200 flights down to 3."
- D-11: Interpretation is a flowing narrative summary — not bulleted findings or a structured report.
- D-12: Empty results (0 rows) are handled by the interpreter — it explains possible reasons based on cube type and parameters.

### Claude's Discretion

- SSE event format for interpretation streaming (can reuse existing `text`/`done` event types)
- Interpretation panel CSS styling and collapse/expand animation
- Pipeline summary construction (how to walk the graph upstream from the selected cube)
- Follow-up agent persona details and skill file content
- `read_cube_results` tool implementation for the follow-up agent
- How the interpretation summary is passed to the follow-up agent (session context injection vs. system prompt)
- Loading indicator design during streaming

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RESULT-01 | Post-execution analysis triggered from results panel | D-01/D-02/D-03: button in ResultsDrawer header triggers one-shot SSE interpret call; SSE infrastructure in Phase 18 is reusable unchanged |
| RESULT-02 | Mission-context explanation (uses mission metadata from Build Agent) | Mission stored in `graph_json.metadata.mission` JSONB by `generate_workflow` tool; interpreter endpoint receives `workflow_id` and fetches mission from DB |
| RESULT-03 | Fallback generic flight-analysis framing when no mission context exists | Skill file expansion with per-cube-category framing templates; `cube_category` passed in interpret request |
</phase_requirements>

---

## Standard Stack

### Core (all already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sse-starlette | existing | SSE streaming from FastAPI | Already used for agent chat; reuse unchanged |
| google-genai | >=1.68.0 | Gemini client | Locked decision from Phase 18; `>=1.67.0` has typing-extensions bug |
| Zustand | existing | Frontend state | Already used for all canvas + chat state |
| React | 18 | Frontend framework | Project standard |

### No New Libraries Required
This phase adds zero new dependencies. All capabilities exist in the current stack.

**Installation:** None required.

---

## Architecture Patterns

### Recommended Project Structure

New files to create:
```
backend/app/agents/
├── tools/
│   └── interpreter_tools.py      # read_pipeline_summary + read_cube_results tools

frontend/src/components/Results/
├── InterpretPanel.tsx             # Collapsible interpretation panel component
├── InterpretPanel.css             # Panel styling

backend/app/agents/skills/
├── results_interpreter.md        # EXPAND (already exists, needs cube-type framing)
├── results_followup.md           # NEW: follow-up agent persona
```

Modify:
```
backend/app/agents/router.py           # Add POST /api/agent/interpret endpoint
backend/app/agents/tools/__init__.py   # Add interpreter_tools import
frontend/src/components/Results/ResultsDrawer.tsx  # Add button + panel
frontend/src/store/flowStore.ts        # Add interpretation state fields
frontend/src/api/agent.ts             # Add streamInterpret() function
```

### Pattern 1: One-Shot SSE Interpretation Endpoint

The `POST /api/agent/interpret` endpoint is NOT a chat endpoint. It has no session management and no history — each call is independent. It reuses `_agent_turn_stream()` with an empty history and a synthetic first message constructed from:
- Cube name + category
- Row count + sample rows (3) + column names (summarized, never full data)
- Pipeline summary (upstream cube chain)
- Mission context from DB (if exists)

```python
# Source: backend/app/agents/router.py (existing pattern)
@router.post("/interpret")
async def interpret_results(
    body: InterpretRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """One-shot SSE interpretation of a single cube's results."""
    client = get_gemini_client()
    history = []  # No history — one-shot

    tool_context = ToolContext(
        db_session=db,
        cube_registry=cube_registry,
        workflow_id=body.workflow_id,
        workflow_graph=body.workflow_graph,
        execution_results=body.execution_results,
    )

    # Build the interpret request message server-side
    interpret_message = _build_interpret_message(body)

    async def event_publisher():
        async for event in _agent_turn_stream(
            client=client,
            history=history,
            new_message=interpret_message,
            persona="results_interpreter",
            tool_context=tool_context,
            request=request,
            session_id=None,  # No session for one-shot
        ):
            yield ServerSentEvent(data=event.model_dump_json(), event=event.type)

    return EventSourceResponse(event_publisher(), ping=15, headers={"X-Accel-Buffering": "no"})
```

**What `_build_interpret_message` constructs:**
A structured text prompt containing all context the LLM needs:
- Cube name, category, and key parameters
- Result summary: row count, columns, 3 sample rows
- Pipeline path: upstream chain of cube names (e.g., "all_flights → squawk_filter → area_spatial_filter")
- Mission context from `graph_json.metadata.mission` (if present) — `analysis_intent` and `description` fields
- Empty-results indicator if row_count == 0

### Pattern 2: InterpretRequest Schema

New Pydantic schema for the interpret endpoint. Simpler than `AgentChatRequest` — no session, no mode, no persona override:

```python
# Source: backend/app/agents/schemas.py (new addition)
class InterpretRequest(BaseModel):
    workflow_id: str | None = None
    workflow_graph: dict | None = None       # Full graph for pipeline walking
    execution_results: dict | None = None    # All cube results (summarized)
    selected_cube_id: str                    # Which cube to interpret
    cube_name: str                           # Display name for context
    cube_category: str                       # For fallback framing
```

### Pattern 3: Pipeline Summary Construction

Walk the `workflow_graph` edges upstream from `selected_cube_id` to build a linear chain. The graph is a DAG — walk backwards via `edges` where `target == node_id`, follow `source`, repeat.

```python
def build_pipeline_summary(graph: dict, selected_node_id: str) -> str:
    """Walk upstream from selected node, return cube chain as string."""
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    edges = graph.get("edges", [])

    chain = []
    current = selected_node_id

    # BFS/DFS backwards
    visited = set()
    while current and current not in visited:
        visited.add(current)
        node = nodes_by_id.get(current)
        if node:
            chain.append(node["data"]["cube_id"])
        # Find upstream node (edge where target == current)
        upstream = next((e["source"] for e in edges if e["target"] == current), None)
        current = upstream

    chain.reverse()
    return " → ".join(chain)
```

This produces e.g. `"all_flights → squawk_filter → area_spatial_filter"` — the D-10 pipeline summary.

### Pattern 4: Mission Context Fetch

Mission context is in `graph_json.metadata.mission`. The endpoint receives `workflow_id` — fetch the workflow from DB and extract mission:

```python
async def _get_mission_context(db: AsyncSession, workflow_id: str | None) -> dict | None:
    if not workflow_id:
        return None
    result = await db.execute(select(Workflow).where(Workflow.id == uuid.UUID(workflow_id)))
    wf = result.scalar_one_or_none()
    if wf is None:
        return None
    graph_data = wf.graph_json or {}
    return graph_data.get("metadata", {}).get("mission")
```

Mission dict shape (from `generate_workflow` tool):
```json
{
  "description": "Squawk 7700 in Jordan FIR — look for MAYDAY-adjacent activity",
  "analysis_intent": "Find flights squawking 7700 within the Jordan FIR boundary",
  "created_by": "build_wizard",
  "created_at": "2026-03-25T..."
}
```

### Pattern 5: Interpreter Tools (scoped to results_interpreter persona)

Two new tools in `interpreter_tools.py`. These are only useful to the results interpreter — they accept `cube_id` as a parameter to fetch specific results from `ToolContext.execution_results`.

**Note:** The global tool registry means ALL tools are available to ALL personas. This is acceptable because `_agent_turn_stream` passes all tool declarations to every call. The skill file must explicitly tell the LLM which tools it should use. Alternatively, the interpret endpoint can build a filtered tool list — but simpler to use the shared registry with skill file guidance.

```python
# Source: interpreter_tools.py (new file)
@agent_tool(
    name="read_cube_results",
    description=(
        "Return the results for a specific cube by node ID. "
        "Use this to fetch data for a specific cube during results discussion. "
        "Returns row count, columns, and up to 10 sample rows."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "node_id": {
                "type": "string",
                "description": "The node ID of the cube whose results to fetch."
            }
        },
        "required": ["node_id"],
    },
)
async def read_cube_results(ctx: ToolContext, node_id: str = "") -> dict:
    if ctx.execution_results is None:
        return {"error": "No execution results available."}
    data = ctx.execution_results.get(node_id)
    if data is None:
        available = list(ctx.execution_results.keys())
        return {"error": f"No results for node '{node_id}'.", "available_node_ids": available}
    rows = data.get("rows", [])
    columns = list(rows[0].keys()) if rows else []
    return {
        "node_id": node_id,
        "row_count": len(rows),
        "columns": columns,
        "sample_rows": rows[:10],
        "truncated": data.get("truncated", False),
    }
```

### Pattern 6: Follow-Up Agent Wiring

The "Discuss results" button opens the Canvas Agent chat panel with a pre-seeded first message. This reuses the **existing** `POST /api/agent/chat` endpoint with:
- `persona: "results_followup"` (new skill file)
- `session_id: null` (new session)
- `message: "[INTERPRET_CONTEXT] " + interpretationSummary` — the full rendered interpretation text injected as the opening message

This approach avoids creating a separate chat UI. The follow-up agent sees the interpretation as its first context turn and can call `read_cube_results` when the analyst asks follow-up questions.

**Alternative (rejected):** Passing interpretation via system prompt injection through working memory. The problem: working memory is session-scoped and would require creating the session server-side before the chat opens. Injecting as first user message is simpler and matches the existing command pattern (`[BUILD_CONFIRMED]`, `[ADJUST_PLAN]`).

The follow-up agent DOES need `execution_results` in its ToolContext — the frontend must pass these in every `/api/agent/chat` request (same as it does today for Canvas Agent).

### Pattern 7: Frontend State for Interpretation

Interpretation state is **mostly local** to `ResultsDrawer` (not Zustand) since it's ephemeral per-cube view state. However, two pieces belong in the store:
- `interpreterSessionId: string | null` — for the follow-up agent session handoff (must survive across the chart/panel interaction)
- The interpretation content itself can stay local (useState in ResultsDrawer)

**What lives in local state:**
- `interpretText: string` — accumulated streamed text
- `interpretLoading: boolean` — spinner during stream
- `interpretOpen: boolean` — panel collapsed/expanded
- `interpretError: string | null`

**What lives in Zustand:**
- `interpreterSessionId: string | null` — so "Discuss results" button in a child component can hand off context to the chat panel opener. Could also be passed via props; either works since ResultsDrawer is a direct child of EditorPage.

**Recommendation:** Keep it all local (useState) in ResultsDrawer. Pass `interpreterSessionId` as a prop down to the "Discuss results" button, and use a callback prop to open the chat panel. This avoids polluting the store.

### Pattern 8: InterpretPanel Component

```tsx
// Source: new component (pattern from MessageBubble + ResultsDrawer)
interface InterpretPanelProps {
  loading: boolean;
  text: string;       // Accumulated streamed text
  error: string | null;
  onDismiss: () => void;
  onDiscuss: () => void;
}

export function InterpretPanel({ loading, text, error, onDismiss, onDiscuss }: InterpretPanelProps) {
  // Renders: spinner (loading) OR streamed markdown text (text) OR error state
  // "Discuss results" button shown only after streaming completes (text && !loading)
  // Collapse via onDismiss
}
```

The panel is positioned above the table (`results-drawer__content` flex column) using CSS. It uses the existing `renderMarkdown` utility from `MessageBubble` for rendering the narrative text.

### Pattern 9: streamInterpret API Client Function

```typescript
// Source: frontend/src/api/agent.ts (new export alongside streamAgentChat)
export async function* streamInterpret(
  workflowId: string | null,
  workflowGraph: WorkflowGraph | null,
  executionResults: Record<string, unknown> | null,
  selectedCubeId: string,
  cubeName: string,
  cubeCategory: string,
): AsyncGenerator<AgentSSEEvent> {
  const response = await fetch(`${API_BASE}/agent/interpret`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workflow_id: workflowId,
      workflow_graph: workflowGraph,
      execution_results: executionResults,
      selected_cube_id: selectedCubeId,
      cube_name: cubeName,
      cube_category: cubeCategory,
    }),
  });
  // SSE reading loop — identical to streamAgentChat
  ...
}
```

### Anti-Patterns to Avoid

- **Passing full execution results to the LLM:** The existing `read_execution_results` tool already summarizes to 3 sample rows. The interpret endpoint must apply the same cap. Never send 100 raw rows into the Gemini context.
- **Auto-triggering on execution complete:** D-02 explicitly prohibits this. No `useEffect` watching `executionStatus` to trigger interpretation.
- **Using the Canvas Agent persona for follow-up:** Canvas Agent has canvas-mutation tools and different framing. The follow-up must use the `results_followup` persona so the LLM doesn't confuse its role.
- **Building a new SSE streaming loop on the frontend:** The existing `streamAgentChat` generator loop (fetch + ReadableStream + SSE line parsing) is already correct. `streamInterpret` should use the same loop body, just a different URL and payload.
- **Registering interpreter tools in a separate registry:** All tools go through the global `_tools` dict via `@agent_tool`. The skill file governs which tools each persona uses.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE streaming loop (backend) | Custom generator | `_agent_turn_stream()` | Already handles tool dispatch, disconnect detection, history append, thinking tokens |
| SSE reading loop (frontend) | New ReadableStream parser | Copy `streamAgentChat` pattern | Existing loop handles SSE framing, partial lines, decoder correctly |
| Markdown rendering | Custom renderer | `renderMarkdown()` from MessageBubble | Already handles bold, italic, code, lists, headings |
| Session management | New session store | `get_or_create_session()` | 30-min TTL, cleanup task already running |
| Mission context storage | New DB field | `graph_json.metadata.mission` | Already stored by `generate_workflow` |
| Tool dispatch | Direct function calls | `dispatch_tool()` + `ToolContext` | Handles injection, error recovery |

**Key insight:** Phase 18 built general-purpose infrastructure specifically so subsequent phases (19, 20, 21, 22) would only need to add skill files and tools — not new infrastructure. Phase 22 should touch the infrastructure layer minimally.

---

## Common Pitfalls

### Pitfall 1: Tool Registration Order
**What goes wrong:** `interpreter_tools.py` is not imported at startup, so `read_cube_results` is not registered. The LLM attempts to call it but `dispatch_tool` returns "unknown tool."
**Why it happens:** `main.py` imports `app.agents.tools.catalog_tools` directly. Importing any submodule of `app.agents.tools` triggers `__init__.py`, which imports all listed modules. Adding `interpreter_tools` to `__init__.py` is all that's needed.
**How to avoid:** Add `import app.agents.tools.interpreter_tools  # noqa: F401` to `tools/__init__.py`.
**Warning signs:** `dispatch_tool` logs "unknown tool: read_cube_results" during a request.

### Pitfall 2: Sending Full Rows to Gemini
**What goes wrong:** 100 rows × many columns = context explosion, slow response, high cost.
**Why it happens:** `execution_results` in the request body contains full row data.
**How to avoid:** The interpret endpoint summarizes: `rows[:3]` for the one-shot message, `rows[:10]` for `read_cube_results` tool. Never forward raw `execution_results` directly to the LLM prompt.
**Warning signs:** Gemini response time > 30 seconds, token count alerts.

### Pitfall 3: One-Shot vs. Chat Session Confusion
**What goes wrong:** The interpret endpoint tries to manage sessions/history for a one-shot call, or the follow-up chat starts with no context.
**Why it happens:** Conflating the one-shot interpreter with the multi-turn follow-up agent.
**How to avoid:** Interpret endpoint: `history = []`, no `session_id`, no `update_session`. Follow-up: standard `POST /api/agent/chat` with `persona="results_followup"` and interpretation injected as first user message.
**Warning signs:** Interpret endpoint holding onto history across multiple button clicks.

### Pitfall 4: Pipeline Walk on Branching Graphs
**What goes wrong:** Workflow has multiple branches (fan-out); upstream walk from selected cube returns only one path, missing other branches.
**Why it happens:** `build_pipeline_summary` follows only one upstream edge per node.
**How to avoid:** For D-10's requirement, a single upstream path is correct — the pipeline summary shows the path leading TO the selected cube, not the full graph. Clarify in comments. For graphs with multiple upstream nodes (e.g., join cubes), collect all upstream node names for the same depth level.
**Warning signs:** Interpretation doesn't mention an obvious upstream filter.

### Pitfall 5: Empty Results Handling
**What goes wrong:** Interpreter returns "No results found" without actionable guidance, violating D-12.
**Why it happens:** Default LLM behavior when given 0 rows is minimal.
**How to avoid:** Skill file must include explicit guidance: "When row_count is 0, explain likely reasons based on cube_category and parameters, and suggest concrete next steps (expand date range, check filter values, try a different data source)."
**Warning signs:** Interpretation for 0-row results is a single sentence with no suggestions.

### Pitfall 6: ResultsDrawer isOpen Guard
**What goes wrong:** "Interpret Results" button appears even when the drawer is closed or has 0 rows.
**Why it happens:** Button visibility tied only to `selectedNodeId !== null` instead of the full `isOpen` condition.
**How to avoid:** The existing `isOpen` in ResultsDrawer is `selectedNodeId !== null && results !== null && results.rows.length > 0`. The button must respect this — D-12 says 0-row results are handled by the interpreter, but D-01 says the button is only visible when results are showing. These are compatible: the drawer opens when rows > 0 (current behavior), and 0-row results close the drawer. The interpreter should handle 0-row case when the user explicitly clicks in the brief window before closing.

Actually — re-reading: `isOpen` requires `rows.length > 0`, so the drawer won't be open for 0 rows. The 0-row empty-result handling (D-12) refers to workflows where the filtered result count is 0 but the cube did execute (the drawer would NOT show in this case). The interpreter's 0-row handling path might need the button to be visible even when rows=0 — or interpret the result from a different trigger. **This is an open question for the planner.**

### Pitfall 7: pro_personas Set in router.py
**What goes wrong:** `results_interpreter` uses `gemini-flash` by default. If it needs reasoning depth, it must be added to `pro_personas`.
**Why it happens:** `pro_personas = {"canvas_agent", "build_agent"}` — other personas get flash.
**How to avoid:** For the interpreter, flash is appropriate (it's a summarization task, not deep reasoning). `results_followup` also uses flash. No change needed to `pro_personas`.
**Warning signs:** Only if interpretation quality is poor — then consider adding to `pro_personas`.

---

## Code Examples

### Build Interpret Message (server-side prompt construction)

```python
# Source: backend/app/agents/router.py or new helper module
def _build_interpret_message(body: InterpretRequest, mission: dict | None, result_summary: dict) -> str:
    """Construct the single LLM message for one-shot interpretation."""
    parts = []

    # Cube identification
    parts.append(f"Cube: {body.cube_name} (category: {body.cube_category})")

    # Result summary
    row_count = result_summary.get("row_count", 0)
    columns = result_summary.get("columns", [])
    sample = result_summary.get("sample_rows", [])
    parts.append(f"Result: {row_count} rows, columns: {', '.join(columns)}")
    if sample:
        import json
        parts.append(f"Sample (first 3 rows):\n{json.dumps(sample, default=str)}")

    # Pipeline summary
    if body.workflow_graph:
        pipeline = build_pipeline_summary(body.workflow_graph, body.selected_cube_id)
        parts.append(f"Pipeline: {pipeline}")

    # Mission context (if present)
    if mission:
        intent = mission.get("analysis_intent") or mission.get("description", "")
        parts.append(f"Analyst's mission: {intent}")
    else:
        parts.append("No mission context available — use cube-type-aware framing.")

    return "\n\n".join(parts)
```

### ResultsDrawer Button + Panel Integration

```tsx
// Source: frontend/src/components/Results/ResultsDrawer.tsx (additions)
// Local state additions:
const [interpretText, setInterpretText] = useState('');
const [interpretLoading, setInterpretLoading] = useState(false);
const [interpretOpen, setInterpretOpen] = useState(false);
const [interpretError, setInterpretError] = useState<string | null>(null);
const abortRef = useRef<AbortController | null>(null);

// Handler:
const handleInterpret = async () => {
  if (!selectedNodeId || !results) return;
  abortRef.current?.abort();
  abortRef.current = new AbortController();
  setInterpretText('');
  setInterpretError(null);
  setInterpretLoading(true);
  setInterpretOpen(true);

  try {
    for await (const event of streamInterpret(...)) {
      if (event.type === 'text') {
        setInterpretText(prev => prev + (event.data as string));
      }
      if (event.type === 'done') break;
    }
  } catch (e) {
    setInterpretError('Interpretation failed — try again.');
  } finally {
    setInterpretLoading(false);
  }
};

// In header JSX (next to Close button):
{isOpen && (
  <button className="results-drawer__interpret" onClick={handleInterpret} disabled={interpretLoading}>
    {interpretLoading ? 'Interpreting...' : 'Interpret Results'}
  </button>
)}

// In content JSX (above table, when interpretOpen):
{interpretOpen && (
  <InterpretPanel
    loading={interpretLoading}
    text={interpretText}
    error={interpretError}
    onDismiss={() => setInterpretOpen(false)}
    onDiscuss={handleDiscuss}
  />
)}
```

### New Endpoint Registration Pattern

```python
# Source: backend/app/agents/router.py (addition)
class InterpretRequest(BaseModel):
    workflow_id: str | None = None
    workflow_graph: dict | None = None
    execution_results: dict | None = None
    selected_cube_id: str
    cube_name: str
    cube_category: str = "unknown"
```

### Skill File Structure for Cube-Type Framing (results_interpreter.md expansion)

The existing 14-line skill file needs expansion with:
1. A section on **cube-type framing** — explicit per-category language guidance
2. A section on **mission-context integration** — when to reference `analysis_intent` vs. infer
3. A section on **empty results handling** — actionable suggestions per category
4. **Narrative format rule** — flowing prose, not bullet points (D-11)

Example framing template guidance:
```markdown
## Cube-Type Framing (when no mission context)

For cubes in category `data_source`:
- Frame as collection scope: "This result contains X flights from [source] ..."

For cubes in category `filter` with squawk-related params:
- Frame as emergency code language: "X flights were identified squawking [code] ..."

For cubes in category `filter` with geographic params:
- Frame as geographic scope: "X flights transited the [region] airspace ..."

For cubes in category `analysis` (signal health, anomaly):
- Frame as anomaly language: "X anomalies were detected, with [top type] appearing most frequently ..."
```

### results_followup Skill File Pattern

```markdown
# Results Follow-Up Agent

You are the Results Follow-Up agent for Tracer 42. An analyst has just read an interpretation
of their workflow results and wants to ask follow-up questions.

## Your Context
The conversation begins with the original interpretation that was shown to the analyst.
Use it as your grounding context for all follow-up answers.

## Your Tools
- `read_cube_results(node_id)` — Fetch results for a specific cube to answer specific questions.

## Rules
- Stay focused on the results being discussed. Do not suggest workflow changes.
- When the analyst asks "show me the top 5", call read_cube_results and answer specifically.
- Keep answers concise and grounded in the actual data.
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `POST /api/agent/interpret` (sync, planned in STATE.md) | SSE-based (D-05) | Phase 22 CONTEXT.md decision | Endpoint is streaming, not sync; frontend must use SSE reader not awaited fetch |
| `google-generativeai` (deprecated) | `google-genai>=1.68.0` | Phase 18 | Must NOT use old package |
| Sync Gemini calls | `client.aio.models.generate_content_stream()` | Phase 18 | Sync calls block event loop |

**Deprecated/outdated:**
- STATE.md mentions `POST /api/agent/interpret (sync)` — this is superseded by the SSE decision in CONTEXT.md D-05.

---

## Open Questions

1. **Zero-row results and drawer visibility**
   - What we know: `ResultsDrawer.isOpen` requires `rows.length > 0` (current code). D-12 says interpreter handles empty results.
   - What's unclear: Does the analyst ever see 0-row results in the drawer? If not, D-12's empty-results path is unreachable via the current trigger.
   - Recommendation: Planner should decide — either (a) allow drawer to open for 0-row results with a "0 results" state that shows the Interpret button, or (b) scope D-12 to mean "the interpreter gracefully handles the case if it somehow receives 0 rows" (e.g., from a cube with partial execution). Option (a) requires modifying `isOpen` logic.

2. **Tool scoping: all tools visible to all personas**
   - What we know: The global tool registry exposes all registered tools to all Gemini calls. `read_cube_results` will be visible to Canvas Agent too.
   - What's unclear: Whether Canvas Agent (or other agents) could accidentally call `read_cube_results` and get confused.
   - Recommendation: Acceptable risk — skill files already govern tool usage. Canvas Agent's skill file doesn't mention `read_cube_results`. If stricter scoping is needed, pass a filtered `tool_decls` list to `_agent_turn_stream` based on persona. Planner can decide.

3. **"Discuss results" UI: chat panel or separate modal**
   - What we know: D-07 says a dedicated follow-up agent in a chat UI. CONTEXT.md says it's not the Canvas Agent but a separate persona.
   - What's unclear: Whether to reuse the existing Canvas Agent `ChatPanel` component (just changing persona) or build a new panel.
   - Recommendation: Reuse `ChatPanel` component with a prop for persona. The panel is already generic enough. This avoids building a new chat UI. Planner should confirm this is acceptable.

---

## Environment Availability

Step 2.6: SKIPPED (no new external dependencies — this phase uses existing FastAPI, Gemini client, React/Zustand stack already verified in Phases 18-21).

---

## Validation Architecture

Note: `workflow.nyquist_validation` is absent from `.planning/config.json` — treated as enabled. However, this project has no existing test files for the agent layer. Following the established project pattern (no VERIFICATION.md files for any phase per STATE.md tech debt note), test coverage targets are aspirational.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (existing in backend) |
| Config file | `backend/pyproject.toml` |
| Quick run command | `cd backend && uv run pytest tests/ -x -q` |
| Full suite command | `cd backend && uv run pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RESULT-01 | `POST /api/agent/interpret` returns SSE stream with text events | smoke | `uv run pytest tests/test_interpret.py::test_interpret_endpoint -x` | ❌ Wave 0 |
| RESULT-02 | Mission context from DB injected into interpret message | unit | `uv run pytest tests/test_interpret.py::test_build_interpret_message_with_mission -x` | ❌ Wave 0 |
| RESULT-03 | Fallback framing used when no mission context | unit | `uv run pytest tests/test_interpret.py::test_build_interpret_message_no_mission -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && uv run pytest tests/ -x -q`
- **Per wave merge:** `cd backend && uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_interpret.py` — covers RESULT-01, RESULT-02, RESULT-03
- [ ] Tests for `build_pipeline_summary()` utility function (pure function, easy to unit test)
- [ ] Tests for `read_cube_results` tool with missing/present node IDs

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `backend/app/agents/router.py` — `_agent_turn_stream` signature and behavior
- Direct code inspection: `backend/app/agents/sessions.py` — session management pattern
- Direct code inspection: `backend/app/agents/context.py` — `ToolContext` fields
- Direct code inspection: `backend/app/agents/tools/canvas_tools.py` — `read_execution_results` summarization pattern
- Direct code inspection: `backend/app/agents/tools/wizard_tools.py` — `generate_workflow` mission metadata shape
- Direct code inspection: `backend/app/models/workflow.py` — JSONB `graph_json` field
- Direct code inspection: `frontend/src/components/Results/ResultsDrawer.tsx` — header structure, `isOpen` logic
- Direct code inspection: `frontend/src/api/agent.ts` — SSE reading pattern
- Direct code inspection: `frontend/src/components/Chat/MessageBubble.tsx` — `renderMarkdown` pattern
- Direct code inspection: `backend/app/agents/tools/__init__.py` — tool registration chain
- Direct code inspection: `backend/app/main.py` — lifespan tool registration

### Secondary (MEDIUM confidence)
- `.planning/phases/22-results-interpreter/22-CONTEXT.md` — all architectural decisions (D-01 through D-12)
- `.planning/STATE.md` — locked decisions from research phases

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use, verified by code inspection
- Architecture patterns: HIGH — reuses existing infrastructure, patterns verified in source
- Pitfalls: HIGH — identified from direct code inspection (tool registration order, row summarization cap, isOpen guard)
- Open questions: Genuinely open — three questions identified that require planner decisions

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (stable infrastructure — only relevant change would be Gemini API updates)
