"""Execution event schemas for SSE streaming workflow execution."""

from typing import Any, Literal

from pydantic import BaseModel


class CubeStatusEvent(BaseModel):
    """A per-cube status event emitted during workflow execution.

    Emitted by stream_graph and serialized to JSON for SSE transmission.

    Statuses:
    - pending:  Cube is queued but not yet started.
    - running:  Cube execution has started.
    - done:     Cube executed successfully; outputs and truncated flag included.
    - error:    Cube raised an exception; error message included.
    - skipped:  Cube was not executed because an upstream cube failed.
    """

    node_id: str
    status: Literal["pending", "running", "done", "error", "skipped"]
    outputs: dict[str, Any] | None = None
    truncated: bool | None = None
    error: str | None = None
    reason: str | None = None  # for skipped: why it was skipped
