"""Catalog tools — two-tier cube catalog for agent use.

These are placeholder implementations. Phase 19 (Cube Expert) will add
full logic. The tools are registered now so the infrastructure can be
tested end-to-end.
"""

from app.agents.context import ToolContext
from app.agents.registry import agent_tool


@agent_tool(
    name="list_cubes_summary",
    description="List all available cubes grouped by category, showing only names and short descriptions. Use this first to discover what cubes exist.",
    parameters_schema={
        "type": "object",
        "properties": {},
    },
)
async def list_cubes_summary(ctx: ToolContext) -> dict:
    """Return cube catalog summaries grouped by category."""
    if ctx.cube_registry is None:
        return {"error": "Cube registry not available"}
    catalog = ctx.cube_registry.catalog()
    grouped: dict[str, list[dict]] = {}
    for cube_def in catalog:
        cat = (
            cube_def.category.value
            if hasattr(cube_def.category, "value")
            else str(cube_def.category)
        )
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(
            {
                "cube_id": cube_def.cube_id,
                "name": cube_def.name,
                "description": cube_def.description,
            }
        )
    return {"categories": grouped}


@agent_tool(
    name="get_cube_definition",
    description="Get the full definition of a specific cube including all input and output parameters with types and constraints. Call this after list_cubes_summary to get details on a specific cube.",
    parameters_schema={
        "type": "object",
        "properties": {
            "cube_name": {
                "type": "string",
                "description": "The cube_id to look up (e.g., 'all_flights', 'squawk_filter')",
            },
        },
        "required": ["cube_name"],
    },
)
async def get_cube_definition(ctx: ToolContext, cube_name: str = "") -> dict:
    """Return full cube definition with parameters."""
    if ctx.cube_registry is None:
        return {"error": "Cube registry not available"}
    cube = ctx.cube_registry.get(cube_name)
    if cube is None:
        return {"error": f"Cube '{cube_name}' not found in catalog"}
    defn = cube.definition
    return {
        "cube_id": defn.cube_id,
        "name": defn.name,
        "description": defn.description,
        "category": (
            defn.category.value
            if hasattr(defn.category, "value")
            else str(defn.category)
        ),
        "inputs": [p.model_dump() for p in defn.inputs],
        "outputs": [p.model_dump() for p in defn.outputs],
    }
