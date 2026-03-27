"""Agent chat SSE endpoint — streams Gemini responses with tool execution."""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette import EventSourceResponse, ServerSentEvent
from starlette.requests import Request
from google.genai import types

from app.agents.client import get_gemini_client
from app.agents.context import ToolContext, prune_history
from app.agents.dispatcher import dispatch_tool
from app.agents.registry import get_gemini_tool_declarations
from app.agents.schemas import AgentChatRequest, AgentSSEEvent, InterpretRequest, ValidationRequest, ValidationResponse
from app.agents.sessions import (
    get_or_create_session,
    update_session,
    get_session_persona,
    get_working_memory,
    update_working_memory,
)
from app.agents.skills_loader import get_system_prompt
from app.agents.validation import validate_graph
from app.config import settings
from app.database import get_db
from app.engine.registry import registry as cube_registry

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _build_tool_declarations() -> list[types.FunctionDeclaration]:
    """Convert registry tool dicts to Gemini FunctionDeclaration objects."""
    raw = get_gemini_tool_declarations()
    return [
        types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=t["parameters"],
        )
        for t in raw
    ]


_VERIFY_PROMPT = """\
You are a workflow verification agent for Tracer 42, a flight analysis platform.

You are reviewing a workflow plan BEFORE it is shown to the analyst. Your job is to catch problems the build agent might have missed.

## Working Memory from the build conversation:

### Mission
{mission}

### Investigation
{investigation}

### Implementation Plan
{implementation_plan}

## Preview Data (the proposed workflow)
```json
{preview_json}
```

## What to Check

1. **Logical correctness** — Do the cubes and connections actually achieve what the analyst asked for? Is the data flow logical?
2. **Missing steps** — Is there a filter or data source that should be included but isn't?
3. **Wrong connections** — Are outputs wired to the right inputs? Does the data flow make sense?
4. **Parameter issues** — Are key parameters filled in correctly based on what the analyst said?
5. **Intent mismatch** — Did the build agent misunderstand what the analyst wanted?

## Response Format

If the plan looks correct, respond with EXACTLY:
```
PASS
```

If there are issues, respond with:
```
ISSUES
- <issue 1: brief description of the problem and how to fix it>
- <issue 2: brief description>
```

Be concise. Only flag real problems, not style preferences. If the plan is reasonable, say PASS.
"""


async def _verify_plan(client, preview_data: dict, session_id: str | None) -> str | None:
    """Run a single verification pass on the workflow plan.

    Returns None if the plan passes, or a string with issues to fix.
    Uses Gemini Flash for speed (not Pro).
    """
    memory = get_working_memory(session_id) if session_id else {}
    prompt = _VERIFY_PROMPT.format(
        mission=memory.get("mission", "(not set)"),
        investigation=memory.get("investigation", "(not set)"),
        implementation_plan=memory.get("implementation_plan", "(not set)"),
        preview_json=json.dumps(preview_data, indent=2),
    )

    try:
        response = await client.aio.models.generate_content(
            model=settings.gemini_flash_model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                system_instruction="You are a workflow verification agent. Be concise and precise.",
            ),
        )
        text = response.text.strip() if response.text else "PASS"

        if text.startswith("PASS"):
            return None
        if text.startswith("ISSUES"):
            # Return just the issues list
            return text[len("ISSUES"):].strip()
        # Ambiguous response — treat as pass
        return None
    except Exception as e:
        log.warning("Plan verification failed (treating as pass): %s", e)
        return None


