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
from app.agents.schemas import AgentChatRequest, AgentSSEEvent
from app.agents.sessions import get_or_create_session, update_session, get_session_persona
from app.agents.skills_loader import get_system_prompt
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


async def _agent_turn_stream(
    client,
    history: list[types.Content],
    new_message: str,
    persona: str,
    tool_context: ToolContext,
    request: Request,
) -> AsyncGenerator[AgentSSEEvent, None]:
    """One agent turn: stream text, handle tool calls, resume streaming.

    Implements the manual tool dispatch loop per research Pattern 2.
    AFC is disabled so we detect function calls manually.
    """
    # Build system prompt from skills
    system_prompt = get_system_prompt(persona)

    # Build tool declarations
    tool_decls = _build_tool_declarations()

    # Configure Gemini call
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=[types.Tool(function_declarations=tool_decls)] if tool_decls else None,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    # Add new user message to history
    history.append(
        types.Content(role="user", parts=[types.Part(text=new_message)])
    )

    # Prune history if needed before calling Gemini
    prune_history(history)

    model_name = settings.gemini_flash_model

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

            # Stream text tokens
            if chunk.text:
                streamed_text += chunk.text
                yield AgentSSEEvent(type="text", data=chunk.text)

            # Detect tool calls
            if chunk.function_calls:
                tool_call_detected = True
                for fc in chunk.function_calls:
                    yield AgentSSEEvent(
                        type="tool_call",
                        data={"name": fc.name, "args": dict(fc.args) if fc.args else {}},
                    )

                    # Execute tool
                    result = await dispatch_tool(fc.name, dict(fc.args) if fc.args else {}, tool_context)

                    yield AgentSSEEvent(
                        type="tool_result",
                        data={"name": fc.name, "result": result},
                    )

                    # Append model's function call to history
                    history.append(types.Content(
                        role="model",
                        parts=[types.Part.from_function_call(
                            name=fc.name,
                            args=dict(fc.args) if fc.args else {},
                        )]
                    ))

                    # Append tool result to history
                    history.append(types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(
                            name=fc.name,
                            response=result,
                        )]
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
    )

    async def event_publisher():
        # First event: session ID so client can reuse it
        yield ServerSentEvent(
            data=json.dumps({"session_id": session_id}),
            event="session",
        )

        async for event in _agent_turn_stream(
            client=client,
            history=history,
            new_message=body.message,
            persona=body.persona,
            tool_context=tool_context,
            request=request,
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
