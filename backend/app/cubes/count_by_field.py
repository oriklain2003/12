"""CountByField cube: groups any data array by a field and returns {value, count} sorted desc."""

from typing import Any

import pandas as pd

from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class CountByFieldCube(BaseCube):
    """Aggregates a data array by grouping on a specified field, returning sorted counts."""

    cube_id = "count_by_field"
    name = "Count By Field"
    description = "Group any data array by a field and count occurrences, sorted by count descending"
    category = CubeCategory.AGGREGATION

    inputs = [
        ParamDefinition(
            name="data",
            type=ParamType.JSON_OBJECT,
            required=True,
            accepts_full_result=True,
            description="Array of row objects to group — also accepts Full Result.",
        ),
        ParamDefinition(
            name="group_by_field",
            type=ParamType.STRING,
            required=True,
            description="Field name to group by.",
        ),
    ]

    outputs = [
        ParamDefinition(
            name="counts",
            type=ParamType.JSON_OBJECT,
            description="Array of {value, count} objects sorted by count descending.",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Group data by field and return sorted counts."""
        data = inputs.get("data")
        group_by_field = inputs.get("group_by_field", "")

        # Guard: no data or field
        if not data or not group_by_field:
            return {"counts": []}

        # Handle full_result dict input — extract first list value
        if isinstance(data, dict):
            data = next((v for v in data.values() if isinstance(v, list)), [])

        if not data:
            return {"counts": []}

        df = pd.DataFrame(data)

        if group_by_field not in df.columns:
            return {"counts": []}

        grouped = (
            df.groupby(group_by_field, dropna=False)
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )

        counts = [
            {"value": str(row[group_by_field]), "count": int(row["count"])}
            for _, row in grouped.iterrows()
        ]

        return {"counts": counts}
