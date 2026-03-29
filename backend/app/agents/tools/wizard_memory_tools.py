"""Working memory tools — let the Build Wizard maintain persistent context across turns.

Three note pads the agent can update at any time:
  - update_mission: What the analyst wants to achieve (evolves as questions are answered)
  - update_investigation: Summary of cube searches and findings
  - update_implementation_plan: Step-by-step plan for the workflow graph
"""

from app.agents.context import ToolContext
from app.agents.registry import agent_tool
from app.agents.sessions import update_working_memory


@agent_tool(
    name="update_mission",
    description=(
        "Update the mission summary — a concise description of what the analyst wants to achieve. "
        "Call this after the analyst's first message and after each clarification that changes "
        "or refines the goal. The content is injected into your context every turn so you "
        "never lose track of the mission. Keep it short (2-5 sentences). "
        "You can overwrite the previous content — always write the full current understanding."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The full mission summary text (overwrites previous).",
            },
        },
        "required": ["content"],
    },
)
async def update_mission(ctx: ToolContext, content: str = "") -> dict:
    """Persist mission notes to session working memory."""
    if ctx.session_id:
        update_working_memory(ctx.session_id, "mission", content)
    return {"status": "saved", "field": "mission"}


@agent_tool(
    name="update_investigation",
    description=(
        "Update the investigation log — a summary of what cubes you found, what searches "
        "you ran, and what the results were. Call this after researching cubes to keep "
        "a record of your findings. The content is injected into your context every turn. "
        "Keep it concise but include: cubes found, their key parameters, and which ones "
        "are relevant. You can overwrite — always write the full current summary."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The full investigation summary text (overwrites previous).",
            },
        },
        "required": ["content"],
    },
)
async def update_investigation(ctx: ToolContext, content: str = "") -> dict:
    """Persist investigation notes to session working memory."""
    if ctx.session_id:
        update_working_memory(ctx.session_id, "investigation", content)
    return {"status": "saved", "field": "investigation"}


@agent_tool(
    name="update_implementation_plan",
    description=(
        "Update the implementation plan — the step-by-step plan for building the workflow graph. "
        "Call this once you have enough information to outline which cubes to use, how to "
        "connect them, and what parameters to set. Update it as the plan evolves. "
        "The content is injected into your context every turn. Keep it structured: "
        "list each cube node, its role, key params, and connections. "
        "You can overwrite — always write the full current plan."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The full implementation plan text (overwrites previous).",
            },
        },
        "required": ["content"],
    },
)
async def update_implementation_plan(ctx: ToolContext, content: str = "") -> dict:
    """Persist implementation plan notes to session working memory."""
    if ctx.session_id:
        update_working_memory(ctx.session_id, "implementation_plan", content)
    return {"status": "saved", "field": "implementation_plan"}
