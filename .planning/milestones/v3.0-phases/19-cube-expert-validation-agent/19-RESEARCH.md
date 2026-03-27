# Phase 19: Cube Expert + Validation Agent - Research

**Researched:** 2026-03-24
**Domain:** LLM sub-agent architecture, rule-based workflow validation, FastAPI sync endpoints, React panel components
**Confidence:** HIGH — Phase 18 infrastructure is fully built; all patterns are code-confirmed from the actual codebase.

## Summary

Phase 19 adds two independent but complementary capabilities on top of the Phase 18 agent infrastructure: (1) rule-based structural validation with a sync `POST /api/agent/validate` endpoint, and (2) a Cube Expert Python class that wraps a dedicated Gemini call to reason about cube selection.

Validation is intentionally LLM-free. All structural checks (missing required params, dangling handles, type mismatches, cycles) run as pure Python against `WorkflowGraph`, `CubeDefinition`, and the existing `topological_sort()`. Template-based explanation strings fill in cube/param names at render time. The endpoint returns sync JSON — no SSE, no Gemini call. This makes it fast (<100ms), deterministic, and zero API cost.

The Cube Expert is a Python class, never an HTTP endpoint. It makes its own Gemini call using `gemini-2.5-flash` with the `cube_expert.md` skill file and three tools: the two existing catalog tools plus a new `find_cubes_for_task` keyword-search tool. It receives only a task description string — not the orchestrator's conversation history. Downstream agents (Canvas, Build) instantiate it directly.

**Primary recommendation:** Build validation as a standalone module under `backend/app/agents/validation.py` (pure Python, no Gemini dependency) and Cube Expert as `backend/app/agents/cube_expert.py` (wraps client + skill loader + tool dispatch). Wire both into `backend/app/agents/router.py` as the spec-locked `POST /api/agent/validate` endpoint.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Two severity levels only: **error** (blocks execution) and **warning** (informational).
- **D-02:** Errors: missing required parameters, dangling input/output handles (sourceHandle/targetHandle not found in cube definition), cycles in the graph.
- **D-03:** Warnings: type mismatches between connected parameters, orphan nodes (cubes with zero connections).
- **D-04:** Handle validation checks that both sourceHandle and targetHandle exist in the respective cube definitions.
- **D-05:** Validation runs automatically when the user clicks Run (pre-run only). No standalone Validate button.
- **D-06:** If errors exist, execution is blocked and the issues panel opens. Warnings do not block execution.
- **D-07:** Issues displayed in a collapsible panel below the canvas (console/terminal style). Each issue shows cube name, parameter name, and explanation. Clicking an issue highlights the relevant node on canvas.
- **D-08:** When validation passes cleanly (zero issues), execution starts immediately with no confirmation dialog or toast. Silent pass-through for the happy path.
- **D-09:** Cube Expert is invoked via a **separate Gemini call** with its own chat turn using `cube_expert.md` skill file. Not direct function calls.
- **D-10:** Uses **gemini-2.5-flash** model (per STATE.md architecture decision).
- **D-11:** Three tools available to Cube Expert: `list_cubes_summary` (existing), `get_cube_definition` (existing), and a new `find_cubes_for_task` (keyword search across cube descriptions/params — pure string matching, no LLM).
- **D-12:** Internal only — no `/api/agent/cube-expert` HTTP endpoint. Called by Canvas Agent (Phase 20) and Build Agent (Phase 21) internally.
- **D-13:** Sub-agent receives only the task description, not the orchestrator's full history.
- **D-14:** All validation checks are **pure rule-based Python code**. No LLM involvement in structural checking.
- **D-15:** Human-readable explanations use **pre-written templates** per issue type with cube/param names filled in. No Gemini call in the validation path.
- **D-16:** Validation endpoint is **sync JSON**: `POST /api/agent/validate` returns a JSON response with issues array.

### Claude's Discretion