async def _agent_turn_stream(
    client,
    history: list[types.Content],
    new_message: str,
    persona: str,
    tool_context: ToolContext,
    request: Request,
    session_id: str | None = None,
) -> AsyncGenerator[AgentSSEEvent, None]:
    """One agent turn: stream text, handle tool calls, resume streaming.

    Implements the manual tool dispatch loop per research Pattern 2.
    AFC is disabled so we detect function calls manually.
    """
    # Build system prompt from skills + working memory
    working_memory = get_working_memory(session_id) if session_id else None
    system_prompt = get_system_prompt(persona, working_memory)

    # Build tool declarations
    tool_decls = _build_tool_declarations()

    # Configure Gemini call — enable thinking for pro model
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=[types.Tool(function_declarations=tool_decls)] if tool_decls else None,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
    )

    # Add new user message to history
    history.append(
        types.Content(role="user", parts=[types.Part(text=new_message)])
    )

    # Prune history if needed before calling Gemini
    prune_history(history)

    # Pro personas use gemini-2.5-pro for reasoning depth; others use flash
    pro_personas = {"canvas_agent", "build_agent"}
    model_name = settings.gemini_pro_model if persona in pro_personas else settings.gemini_flash_model

    # Outer loop: keep going until Gemini returns text (no more tool calls)
    max_tool_rounds = 10  # Safety limit
    for _round in range(max_tool_rounds):
        tool_call_detected = False
        streamed_text = ""

        async for chunk in await client.aio.models.generate_content_stream(
            model=model_name,
            contents=history,
            config=config,
        ):
            # Check disconnect before yielding (per D-13)
            if await request.is_disconnected():
                return

            # Stream thinking and text tokens
            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                for part in chunk.candidates[0].content.parts:
                    if part.thought and part.text:
                        yield AgentSSEEvent(type="thinking", data=part.text)
                    elif part.text and not part.thought:
                        streamed_text += part.text
                        yield AgentSSEEvent(type="text", data=part.text)

            # Detect tool calls
            if chunk.function_calls:
                tool_call_detected = True
                # Preserve original parts from chunk (includes thought_signature for Gemini 3)
                original_parts = list(chunk.candidates[0].content.parts) if chunk.candidates else []

                # Execute each tool and collect results
                tool_results: list[tuple[str, dict]] = []
                for fc in chunk.function_calls:
                    yield AgentSSEEvent(
                        type="tool_call",
                        data={"name": fc.name, "args": dict(fc.args) if fc.args else {}},
                    )

                    result = await dispatch_tool(fc.name, dict(fc.args) if fc.args else {}, tool_context)

                    # --- Plan verification gate ---
                    # When show_intent_preview is called, run a one-shot verification.
                    # If issues found, replace the result with an error so the build
                    # agent fixes the plan and tries again. Only verify once per session.
                    if fc.name == "show_intent_preview" and session_id and persona == "build_agent":
                        memory = get_working_memory(session_id)
                        already_verified = memory.get("_verification_done", "")
                        if not already_verified:
                            yield AgentSSEEvent(
                                type="tool_call",
                                data={"name": "plan_verification", "args": {}},
                            )
                            issues = await _verify_plan(client, result, session_id)
                            if issues:
                                # Mark that verification ran (so we don't loop)
                                update_working_memory(session_id, "_verification_done", "attempted")
                                # Replace the preview result with issues
                                result = {
                                    "status": "verification_failed",
                                    "issues": issues,
                                    "instruction": (
                                        "The verification agent found issues with your plan. "
                                        "Fix the problems listed below, update your Working Memory, "
                                        "then call show_intent_preview again with the corrected plan. "
                                        "Do NOT ask the analyst about these — fix them yourself."
                                    ),
                                }
                                yield AgentSSEEvent(
                                    type="tool_result",
                                    data={"name": "plan_verification", "result": {"status": "issues_found"}},
                                )
                            else:
                                update_working_memory(session_id, "_verification_done", "passed")
                                yield AgentSSEEvent(
                                    type="tool_result",
                                    data={"name": "plan_verification", "result": {"status": "passed"}},
                                )

                    tool_results.append((fc.name, result))

                    yield AgentSSEEvent(
                        type="tool_result",
                        data={"name": fc.name, "result": result},
                    )

                # Append model's original parts to history (preserves thought_signature)
                history.append(types.Content(
                    role="model",
                    parts=original_parts,
                ))

                # Append all tool results to history
                history.append(types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(name=name, response=res)
                        for name, res in tool_results
                    ],
                ))
                break  # End chunk iteration; restart Gemini call with tool results

        if not tool_call_detected:
            # Append model's text response to history
            if streamed_text:
                history.append(types.Content(
                    role="model",
                    parts=[types.Part(text=streamed_text)]
                ))
            break

    yield AgentSSEEvent(type="done", data=None)


