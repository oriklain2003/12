"""Agent tool registry — decorator-based registration mirroring CubeRegistry pattern."""

import functools
import logging
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass
class RegisteredTool:
    """A tool registered for agent use."""

    name: str
    description: str
    parameters_schema: dict  # JSON Schema dict for Gemini FunctionDeclaration
    fn: Callable  # The async function to call


_tools: dict[str, RegisteredTool] = {}


def agent_tool(name: str, description: str, parameters_schema: dict):
    """Decorator: register an async function as an agent tool.

    Args:
        name: Tool name (used by Gemini to call the function)
        description: Human-readable description for Gemini's tool selection
        parameters_schema: JSON Schema dict defining expected parameters.
            Keep flat (no nested $defs) to avoid Gemini schema rejection.

    Usage:
        @agent_tool(
            name="list_cubes_summary",
            description="List all available cubes with names and descriptions",
            parameters_schema={"type": "object", "properties": {}}
        )
        async def list_cubes_summary(ctx: ToolContext) -> dict:
            ...
    """

    def decorator(fn: Callable) -> Callable:
        _tools[name] = RegisteredTool(
            name=name,
            description=description,
            parameters_schema=parameters_schema,
            fn=fn,
        )
        log.debug("Registered agent tool: %s", name)

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


def get_tool(name: str) -> RegisteredTool | None:
    """Look up a registered tool by name."""
    return _tools.get(name)


def get_all_tools() -> dict[str, RegisteredTool]:
    """Return all registered tools."""
    return dict(_tools)


def get_gemini_tool_declarations() -> list[dict]:
    """Return Gemini-compatible FunctionDeclaration dicts for all registered tools.

    These are used to construct google.genai.types.Tool objects.
    Conversion to actual types.FunctionDeclaration happens in the router
    to avoid importing google.genai in this module.
    """
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters_schema,
        }
        for t in _tools.values()
    ]


# Alias for plan-declared export name
def get_all_tool_declarations() -> list[dict]:
    """Alias for get_gemini_tool_declarations — returns all tool declarations."""
    return get_gemini_tool_declarations()
