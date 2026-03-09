"""SetOperations cube: pure Python set math on LIST_OF_STRINGS parameters."""

from typing import Any

from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class SetOperationsCube(BaseCube):
    """Performs intersection, union, or difference on sets of string IDs."""

    cube_id = "set_operations"
    name = "Set Operations"
    description = "Set math (intersection, union, difference) on lists of IDs"
    category = CubeCategory.FILTER

    inputs = [
        ParamDefinition(
            name="set_a",
            type=ParamType.LIST_OF_STRINGS,
            description="First set of IDs",
            required=True,
        ),
        ParamDefinition(
            name="set_b",
            type=ParamType.LIST_OF_STRINGS,
            description="Second set of IDs",
            required=True,
        ),
        ParamDefinition(
            name="set_c",
            type=ParamType.LIST_OF_STRINGS,
            description="Optional third set for 3-way operations",
            required=False,
        ),
        ParamDefinition(
            name="operation",
            type=ParamType.STRING,
            description="Set operation: intersection, union, or difference (A minus B)",
            required=False,
            default="intersection",
            widget_hint="select",
        ),
    ]

    outputs = [
        ParamDefinition(
            name="result",
            type=ParamType.LIST_OF_STRINGS,
            description="Resulting set of IDs",
        ),
        ParamDefinition(
            name="count",
            type=ParamType.NUMBER,
            description="Number of IDs in result",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Apply set operation on input lists and return sorted result."""
        set_a = set(inputs.get("set_a") or [])
        set_b = set(inputs.get("set_b") or [])
        set_c_raw = inputs.get("set_c")
        operation = inputs.get("operation") or "intersection"

        if operation == "intersection":
            result = set_a & set_b
        elif operation == "union":
            result = set_a | set_b
        elif operation == "difference":
            result = set_a - set_b
        else:
            raise ValueError(f"Unknown operation: {operation!r}. Use intersection, union, or difference.")

        # Apply third set if provided
        if set_c_raw is not None:
            set_c = set(set_c_raw)
            if operation == "intersection":
                result = result & set_c
            elif operation == "union":
                result = result | set_c
            elif operation == "difference":
                result = result - set_c

        sorted_result = sorted(result)
        return {
            "result": sorted_result,
            "count": len(sorted_result),
        }
