"""Tool dispatcher — executes tool calls from Gemini and handles errors."""

import asyncio
import logging
from typing import Any

from app.agents.context import ToolContext
from app.agents.registry import get_tool

log = logging.getLogger(__name__)

MAX_RETRIES = 1  # retry once on transient errors per D-06


async def dispatch_tool(
    tool_name: str,
    tool_args: dict[str, Any],
    ctx: ToolContext,
) -> dict[str, Any]:
    """Execute a registered tool by name with given arguments.

    Per D-06: retry once for transient errors, then return error message
    as tool result so Gemini can reason about it.

    Per D-07: ToolContext is injected as first argument to the tool function.

    Args:
        tool_name: Name of the registered tool to call
        tool_args: Arguments from Gemini's function call
        ctx: ToolContext with db_session, cube_registry, workflow_id

    Returns:
        Dict with tool result. On error: {"error": "description"}.
    """
    tool = get_tool(tool_name)
    if tool is None:
        log.warning("Unknown tool requested: %s", tool_name)
        return {"error": f"Unknown tool: {tool_name}"}

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = await tool.fn(ctx, **tool_args)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            last_error = exc
            log.warning(
                "Tool %s attempt %d failed: %s",
                tool_name,
                attempt + 1,
                exc,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(0.5)  # Brief pause before retry

    # All retries exhausted — return error as tool result per D-06
    error_msg = f"Tool '{tool_name}' failed after {MAX_RETRIES + 1} attempts: {last_error}"
    log.error(error_msg)
    return {"error": error_msg}
