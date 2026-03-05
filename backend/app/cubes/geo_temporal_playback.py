"""GeoTemporalPlayback cube: passthrough visualization cube for animated geo-temporal data."""

from typing import Any

from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class GeoTemporalPlaybackCube(BaseCube):
    """Visualization cube that animates geo-temporal data on a map with timeline controls.

    This is a passthrough cube — data flows through unchanged. The frontend
    reads the widget="geo_playback" field and renders the GeoPlaybackWidget
    instead of the default table+map results panel.
    """

    cube_id = "geo_temporal_playback"
    name = "Geo-Temporal Playback"
    description = "Animate geo-temporal data on a map with timeline controls"
    category = CubeCategory.OUTPUT
    widget = "geo_playback"

    inputs = [
        ParamDefinition(
            name="data",
            type=ParamType.JSON_OBJECT,
            required=True,
            accepts_full_result=True,
            description="The dataset to visualize. Accepts full result bundle from any cube.",
        ),
        ParamDefinition(
            name="geometry_column",
            type=ParamType.STRING,
            required=True,
            default="geometry",
            description="Column containing GeoJSON geometry (Point, LineString, etc.).",
        ),
        ParamDefinition(
            name="timestamp_column",
            type=ParamType.STRING,
            required=True,
            default="timestamp",
            description="Column containing timestamp values for animation timeline.",
        ),
        ParamDefinition(
            name="id_column",
            type=ParamType.STRING,
            required=False,
            description="Column to identify distinct objects (used for color assignment per track).",
        ),
        ParamDefinition(
            name="color_by_column",
            type=ParamType.STRING,
            required=False,
            description="Column for grouping colors (overrides id_column for coloring if provided).",
        ),
    ]

    outputs = [
        ParamDefinition(
            name="data",
            type=ParamType.JSON_OBJECT,
            description="Passthrough of input data (visualization-only cube).",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Passthrough — visualization happens entirely on the frontend.

        Returns the input data unchanged so downstream cubes can chain off it
        if needed.
        """
        data = inputs.get("data", [])
        # Passthrough — visualization happens on frontend
        return {"data": data}