@router.post("/chat")
async def agent_chat(
    body: AgentChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Stream an agent chat response as Server-Sent Events.

    Typed events: text, tool_call, tool_result, thinking, done, session.
    First event is always 'session' with the session_id for the client to reuse.
    """
    client = get_gemini_client()

    # Get or create session
    session_id, history = get_or_create_session(body.session_id, body.persona)

    # Build tool context (per D-07)
    tool_context = ToolContext(
        db_session=db,
        cube_registry=cube_registry,
        workflow_id=body.workflow_id,
        workflow_graph=body.workflow_graph,
        execution_errors=body.execution_errors,
        execution_results=body.execution_results,
        session_id=session_id,
    )

    # Prepend mode context to user message for Gemini system prompt awareness
    mode_prefix = f"[Mode: {body.mode}] " if body.mode != "general" else ""

    # Translate UI command signals into clear LLM directives
    command_map = {
        "[BUILD_CONFIRMED]": (
            "[COMMAND: BUILD_CONFIRMED] The analyst clicked 'Build This' to approve the workflow plan. "
            "Skip to Step 4 immediately. Your Working Memory contains a 'Last Preview' section with "
            "the EXACT cubes, connections, and parameters the analyst approved. Use that structured JSON "
            "as the source of truth — translate those nodes and connections into the generate_workflow call. "
            "Do NOT ask any questions. Do NOT start over. Do NOT invent a different workflow. "
            "Call get_cube_definition for each cube in the preview, then call generate_workflow "
            "with nodes and edges matching the approved preview exactly."
        ),
        "[ADJUST_PLAN]": (
            "[COMMAND: ADJUST_PLAN] The analyst clicked 'Adjust Plan'. "
            "Ask what they'd like to change about the current plan. Keep it brief — one question."
        ),
    }
    effective_message = command_map.get(body.message, f"{mode_prefix}{body.message}")

    async def event_publisher():
        # First event: session ID so client can reuse it.
        # Must include "type" in the JSON payload because the frontend SSE parser
        # reads only data: lines and uses event.type from the JSON — the SSE event: field is ignored.
        yield ServerSentEvent(
            data=json.dumps({"type": "session", "data": {"session_id": session_id}}),
            event="session",
        )

        async for event in _agent_turn_stream(
            client=client,
            history=history,
            new_message=effective_message,
            persona=body.persona,
            tool_context=tool_context,
            request=request,
            session_id=session_id,
        ):
            if await request.is_disconnected():
                break
            yield ServerSentEvent(
                data=event.model_dump_json(),
                event=event.type,
            )

        # Update session with latest history
        update_session(session_id, history)

    return EventSourceResponse(
        event_publisher(),
        ping=15,
        headers={"X-Accel-Buffering": "no"},
    )


@router.post("/mission")
async def save_mission(
    workflow_id: str,
    mission: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Save mission context to workflow metadata (per INFRA-07).

    Stores in graph_json.metadata.mission without overwriting existing graph data.
    """
    from sqlalchemy import select
    from app.models.workflow import Workflow
    import uuid
    from datetime import datetime, timezone

    result = await db.execute(
        select(Workflow).where(Workflow.id == uuid.UUID(workflow_id))
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Workflow not found")

    graph_data = dict(wf.graph_json) if wf.graph_json else {}
    metadata = graph_data.get("metadata", {})
    metadata["mission"] = mission
    graph_data["metadata"] = metadata
    wf.graph_json = graph_data
    wf.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return {"status": "saved", "workflow_id": workflow_id}


@router.post("/build-from-preview")
async def build_from_preview(
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Build a workflow directly from the last approved preview — no LLM round-trip.

    Reads last_preview from session working memory, converts the preview nodes/connections
    into a full workflow graph, validates, and saves to DB.
    """
    import uuid as uuid_mod
    from datetime import datetime, timezone
    from app.agents.sessions import get_working_memory
    from app.models.workflow import Workflow
    from app.schemas.workflow import (
        Position, WorkflowEdge, WorkflowGraph, WorkflowNode, WorkflowNodeData,
    )

    session_id = body.get("session_id")
    if not session_id:
        return {"status": "error", "message": "Missing session_id"}

    memory = get_working_memory(session_id)
    preview_json = memory.get("last_preview", "")
    if not preview_json:
        return {"status": "error", "message": "No preview found — build a plan first"}

    preview = json.loads(preview_json)
    preview_nodes = preview.get("nodes", [])
    preview_connections = preview.get("connections", [])
    mission_name = preview.get("mission_name", "Untitled Workflow")
    mission_description = preview.get("mission_description", "")

    if not preview_nodes:
        return {"status": "error", "message": "Preview has no nodes"}

    # --- Compute topological depth for positioning ---
    depth_map: dict[str, int] = {n["cube_id"]: 0 for n in preview_nodes}
    children: dict[str, list[str]] = {n["cube_id"]: [] for n in preview_nodes}
    has_incoming: set[str] = set()

    for conn in preview_connections:
        children.setdefault(conn["from_cube"], []).append(conn["to_cube"])
        has_incoming.add(conn["to_cube"])

    queue = [n["cube_id"] for n in preview_nodes if n["cube_id"] not in has_incoming]
    while queue:
        current = queue.pop(0)
        current_depth = depth_map.get(current, 0)
        for child in children.get(current, []):
            if depth_map.get(child, 0) <= current_depth:
                depth_map[child] = current_depth + 1
                queue.append(child)

    # Group by depth for y-positioning
    by_depth: dict[int, list[str]] = {}
    for cube_id, depth in depth_map.items():
        by_depth.setdefault(depth, []).append(cube_id)

    # --- Build workflow nodes ---
    node_id_map: dict[str, str] = {}  # cube_id → node_id
    wf_nodes: list[WorkflowNode] = []

    for pnode in preview_nodes:
        cube_id = pnode["cube_id"]
        node_id = f"{cube_id}_1"
        node_id_map[cube_id] = node_id

        depth = depth_map.get(cube_id, 0)
        y_index = by_depth.get(depth, []).index(cube_id)

        wf_nodes.append(WorkflowNode(
            id=node_id,
            type="cube",
            position=Position(x=depth * 300, y=y_index * 200),
            data=WorkflowNodeData(
                cube_id=cube_id,
                params=pnode.get("key_params") or {},
            ),
        ))

    # --- Build workflow edges ---
    wf_edges: list[WorkflowEdge] = []
    for i, conn in enumerate(preview_connections):
        source_id = node_id_map.get(conn["from_cube"])
        target_id = node_id_map.get(conn["to_cube"])
        if not source_id or not target_id:
            continue

        # Resolve handle names: use explicit names if provided,
        # otherwise default to __full_result__ output → first input that accepts it
        source_handle = conn.get("from_output")
        target_handle = conn.get("to_input")

        if not source_handle:
            source_handle = "__full_result__"

        if not target_handle:
            target_cube = cube_registry.get(conn["to_cube"])
            if target_cube:
                # Find first input that accepts_full_result, or just first input
                for inp in target_cube.inputs:
                    if getattr(inp, "accepts_full_result", False):
                        target_handle = inp.name
                        break
                if not target_handle and target_cube.inputs:
                    target_handle = target_cube.inputs[0].name

        wf_edges.append(WorkflowEdge(
            id=f"e_{i}",
            source=source_id,
            target=target_id,
            sourceHandle=source_handle,
            targetHandle=target_handle,
        ))

    graph = WorkflowGraph(nodes=wf_nodes, edges=wf_edges)

    # Validate
    result = validate_graph(graph, cube_registry)
    if result.has_errors:
        return {
            "status": "validation_failed",
            "errors": [
                issue.model_dump()
                for issue in result.issues
                if issue.severity == "error"
            ],
        }

    # Save
    graph_dict = graph.model_dump()
    mission_text = memory.get("mission", "")
    graph_dict["metadata"] = {
        "mission": {
            "description": mission_description or mission_text,
            "analysis_intent": mission_text,
            "created_by": "build_wizard",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    }

    wf = Workflow(id=uuid_mod.uuid4(), name=mission_name, graph_json=graph_dict)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)

    return {
        "status": "created",
        "workflow_id": str(wf.id),
        "workflow_name": wf.name,
    }


@router.post("/validate", response_model=ValidationResponse)
async def validate_workflow(body: ValidationRequest) -> ValidationResponse:
    """Validate a workflow graph for structural issues.

    Returns issues array. Errors block execution. Warnings are informational.
    No LLM call -- pure rule-based Python, fast (<100ms).
    """
    return validate_graph(body.graph, cube_registry)


# ---------------------------------------------------------------------------
# Results Interpreter helpers (per D-05, D-08, D-09, D-10, D-11, D-12)
# ---------------------------------------------------------------------------


async def _get_mission_context(db: AsyncSession, workflow_id: str | None) -> dict | None:
    """Fetch mission context from workflow metadata JSONB."""
    if not workflow_id:
        return None
    from sqlalchemy import select
    from app.models.workflow import Workflow
    import uuid
    result = await db.execute(
        select(Workflow).where(Workflow.id == uuid.UUID(workflow_id))
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        return None
    graph_data = wf.graph_json or {}
    return graph_data.get("metadata", {}).get("mission")


def _build_interpret_message(
    body: InterpretRequest,
    mission: dict | None,
    result_summary: dict,
    pipeline_str: str | None,
) -> str:
    """Construct the single LLM message for one-shot interpretation."""
    parts = []

    # Cube identification
    parts.append(f"Cube: {body.cube_name} (category: {body.cube_category})")

    # Result summary
    row_count = result_summary.get("row_count", 0)
    columns = result_summary.get("columns", [])
    sample = result_summary.get("sample_rows", [])
    parts.append(f"Result: {row_count} rows, columns: {', '.join(str(c) for c in columns)}")
    if sample:
        import json as _json
        parts.append(f"Sample (first {len(sample)} rows):\n{_json.dumps(sample, default=str, indent=2)}")

    # Pipeline summary
    if pipeline_str:
        parts.append(f"Pipeline path: {pipeline_str}")

    # Mission context
    if mission:
        intent = mission.get("analysis_intent") or mission.get("description", "")
        desc = mission.get("description", "")
        parts.append(f"Analyst's mission: {intent}")
        if desc and desc != intent:
            parts.append(f"Mission description: {desc}")
    else:
        parts.append("No mission context available — use cube-type-aware framing based on the cube category.")

    return "\n\n".join(parts)


def _summarize_selected_cube(execution_results: dict | None, selected_cube_id: str) -> dict:
    """Extract and summarize results for the selected cube."""
    if not execution_results:
        return {"row_count": 0, "columns": [], "sample_rows": []}
    data = execution_results.get(selected_cube_id, {})
    rows = data.get("rows", []) if isinstance(data, dict) else []
    columns = list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
    return {
        "row_count": len(rows),
        "columns": columns,
        "sample_rows": rows[:3],  # Cap at 3 for the one-shot message
        "truncated": data.get("truncated", False) if isinstance(data, dict) else False,
    }


def _build_pipeline_str(workflow_graph: dict | None, selected_node_id: str) -> str | None:
    """Walk upstream from selected node to build pipeline string."""
    if not workflow_graph:
        return None
    nodes = workflow_graph.get("nodes", [])
    edges = workflow_graph.get("edges", [])
    if not nodes:
        return None

    nodes_by_id = {n["id"]: n for n in nodes}
    chain = []
    visited: set[str] = set()
    queue = [selected_node_id]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        node = nodes_by_id.get(current)
        if node:
            cube_id = node.get("data", {}).get("cube_id", node.get("data", {}).get("cubeDef", {}).get("id", current))
            chain.append(cube_id)
        # Find all upstream nodes
        for e in edges:
            if e.get("target") == current and e.get("source") not in visited:
                queue.append(e["source"])

    chain.reverse()
    return " -> ".join(chain) if len(chain) > 1 else None


@router.post("/interpret")
async def interpret_results(
    body: InterpretRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """One-shot SSE interpretation of a single cube's results.

    No session management — each call is independent. Reuses _agent_turn_stream
    with empty history and the results_interpreter persona. Per D-05.
    """
    client = get_gemini_client()

    # Fetch mission context from DB (per D-08, RESULT-02)
    mission = await _get_mission_context(db, body.workflow_id)

    # Summarize the selected cube's results (cap at 3 rows for LLM prompt)
    result_summary = _summarize_selected_cube(body.execution_results, body.selected_cube_id)

    # Build pipeline string (per D-10)
    pipeline_str = _build_pipeline_str(body.workflow_graph, body.selected_cube_id)

    # Build the single interpret message
    interpret_message = _build_interpret_message(body, mission, result_summary, pipeline_str)

    # Build tool context — interpreter tools may need execution_results
    tool_context = ToolContext(
        db_session=db,
        cube_registry=cube_registry,
        workflow_id=body.workflow_id,
        workflow_graph=body.workflow_graph,
        execution_results=body.execution_results,
    )

    # One-shot: empty history, no session
    history: list[types.Content] = []

    async def event_publisher():
        async for event in _agent_turn_stream(
            client=client,
            history=history,
            new_message=interpret_message,
            persona="results_interpreter",
            tool_context=tool_context,
            request=request,
            session_id=None,
        ):
            if await request.is_disconnected():
                break
            yield ServerSentEvent(
                data=event.model_dump_json(),
                event=event.type,
            )

    return EventSourceResponse(
        event_publisher(),
        ping=15,
        headers={"X-Accel-Buffering": "no"},
    )