- Validation rule implementation details (how to traverse the graph, check handle existence)
- `find_cubes_for_task` search algorithm (keyword matching, TF-IDF, or simple substring)
- Cube Expert Python class structure and how it wraps the Gemini call
- Issues panel frontend component design and node highlighting mechanism
- Validation response schema shape

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CUBE-01 | Two-tier catalog tool — summary endpoint (names + descriptions by category) | `list_cubes_summary` is already fully implemented in `catalog_tools.py`; just needs `find_cubes_for_task` added alongside it. |
| CUBE-02 | Full cube definition loader (params, types, constraints on demand) | `get_cube_definition` is already fully implemented in `catalog_tools.py`; no changes needed. |
| CUBE-03 | Cube Expert sub-agent that reasons about which cube fits a use case | New `CubeExpert` class; follows `_agent_turn_stream` pattern from `router.py` but non-streaming and scoped to `cube_expert` persona. |
| VALID-01 | Rule-based structural checks (missing params, dangling inputs, type mismatches, cycles) | `topological_sort()` already handles cycles; `ParamDefinition.required` and handle name lookup via `CubeRegistry.get()` support the rest. |
| VALID-02 | Human-readable explanation of issues via template (not LLM) | Pre-written template strings per issue type, parameterized with cube/param names at check time. |
| VALID-03 | Pre-run trigger — validation runs before workflow execution | Toolbar `handleRun` calls `POST /api/agent/validate` before `startStream`; blocks on errors. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | (existing) | Sync `POST /api/agent/validate` endpoint | Already in use; sync routes work naturally alongside SSE routes |
| google-genai | >=1.68.0 | Gemini call in Cube Expert | Locked decision in STATE.md; v1.67.0 has typing-extensions bug |
| Pydantic v2 | (existing) | `ValidationIssue`, `ValidationResponse` schemas | All API contracts use Pydantic in this codebase |
| React + Zustand | (existing) | Issues panel state management + node highlight | Canvas state already in `flowStore.ts` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sse-starlette | (existing) | NOT needed for validate endpoint | Validate is sync JSON, not SSE |
| pytest-asyncio | (existing) | Testing Cube Expert async call (mocked) | All async tests already use `asyncio_mode = "auto"` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Template strings for explanations | LLM-generated messages | Templates are deterministic, free, instant; LLM adds latency and API cost with no quality benefit for structural errors |
| Substring keyword matching in `find_cubes_for_task` | TF-IDF / embeddings | Simple substring is sufficient — cube descriptions are short, predictable; embeddings add dependency overhead |
| Sync JSON for validate | SSE stream | Validation is deterministic and fast (<100ms); SSE adds frontend complexity for no benefit |

**Installation:** No new packages required. Phase 18 installed all dependencies.

## Architecture Patterns

### Recommended Project Structure

```
backend/app/agents/
├── validation.py         # New: pure Python validator (no Gemini)
├── cube_expert.py        # New: CubeExpert class (wraps Gemini call)
├── router.py             # Extend: add POST /api/agent/validate
├── schemas.py            # Extend: ValidationIssue, ValidationRequest, ValidationResponse
├── tools/
│   └── catalog_tools.py  # Extend: add find_cubes_for_task
└── skills/
    ├── cube_expert.md    # Exists: Cube Expert persona
    └── validation_agent.md  # Exists: placeholder only (not used — validation is rule-based)

frontend/src/
├── components/
│   └── Validation/
│       ├── IssuesPanel.tsx   # New: collapsible panel below canvas
│       └── IssuesPanel.css
├── store/
│   └── flowStore.ts      # Extend: validationIssues state, showIssuesPanel flag
└── api/
    └── agent.ts          # New: validateWorkflow() API client function
```

### Pattern 1: Rule-Based Validation in `validation.py`

**What:** A single `validate_graph(graph: WorkflowGraph, registry: CubeRegistry) -> ValidationResponse` function that runs all checks in one pass and returns a structured result.

**When to use:** Called by `POST /api/agent/validate`. No instantiation, no state, no async.

