"""Pydantic models for agent API requests and SSE events."""

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
