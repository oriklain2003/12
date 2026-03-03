"""AddNumbersCube: adds two numbers together."""

from typing import Any

from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class AddNumbersCube(BaseCube):
    """A cube that adds two numeric inputs together."""

    cube_id = "add_numbers"
    name = "Add Numbers"
    description = "Adds two numbers together"
    category = CubeCategory.ANALYSIS
    inputs = [
        ParamDefinition(
            name="a",
            type=ParamType.NUMBER,
            description="First number",
        ),
        ParamDefinition(
            name="b",
            type=ParamType.NUMBER,
            description="Second number",
        ),
    ]
    outputs = [
        ParamDefinition(
            name="sum",
            type=ParamType.NUMBER,
            description="Sum of a and b",
        )
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        return {"sum": float(inputs.get("a", 0)) + float(inputs.get("b", 0))}
