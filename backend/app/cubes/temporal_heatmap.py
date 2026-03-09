"""TemporalHeatmapCube: aggregates flight activity by time buckets to reveal operational tempo."""

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class TemporalHeatmapCube(BaseCube):
    """Aggregates flight activity by hour-of-day or day-of-week time buckets."""

    cube_id = "temporal_heatmap"
    name = "Temporal Heatmap"
    description = "Aggregate flight activity by time buckets (hour-of-day or day-of-week) to reveal operational tempo patterns"
    category = CubeCategory.AGGREGATION

    inputs = [
        ParamDefinition(
            name="flights",
            type=ParamType.JSON_OBJECT,
            required=True,
            accepts_full_result=True,
            description="Array of flight objects with first_seen_ts (epoch seconds).",
        ),
        ParamDefinition(
            name="granularity",
            type=ParamType.STRING,
            default="hourly",
            widget_hint="select",
            description='Time bucket granularity: "hourly" (hour of day) or "daily" (day of week).',
        ),
    ]

    outputs = [
        ParamDefinition(
            name="buckets",
            type=ParamType.JSON_OBJECT,
            description="Array of time bucket objects with counts.",
        ),
        ParamDefinition(
            name="peak",
            type=ParamType.JSON_OBJECT,
            description="The bucket with highest activity.",
        ),
        ParamDefinition(
            name="total_flights",
            type=ParamType.NUMBER,
            description="Total flights analyzed.",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        flights = inputs.get("flights")
        granularity = inputs.get("granularity", "hourly")

        # Extract flights from full_result wrapping
        if isinstance(flights, dict):
            if "flights" in flights:
                flights = flights["flights"]
            elif "filtered_flights" in flights:
                flights = flights["filtered_flights"]
            else:
                # Fallback: grab first list value
                flights = next((v for v in flights.values() if isinstance(v, list)), [])

        if not flights:
            return {"buckets": [], "peak": None, "total_flights": 0}

        # Parse timestamps and count by bucket
        counter: Counter = Counter()
        for flight in flights:
            ts = flight.get("first_seen_ts")
            if ts is None:
                continue
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            if granularity == "daily":
                counter[dt.weekday()] += 1
            else:
                counter[dt.hour] += 1

        if not counter:
            return {"buckets": [], "peak": None, "total_flights": 0}

        # Build bucket objects
        if granularity == "daily":
            buckets = sorted(
                [{"day": day, "day_name": DAY_NAMES[day], "count": count} for day, count in counter.items()],
                key=lambda b: b["day"],
            )
        else:
            buckets = sorted(
                [{"hour": hour, "count": count} for hour, count in counter.items()],
                key=lambda b: b["hour"],
            )

        peak = max(buckets, key=lambda b: b["count"])
        total_flights = sum(b["count"] for b in buckets)

        return {"buckets": buckets, "peak": peak, "total_flights": total_flights}
