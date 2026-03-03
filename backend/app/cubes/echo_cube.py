"""EchoCube: echoes its input value back as output."""

from typing import Any

from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class EchoCube(BaseCube):
    """A simple cube that echoes its input value back as output."""

    cube_id = "echo"
    name = "Echo"
    description = "Echoes its input value back as output"
    category = CubeCategory.OUTPUT
    inputs = [
        ParamDefinition(
            name="value",
            type=ParamType.STRING,
            description="Value to echo",
        )
    ]
    outputs = [
        ParamDefinition(
            name="result",
            type=ParamType.STRING,
            description="Echoed value",
        )
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        return {"result": inputs.get("value", "")}
