"""Cube Expert sub-agent -- reasons about cube selection via dedicated Gemini call.

Internal Python class only -- never an HTTP endpoint (per D-12).
Receives only a task description string -- not orchestrator history (per D-13).
Uses gemini-2.5-flash model (per D-10).
"""

import logging
from google.genai import types

from app.agents.client import get_gemini_client
from app.agents.context import ToolContext
from app.agents.dispatcher import dispatch_tool
from app.agents.registry import get_gemini_tool_declarations
from app.agents.skills_loader import get_system_prompt
from app.config import settings

log = logging.getLogger(__name__)


class CubeExpert:
    """Sub-agent that reasons about cube selection using a dedicated Gemini call.

    Downstream agents (Canvas, Build) instantiate this directly.
    Never exposed as an HTTP endpoint (per D-12).
    """

    async def ask(self, task: str, ctx: ToolContext) -> str:
        """Ask the Cube Expert which cube fits the described task.

        Args:
            task: Natural language description of what the user wants to do.
            ctx: ToolContext with cube_registry for tool dispatch.

        Returns:
            Plain text recommendation string from the expert.
        """
        client = get_gemini_client()
        system_prompt = get_system_prompt("cube_expert")

        # Build tool declarations from global registry
        raw_tools = get_gemini_tool_declarations()
        tool_decls = [
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=t["parameters"],
            )
            for t in raw_tools
        ]

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[types.Tool(function_declarations=tool_decls)] if tool_decls else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        # Single user message — task description only (per D-13)
        history = [types.Content(role="user", parts=[types.Part(text=task)])]

        # Non-streaming tool dispatch loop (adapted from router.py streaming pattern)
        max_rounds = 10
        for _ in range(max_rounds):
            response = await client.aio.models.generate_content(
                model=settings.gemini_flash_model,
                contents=history,
                config=config,
            )

            # Check for function calls in response
            fc_list = []
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        fc_list.append(part.function_call)

            if not fc_list:
                # Text response — done
                return response.text or ""

            # Execute tools and append results to history
            history.append(response.candidates[0].content)
            for fc in fc_list:
                result = await dispatch_tool(
                    fc.name, dict(fc.args) if fc.args else {}, ctx
                )
                history.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(
                        name=fc.name, response=result
                    )],
                ))

        return ""  # Safety fallback if loop exhausts