```python
# backend/app/agents/validation.py (new file)
from app.schemas.workflow import WorkflowGraph
from app.engine.registry import CubeRegistry
from app.engine.executor import topological_sort

def validate_graph(graph: WorkflowGraph, registry: CubeRegistry) -> "ValidationResponse":
    issues = []

    # 1. Cycle check — reuse existing topological_sort
    try:
        topological_sort(graph.nodes, graph.edges)
    except ValueError:
        issues.append(ValidationIssue(
            severity="error",
            node_id=None,
            cube_name=None,
            param_name=None,
            message="Workflow contains a cycle. Circular connections are not allowed.",
            rule="cycle",
        ))
        # Cycle makes other checks unreliable — return early
        return ValidationResponse(issues=issues)

    node_map = {n.id: n for n in graph.nodes}

    for node in graph.nodes:
        cube = registry.get(node.data.cube_id)
        if cube is None:
            issues.append(ValidationIssue(
                severity="error",
                node_id=node.id,
                cube_name=node.data.cube_id,
                param_name=None,
                message=f"Cube '{node.data.cube_id}' is not registered in the catalog.",
                rule="unknown_cube",
            ))
            continue

        defn = cube.definition
        input_names = {p.name for p in defn.inputs}
        output_names = {p.name for p in defn.outputs}
        # Add special full-result handle
        output_names.add("__full_result__")

        connected_inputs = {
            e.targetHandle for e in graph.edges
            if e.target == node.id and e.targetHandle
        }

        # 2. Missing required params (not provided by user AND not connected)
        for param in defn.inputs:
            if not param.required:
                continue
            has_value = (
                node.data.params.get(param.name) not in (None, "", [])
            )
            is_connected = param.name in connected_inputs
            if not has_value and not is_connected:
                issues.append(ValidationIssue(
                    severity="error",
                    node_id=node.id,
                    cube_name=defn.name,
                    param_name=param.name,
                    message=(
                        f"Cube '{defn.name}' is missing required input '{param.name}'. "
                        f"Connect a data source or enter a value."
                    ),
                    rule="missing_required_param",
                ))

    # 3. Dangling handles — edges referencing non-existent params
    for edge in graph.edges:
        source_node = node_map.get(edge.source)
        target_node = node_map.get(edge.target)

        if source_node:
            src_cube = registry.get(source_node.data.cube_id)
            if src_cube and edge.sourceHandle:
                valid_outputs = {p.name for p in src_cube.definition.outputs}
                valid_outputs.add("__full_result__")
                if edge.sourceHandle not in valid_outputs:
                    issues.append(ValidationIssue(
                        severity="error",
                        node_id=edge.source,
                        cube_name=src_cube.definition.name,
                        param_name=edge.sourceHandle,
                        message=(
                            f"Edge references output '{edge.sourceHandle}' on cube "
                            f"'{src_cube.definition.name}', but that output does not exist."
                        ),
                        rule="dangling_source_handle",
                    ))

        if target_node:
            tgt_cube = registry.get(target_node.data.cube_id)
            if tgt_cube and edge.targetHandle:
                valid_inputs = {p.name for p in tgt_cube.definition.inputs}
                if edge.targetHandle not in valid_inputs:
                    issues.append(ValidationIssue(
                        severity="error",
                        node_id=edge.target,
                        cube_name=tgt_cube.definition.name,
                        param_name=edge.targetHandle,
                        message=(
                            f"Edge references input '{edge.targetHandle}' on cube "
                            f"'{tgt_cube.definition.name}', but that input does not exist."
                        ),
                        rule="dangling_target_handle",
                    ))

    # 4. Type mismatch warnings
    for edge in graph.edges:
        source_node = node_map.get(edge.source)
        target_node = node_map.get(edge.target)
        if not (source_node and target_node and edge.sourceHandle and edge.targetHandle):
            continue
        if edge.sourceHandle == "__full_result__":
            continue
        src_cube = registry.get(source_node.data.cube_id)
        tgt_cube = registry.get(target_node.data.cube_id)
        if not (src_cube and tgt_cube):
            continue
        src_param = next((p for p in src_cube.definition.outputs if p.name == edge.sourceHandle), None)
        tgt_param = next((p for p in tgt_cube.definition.inputs if p.name == edge.targetHandle), None)
        if src_param and tgt_param and src_param.type != tgt_param.type:
            issues.append(ValidationIssue(
                severity="warning",
                node_id=edge.target,
                cube_name=tgt_cube.definition.name,
                param_name=edge.targetHandle,
                message=(
                    f"Type mismatch: '{src_cube.definition.name}.{edge.sourceHandle}' "
                    f"({src_param.type.value}) connected to "
                    f"'{tgt_cube.definition.name}.{edge.targetHandle}' "
                    f"({tgt_param.type.value})."
                ),
                rule="type_mismatch",
            ))

    # 5. Orphan node warnings
    all_connected_nodes = set()
    for edge in graph.edges:
        all_connected_nodes.add(edge.source)
        all_connected_nodes.add(edge.target)
    for node in graph.nodes:
        if node.id not in all_connected_nodes and len(graph.nodes) > 1:
            cube = registry.get(node.data.cube_id)
            cube_name = cube.definition.name if cube else node.data.cube_id
            issues.append(ValidationIssue(
                severity="warning",
                node_id=node.id,
                cube_name=cube_name,
                param_name=None,
                message=f"Cube '{cube_name}' has no connections.",
                rule="orphan_node",
            ))

    return ValidationResponse(issues=issues)
```

### Pattern 2: Cube Expert Class in `cube_expert.py`

