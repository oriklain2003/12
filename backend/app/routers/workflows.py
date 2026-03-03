"""Workflows router: full CRUD endpoints for workflow management."""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette import EventSourceResponse, ServerSentEvent
from starlette.requests import Request

from app.database import get_db
from app.engine.executor import execute_graph, stream_graph, topological_sort
from app.models.workflow import Workflow
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowGraph,
    WorkflowResponse,
    WorkflowUpdate,
)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _to_response(wf: Workflow) -> WorkflowResponse:
    """Convert a Workflow ORM instance to WorkflowResponse.

    The graph_json column stores a plain dict (JSONB). We explicitly
    construct WorkflowGraph from it to ensure proper Pydantic validation.
    """
    graph = WorkflowGraph.model_validate(wf.graph_json)
    return WorkflowResponse(
        id=wf.id,
        name=wf.name,
        graph_json=graph,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    body: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    """Create a new workflow."""
    wf = Workflow(
        id=uuid.uuid4(),
        name=body.name,
        graph_json=body.graph_json.model_dump(),
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return _to_response(wf)


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    db: AsyncSession = Depends(get_db),
) -> list[WorkflowResponse]:
    """List all workflows ordered by most recently updated."""
    result = await db.execute(select(Workflow).order_by(Workflow.updated_at.desc()))
    workflows = result.scalars().all()
    return [_to_response(wf) for wf in workflows]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    """Get a specific workflow by ID."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _to_response(wf)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    body: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    """Update a workflow's name and/or graph."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if body.name is not None:
        wf.name = body.name
    if body.graph_json is not None:
        wf.graph_json = body.graph_json.model_dump()

    # Set updated_at manually since onupdate may not trigger on attribute mutation
    wf.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(wf)
    return _to_response(wf)


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete a workflow by ID."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    await db.delete(wf)
    await db.commit()
    return {"detail": "Workflow deleted"}


@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Execute a workflow graph and return per-node results.

    Returns a dict keyed by node_id with status, outputs, and truncated flag.
    Returns 400 if the graph contains a cycle.
    Returns 404 if the workflow is not found.
    """
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    graph = WorkflowGraph.model_validate(wf.graph_json)

    # HTTPException (400 for cycle) propagates naturally through FastAPI
    try:
        return await execute_graph(graph)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{workflow_id}/run/stream")
async def stream_workflow(
    workflow_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Stream workflow execution progress as Server-Sent Events.

    Yields one 'cube_status' SSE event per cube state transition:
    pending (all nodes up-front), then running/done/error/skipped per node.

    Returns 400 if the graph contains a cycle (before SSE stream starts).
    Returns 404 if the workflow is not found.
    """
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    graph = WorkflowGraph.model_validate(wf.graph_json)

    # Validate graph BEFORE starting SSE so we can still return HTTP error codes
    try:
        topological_sort(graph.nodes, graph.edges)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def event_publisher():
        async for event in stream_graph(graph, request):
            yield ServerSentEvent(
                data=event.model_dump_json(exclude_none=True),
                event="cube_status",
            )

    return EventSourceResponse(
        event_publisher(),
        ping=15,
        headers={"X-Accel-Buffering": "no"},
    )
