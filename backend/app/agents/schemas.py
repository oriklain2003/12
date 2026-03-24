"""Pydantic models for agent API requests and SSE events."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """Request body for POST /api/agent/chat."""
    message: str = Field(..., min_length=1, description="User message text")
    session_id: str | None = Field(None, description="Existing session ID, or None to create new")
    persona: str = Field("canvas_agent", description="Agent persona to use")
    workflow_id: str | None = Field(None, description="Workflow ID for context")


class AgentSSEEvent(BaseModel):
    """Typed SSE event sent during agent chat stream."""
    type: str  # "text" | "tool_call" | "tool_result" | "thinking" | "done" | "session"
    data: str | dict | None = None


class MissionContext(BaseModel):
    """Mission context stored in workflow metadata."""
    intent: str = ""
    parameters: dict = Field(default_factory=dict)
    created_by: str = ""
    created_at: str = ""


# ---------------------------------------------------------------------------
# Validation schemas (per D-01, D-15, D-16)
# ---------------------------------------------------------------------------

class ValidationIssue(BaseModel):
    """A single validation issue found in a workflow graph."""
    severity: str  # "error" | "warning"
    node_id: str | None = None  # null for graph-level issues like cycles
    cube_name: str | None = None
    param_name: str | None = None
    message: str  # Pre-written template message (per D-15)
    rule: str  # Machine-readable: "missing_required_param", "dangling_source_handle",
               # "dangling_target_handle", "type_mismatch", "orphan_node", "cycle", "unknown_cube"


class ValidationRequest(BaseModel):
    """Request body for POST /api/agent/validate."""
    graph: "WorkflowGraph"


class ValidationResponse(BaseModel):
    """Response from POST /api/agent/validate."""
    issues: list[ValidationIssue] = []

    @property
    def has_errors(self) -> bool:
        """Return True if any issue has severity='error'."""
        return any(i.severity == "error" for i in self.issues)


# Deferred import to avoid circular dependency
from app.schemas.workflow import WorkflowGraph  # noqa: E402
ValidationRequest.model_rebuild()