**What:** A Python class that makes a single non-streaming Gemini call with the `cube_expert` persona and three tools. Returns a text string (the expert's recommendation).

**When to use:** Called by Canvas Agent and Build Agent to resolve "which cube fits this task?" questions.

```python
# backend/app/agents/cube_expert.py (new file)
import logging
from google.genai import types
from app.agents.client import get_gemini_client
from app.agents.context import ToolContext
from app.agents.dispatcher import dispatch_tool
from app.agents.registry import get_gemini_tool_declarations
from app.agents.skills_loader import get_system_prompt
from app.config import settings

log = logging.getLogger(__name__)

class CubeExpert:
    """Sub-agent that reasons about cube selection using a dedicated Gemini call.

    Receives only a task description string — not the orchestrator's history.
    Uses gemini-2.5-flash + cube_expert persona + three catalog tools.
    """

    async def ask(self, task: str, ctx: ToolContext) -> str:
        """Ask the Cube Expert which cube fits the described task.

        Returns: plain text recommendation string.
        """
        client = get_gemini_client()
        system_prompt = get_system_prompt("cube_expert")
        raw_tools = get_gemini_tool_declarations()
        tool_decls = [
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=t["parameters"],
            )
            for t in raw_tools
        ]
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[types.Tool(function_declarations=tool_decls)] if tool_decls else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        history = [types.Content(role="user", parts=[types.Part(text=task)])]

        # Tool dispatch loop (non-streaming, matches router.py pattern)
        for _ in range(10):
            response = await client.aio.models.generate_content(
                model=settings.gemini_flash_model,
                contents=history,
                config=config,
            )
            # Check for tool calls
            fc_list = []
            for part in (response.candidates[0].content.parts if response.candidates else []):
                if hasattr(part, "function_call") and part.function_call:
                    fc_list.append(part.function_call)

            if not fc_list:
                # Text response — done
                return response.text or ""

            # Execute tools and append results
            history.append(response.candidates[0].content)
            for fc in fc_list:
                result = await dispatch_tool(fc.name, dict(fc.args) if fc.args else {}, ctx)
                history.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(name=fc.name, response=result)]
                ))

        return ""  # Safety fallback if loop exhausts
```

### Pattern 3: `find_cubes_for_task` Tool

**What:** Keyword-search tool. Splits the query into words, scores each cube by how many words appear in `cube_id + name + description` (case-insensitive), returns top-N ranked cubes with summaries.

**When to use:** Called by Cube Expert before `get_cube_definition` — narrows the field from all cubes to the most relevant candidates.

```python
@agent_tool(
    name="find_cubes_for_task",
    description=(
        "Search for cubes that match a task description by keyword. "
        "Returns ranked cube summaries. Use this after list_cubes_summary "
        "when you have a specific task to match."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language description of the task, e.g. 'filter flights by geographic area'",
            },
            "limit": {
                "type": "number",
                "description": "Maximum number of results to return (default: 5)",
            },
        },
        "required": ["query"],
    },
)
async def find_cubes_for_task(ctx: ToolContext, query: str = "", limit: int = 5) -> dict:
    if ctx.cube_registry is None:
        return {"error": "Cube registry not available"}
    keywords = query.lower().split()
    scored = []
    for cube_def in ctx.cube_registry.catalog():
        haystack = f"{cube_def.cube_id} {cube_def.name} {cube_def.description}".lower()
        score = sum(1 for kw in keywords if kw in haystack)
        if score > 0:
            scored.append((score, cube_def))
    scored.sort(key=lambda x: x[0], reverse=True)
    return {
        "results": [
            {
                "cube_id": d.cube_id,
                "name": d.name,
                "description": d.description,
                "category": d.category.value if hasattr(d.category, "value") else str(d.category),
                "score": s,
            }
            for s, d in scored[:limit]
        ]
    }
```

### Pattern 4: Validation Schemas in `schemas.py`

**What:** Pydantic models for the `POST /api/agent/validate` request and response.

```python
# Add to backend/app/agents/schemas.py

class ValidationIssue(BaseModel):
    severity: str           # "error" | "warning"
    node_id: str | None     # ID of the offending node (null for graph-level issues like cycles)
    cube_name: str | None   # Human-readable cube name
    param_name: str | None  # Parameter name or handle name (null for node-level issues)
    message: str            # Pre-written template message, fully formatted
    rule: str               # Machine-readable rule name: "missing_required_param",
                            # "dangling_source_handle", "dangling_target_handle",
                            # "type_mismatch", "orphan_node", "cycle", "unknown_cube"

class ValidationRequest(BaseModel):
    graph: WorkflowGraph

class ValidationResponse(BaseModel):
    issues: list[ValidationIssue]

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)
```

### Pattern 5: Sync Validate Endpoint in `router.py`

**What:** Add a plain `async def` route (no SSE) that calls `validate_graph` and returns JSON. Sits alongside the existing `POST /api/agent/chat` SSE route.

```python
# Add to backend/app/agents/router.py

from app.agents.validation import validate_graph
from app.agents.schemas import ValidationRequest, ValidationResponse

@router.post("/validate", response_model=ValidationResponse)
async def validate_workflow(
    body: ValidationRequest,
    db: AsyncSession = Depends(get_db),
) -> ValidationResponse:
    """Validate a workflow graph for structural issues.

    Returns issues array. Errors block execution. Warnings are informational.
    No LLM call — pure rule-based Python, fast (<100ms).
    """
    return validate_graph(body.graph, cube_registry)
```

### Pattern 6: Frontend Pre-Run Validation Hook

**What:** Modify `handleRun` in `Toolbar.tsx` to call `POST /api/agent/validate` with the current graph before calling `startStream`. If errors exist, abort and open issues panel. If only warnings, continue (silent).

```typescript
// frontend/src/api/agent.ts (new file)
import { apiFetch } from './client';
import type { WorkflowGraph } from '../types/workflow';

export interface ValidationIssue {
  severity: 'error' | 'warning';
  node_id: string | null;
  cube_name: string | null;
  param_name: string | null;
  message: string;
  rule: string;
}

export interface ValidationResponse {
  issues: ValidationIssue[];
}

export const validateWorkflow = (graph: WorkflowGraph) =>
  apiFetch<ValidationResponse>('/agent/validate', {
    method: 'POST',
    body: JSON.stringify({ graph }),
  });
```

```typescript
// In Toolbar.tsx handleRun — insert before startStream(graph):
const validation = await validateWorkflow(graph);
const errors = validation.issues.filter(i => i.severity === 'error');
if (errors.length > 0) {
  useFlowStore.getState().setValidationIssues(validation.issues);
  useFlowStore.getState().setShowIssuesPanel(true);
  return; // block execution
}
// Clear stale issues on clean validation
useFlowStore.getState().setValidationIssues(validation.issues); // may have warnings
startStream(graph);
```

### Pattern 7: Issues Panel Component

**What:** A collapsible `<div>` rendered below the canvas in `EditorPage.tsx`. Each row shows severity icon + cube name + param + message. Clicking a row calls `setSelectedNodeId` on the React Flow instance to highlight the offending node.

Key design details:
- Sits between `<FlowCanvas />` and `<ResultsDrawer />` in the `app__canvas-area` div
- Collapsible via a toggle header (panel is open by default when errors exist)
- Node highlight: call `useReactFlow().setCenter()` or apply a CSS class via Zustand + node data change
- Empty state when no issues: panel hidden or collapsed

### Anti-Patterns to Avoid

- **Calling Gemini in the validation path:** Validation is rule-based only (D-14). Even for "nice" explanations, pre-written templates are correct here.
- **Making CubeExpert an HTTP endpoint:** It is a Python class only, called internally (D-12). An HTTP endpoint would expose it incorrectly and add round-trip latency.
- **Sharing orchestrator history with CubeExpert:** Sub-agent receives task string only (D-13). Passing full history causes context explosion.
- **Using `generate_content_stream` for CubeExpert:** The expert response is short text; non-streaming `generate_content` is appropriate. No streaming needed.
- **Using `google-generativeai` (deprecated):** Always `from google import genai` — the `google-generativeai` package is deprecated per STATE.md.
- **Registering `find_cubes_for_task` in the global tool registry without care:** The global registry is shared with the main chat agent. All three catalog tools are appropriate for both — no conflict. But do not register validation-specific internals as agent tools.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cycle detection | Graph traversal code | `topological_sort()` in `executor.py` | Already handles Kahn's algorithm correctly; raises `ValueError` on cycle |
| Cube lookup by ID | Dict traversal | `CubeRegistry.get(cube_id)` | Registry singleton is already loaded at startup |
| Param definition access | Manual schema parsing | `cube.definition.inputs` / `.outputs` (list of `ParamDefinition`) | Direct attribute access, typed by Pydantic |
| Gemini client | `genai.Client` instantiation | `get_gemini_client()` singleton from `client.py` | Manages init, API key, cleanup |
| System prompt assembly | String concatenation | `get_system_prompt("cube_expert")` from `skills_loader.py` | Prepends `system_brief` + persona automatically |
| Tool dispatch | Direct function calls | `dispatch_tool()` from `dispatcher.py` | Handles retry, error wrapping, ToolContext injection |
| Tool declarations | Manual dict building | `get_gemini_tool_declarations()` from `registry.py` | Returns all registered tools in Gemini-compatible format |

**Key insight:** Phase 18 built exactly the infrastructure needed. The Phase 19 additions are thin layers on top — validation.py is ~100 lines of pure Python; cube_expert.py is ~60 lines wrapping existing primitives.

## Common Pitfalls

### Pitfall 1: `find_cubes_for_task` registered in global tool registry — visible to main chat agent
**What goes wrong:** If `find_cubes_for_task` is registered via `@agent_tool`, it appears in `get_gemini_tool_declarations()` which is consumed by the main chat agent in `router.py`. The main chat agent will try to call it, which is fine — it's a valid tool for any agent.
**Why it happens:** `_tools` dict in `registry.py` is global. All `@agent_tool` decorated functions end up there.
**How to avoid:** This is actually fine and intended per D-11 — the three catalog tools are available to all agents. Just ensure the description is clear enough that the main chat agent uses it correctly too. No special scoping needed.
**Warning signs:** None — this is expected behavior.

### Pitfall 2: Missing required param check incorrectly blocks when param has a connection
**What goes wrong:** Validation flags a required param as missing, but it's actually being supplied by an incoming edge — the validator forgot to check connected inputs.
**Why it happens:** Checking `node.data.params` alone misses connection-supplied values.
**How to avoid:** Build `connected_inputs` set from `graph.edges` (where `edge.target == node.id`) before checking required params. A param is satisfied if: it has a non-empty value in `node.data.params` OR its name appears in `connected_inputs`.
**Warning signs:** Validator reports false positives on correctly-wired workflows.

### Pitfall 3: `__full_result__` handle treated as dangling
**What goes wrong:** The `__full_result__` sourceHandle is a virtual handle that bundles all outputs. It is not in `cube.definition.outputs` by name. Handle validation flags every edge using it.
**Why it happens:** `__full_result__` is a convention in `executor.py` (line 79), not a declared output param.
**How to avoid:** When checking source handles, add `"__full_result__"` to the set of valid output names before the membership check. Confirmed in `executor.py`: `if edge.sourceHandle == "__full_result__": value = source_outputs`.
**Warning signs:** Every workflow with a full-result connection reports a dangling handle error.

### Pitfall 4: Cube Expert tool dispatch loop stalls on no-text final response
**What goes wrong:** Gemini returns a response with no text and no function calls (e.g., empty content). The loop exits without returning useful text.
**Why it happens:** Edge case in Gemini API — finish_reason may be STOP with empty parts.
**How to avoid:** After the loop, return a fallback string like `""` or check `response.text` with a default. The `CubeExpert.ask()` pattern above already handles this.
**Warning signs:** `cube_expert.ask()` returns empty string for valid queries.

### Pitfall 5: Frontend issues panel re-renders on every store update during execution
**What goes wrong:** `validationIssues` state in Zustand is an array. If the array reference changes on unrelated store updates, the panel re-renders unnecessarily.
**Why it happens:** Zustand subscriptions re-render on reference equality by default.
**How to avoid:** Use a selector that returns the same reference when issues haven't changed — or store issues as a stable reference (only set from validate call, never mutated incrementally).
**Warning signs:** Panel flickers during workflow execution.

### Pitfall 6: Node highlight after clicking issue doesn't work in React Flow v12+
**What goes wrong:** Calling `reactFlowInstance.setCenter()` to highlight the offending node may not visually distinguish the node as the problem source.
**Why it happens:** `setCenter` scrolls to the node but doesn't change its appearance. Visual highlight requires either updating node data to add a CSS class or using React Flow's `selected` state.
**How to avoid:** The cleanest approach for this codebase: dispatch a Zustand action that stores `highlightedNodeId`, and have `CubeNode` read this to apply a CSS class. This avoids touching React Flow's internal selected state (which the user may have already set by clicking nodes).
**Warning signs:** User clicks an issue row, viewport scrolls, but no node is visually distinguished.

## Code Examples

### Importing and calling `topological_sort` for cycle check

```python
# Source: backend/app/engine/executor.py (confirmed)
from app.engine.executor import topological_sort

try:
    topological_sort(graph.nodes, graph.edges)
except ValueError:
    # "Workflow graph contains a cycle" — exact message from line 55
    ...
```

### Accessing param definitions for a cube

```python
# Source: backend/app/engine/registry.py + backend/app/schemas/cube.py (confirmed)
cube = registry.get(node.data.cube_id)  # returns BaseCube | None
if cube:
    defn = cube.definition  # CubeDefinition
    for param in defn.inputs:  # list[ParamDefinition]
        if param.required:
            print(param.name, param.type.value)
```

### Non-streaming Gemini call (for CubeExpert)

```python
# Source: Pattern derived from router.py _agent_turn_stream — adapted for non-streaming
# google-genai 1.68.0, confirmed working in Phase 18
response = await client.aio.models.generate_content(
    model=settings.gemini_flash_model,   # "gemini-2.5-flash"
    contents=history,
    config=config,
)
text = response.text  # str | None
```

### Checking for function calls in non-streaming response

```python
# Source: google-genai SDK pattern confirmed in Phase 18 (router.py uses streaming variant)
# For non-streaming: iterate response.candidates[0].content.parts
for part in response.candidates[0].content.parts:
    if hasattr(part, "function_call") and part.function_call:
        fc = part.function_call
        result = await dispatch_tool(fc.name, dict(fc.args) if fc.args else {}, ctx)
```

### Frontend: `apiFetch` wrapper pattern (confirmed from `workflows.ts`)

```typescript
// Source: frontend/src/api/workflows.ts (confirmed pattern)
import { apiFetch } from './client';

export const validateWorkflow = (graph: WorkflowGraph) =>
  apiFetch<ValidationResponse>('/agent/validate', {
    method: 'POST',
    body: JSON.stringify({ graph }),
  });
```

### Zustand store extension pattern (confirmed from `flowStore.ts`)

```typescript
// Source: frontend/src/store/flowStore.ts (confirmed interface pattern)
// Add to FlowState interface:
validationIssues: ValidationIssue[];
showIssuesPanel: boolean;
highlightedNodeId: string | null;
setValidationIssues: (issues: ValidationIssue[]) => void;
setShowIssuesPanel: (show: boolean) => void;
setHighlightedNodeId: (nodeId: string | null) => void;
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `google-generativeai` (deprecated) | `google-genai` >= 1.68.0 | 2026 | All new code uses `from google import genai` |
| `types.Part.from_function_call(id=..., name=..., args=...)` | `types.Part.from_function_call(name=..., args=...)` only | Phase 18 (2026-03-24) | `id` parameter not accepted in 1.68.0 — omit it |
| Streaming for all Gemini calls | Non-streaming `generate_content` for short sub-agent calls | Phase 19 | Cube Expert uses `client.aio.models.generate_content` (no `_stream` suffix) |

**Deprecated/outdated:**
- `execute_graph()` in `executor.py`: Dead production code per STATE.md tech debt. Do not reference from new code; use `stream_graph()` for execution. Validation does not call either.
- Orphaned `GET /api/workflows/{id}/run/stream` route: Exists in router but has no frontend caller. Phase 19 does not use or touch it.

## Open Questions

1. **Does `find_cubes_for_task` need to search param descriptions as well as cube descriptions?**
   - What we know: Current cube descriptions are at the cube level. Param descriptions (`ParamDefinition.description`) are shorter but could add signal (e.g., "GeoJSON polygon" in `area_spatial_filter`).
   - What's unclear: Whether including param text improves recall meaningfully for the 15-20 cubes currently registered.
   - Recommendation: Start with `cube_id + name + description` only (simpler). Extend to param descriptions in a follow-up if false negatives are observed.

2. **Should validation run against the current in-memory graph or the last-saved graph?**
   - What we know: `handleRun` in `Toolbar.tsx` serializes the current in-memory graph via `serializeGraph(nodes, edges)` before calling `startStream`. Validation should match this.
   - What's unclear: Whether there's a need to auto-save before validation.
   - Recommendation: Validate the in-memory serialized graph (same object passed to `startStream`). Do not auto-save. This is consistent with the existing run flow.

3. **Node highlighting mechanism: `highlightedNodeId` in Zustand vs React Flow `selected` state**
   - What we know: React Flow v12 (`@xyflow/react`) tracks `selected` state on nodes internally. `CubeNode` in this codebase reads `node.data` for custom rendering.
   - What's unclear: Whether `useReactFlow().setNodes()` to toggle a node's `selected` prop would conflict with user selection.
   - Recommendation: Use a dedicated `highlightedNodeId` in Zustand. `CubeNode` applies a `cube-node--highlighted` CSS class when `node.id === highlightedNodeId`. Clear on next validation run or on canvas click.

## Environment Availability

Step 2.6: SKIPPED — Phase 19 has no new external dependencies. All required tools (Python, uv, pnpm, Gemini API via google-genai) were verified in Phase 18.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` |
| Quick run command | `cd backend && uv run pytest tests/test_validation.py tests/test_cube_expert.py -x` |
| Full suite command | `cd backend && uv run pytest` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VALID-01 | Missing required param flagged as error | unit | `uv run pytest tests/test_validation.py::TestValidation::test_missing_required_param -x` | Wave 0 |
| VALID-01 | Dangling sourceHandle flagged as error | unit | `uv run pytest tests/test_validation.py::TestValidation::test_dangling_source_handle -x` | Wave 0 |
| VALID-01 | Dangling targetHandle flagged as error | unit | `uv run pytest tests/test_validation.py::TestValidation::test_dangling_target_handle -x` | Wave 0 |
| VALID-01 | Cycle detected as error | unit | `uv run pytest tests/test_validation.py::TestValidation::test_cycle_detection -x` | Wave 0 |
| VALID-01 | Type mismatch flagged as warning | unit | `uv run pytest tests/test_validation.py::TestValidation::test_type_mismatch_warning -x` | Wave 0 |
| VALID-01 | Orphan node flagged as warning | unit | `uv run pytest tests/test_validation.py::TestValidation::test_orphan_node_warning -x` | Wave 0 |
| VALID-01 | Clean graph returns zero issues | unit | `uv run pytest tests/test_validation.py::TestValidation::test_clean_graph_no_issues -x` | Wave 0 |
| VALID-01 | `__full_result__` handle not flagged as dangling | unit | `uv run pytest tests/test_validation.py::TestValidation::test_full_result_handle_valid -x` | Wave 0 |
| VALID-02 | Error message contains cube name and param name | unit | covered by test_missing_required_param above | Wave 0 |
| VALID-03 | POST /api/agent/validate returns 200 with issues array | integration | `uv run pytest tests/test_validation.py::TestValidateEndpoint -x` | Wave 0 |
| CUBE-01 | `list_cubes_summary` returns grouped categories | unit | `uv run pytest tests/test_agent_infra.py::TestRegistry::test_catalog_tools_registered -x` | Exists |
| CUBE-02 | `get_cube_definition` returns full params for known cube | unit | `uv run pytest tests/test_cube_expert.py::TestCatalogTools::test_get_cube_definition -x` | Wave 0 |
| CUBE-03 | `find_cubes_for_task` returns scored results for keyword | unit | `uv run pytest tests/test_cube_expert.py::TestFindCubes -x` | Wave 0 |
| CUBE-03 | CubeExpert.ask() dispatches tools and returns non-empty text (mocked Gemini) | unit | `uv run pytest tests/test_cube_expert.py::TestCubeExpert::test_ask_mocked -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && uv run pytest tests/test_validation.py tests/test_cube_expert.py -x`
- **Per wave merge:** `cd backend && uv run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_validation.py` — covers VALID-01, VALID-02, VALID-03
- [ ] `backend/tests/test_cube_expert.py` — covers CUBE-02, CUBE-03

*(CUBE-01 is partially covered by existing `test_agent_infra.py::TestRegistry::test_catalog_tools_registered`. Extend or add to it.)*

## Sources

### Primary (HIGH confidence)

- `/Users/oriklain/work/five/tracer/12-flow/backend/app/engine/executor.py` — `topological_sort()` signature, cycle error message, `__full_result__` handle convention confirmed
- `/Users/oriklain/work/five/tracer/12-flow/backend/app/agents/router.py` — Gemini tool dispatch loop pattern, `_agent_turn_stream`, session handling, sync route patterns confirmed
- `/Users/oriklain/work/five/tracer/12-flow/backend/app/agents/tools/catalog_tools.py` — existing `list_cubes_summary` and `get_cube_definition` confirmed as fully implemented (not stubs)
- `/Users/oriklain/work/five/tracer/12-flow/backend/app/schemas/cube.py` — `ParamDefinition.required`, `ParamType`, `CubeDefinition.inputs/outputs` confirmed
- `/Users/oriklain/work/five/tracer/12-flow/backend/app/schemas/workflow.py` — `WorkflowGraph`, `WorkflowNode`, `WorkflowEdge` (with `sourceHandle`/`targetHandle`) confirmed
- `/Users/oriklain/work/five/tracer/12-flow/backend/app/agents/registry.py` — `@agent_tool` decorator, global `_tools` dict, `get_gemini_tool_declarations()` confirmed
- `/Users/oriklain/work/five/tracer/12-flow/backend/app/agents/client.py` — `get_gemini_client()` singleton, `client.aio.models` confirmed
- `/Users/oriklain/work/five/tracer/12-flow/backend/app/agents/skills_loader.py` — `get_system_prompt()` prepends `system_brief` + persona confirmed
- `/Users/oriklain/work/five/tracer/12-flow/frontend/src/components/Toolbar/Toolbar.tsx` — `handleRun` flow (serialize graph → `startStream`) confirmed; injection point identified
- `/Users/oriklain/work/five/tracer/12-flow/frontend/src/store/flowStore.ts` — `FlowState` interface shape, extension pattern confirmed
- `/Users/oriklain/work/five/tracer/12-flow/.planning/STATE.md` — locked architecture decisions confirmed (flash model, no HTTP endpoint for Cube Expert, three agent HTTP endpoints, sub-agent history isolation)
- `/Users/oriklain/work/five/tracer/12-flow/.planning/phases/19-cube-expert-validation-agent/19-CONTEXT.md` — all D-01 through D-16 decisions

### Secondary (MEDIUM confidence)

- `backend/app/agents/dispatcher.py` — retry behavior, `ToolContext` injection — confirmed functional in Phase 18 integration tests

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and in use
- Architecture: HIGH — all patterns derived directly from Phase 18 source code
- Pitfalls: HIGH — most are code-confirmed edge cases (e.g., `__full_result__` handle, `id` param omission in `from_function_call`)
- Frontend integration: HIGH — injection point in `handleRun` confirmed from `Toolbar.tsx`

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (stable — no fast-moving dependencies)
