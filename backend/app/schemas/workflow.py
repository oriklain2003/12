import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class Position(BaseModel):
    x: float
    y: float


class WorkflowNodeData(BaseModel):
    cube_id: str
    params: dict = Field(default_factory=dict)


class WorkflowNode(BaseModel):
    id: str
    type: str = "cube"
    position: Position
    data: WorkflowNodeData


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: str | None = None
    targetHandle: str | None = None


class WorkflowGraph(BaseModel):
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)


class WorkflowCreate(BaseModel):
    name: str = "Untitled Workflow"
    graph_json: WorkflowGraph = Field(default_factory=WorkflowGraph)


class WorkflowUpdate(BaseModel):
    name: str | None = None
    graph_json: WorkflowGraph | None = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    name: str
    graph_json: WorkflowGraph
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
