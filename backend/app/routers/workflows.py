"""Workflows router: full CRUD endpoints for workflow management."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
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
