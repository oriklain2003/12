"""AllFlights cube: queries Tracer 42 research.flight_metadata with optional filters."""

import time
from typing import Any

from sqlalchemy import text

from app.cubes.base import BaseCube
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


def point_in_polygon(lat: float, lon: float, polygon: list[list[float]]) -> bool:
    """Ray-casting algorithm to determine if a point is inside a polygon.

    Args:
        lat: Point latitude.
        lon: Point longitude.
        polygon: List of [lat, lon] coordinate pairs forming a closed polygon.

    Returns:
        True if the point is inside (or on edge of) the polygon.
    """
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    j = n - 1

    for i in range(n):
        lat_i, lon_i = polygon[i][0], polygon[i][1]
        lat_j, lon_j = polygon[j][0], polygon[j][1]

        # Check if ray from point crosses this edge
        if (lon_i > lon) != (lon_j > lon):
            # Compute intersection x of ray with edge
            intersect_lat = lat_j + (lon - lon_j) / (lon_i - lon_j) * (lat_i - lat_j)
            if lat < intersect_lat:
                inside = not inside

        j = i

    return inside


class AllFlightsCube(BaseCube):
    """Queries flight metadata from the Tracer 42 research schema."""

    cube_id = "all_flights"
    name = "All Flights"
    description = "Query flight metadata from Tracer 42 database"
    category = CubeCategory.DATA_SOURCE

    inputs = [
        ParamDefinition(
            name="time_range_seconds",
            type=ParamType.NUMBER,
            description="Relative time filter — last N seconds. Default: 604800 (7 days).",
            required=False,
            default=604800,
        ),
        ParamDefinition(
            name="start_time",
            type=ParamType.STRING,
            description="Absolute start time as epoch seconds string. Overrides relative if provided.",
            required=False,
        ),
        ParamDefinition(
            name="end_time",
            type=ParamType.STRING,
            description="Absolute end time as epoch seconds string.",
            required=False,
        ),
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Filter to specific flight IDs.",
            required=False,
        ),
        ParamDefinition(
            name="callsign",
            type=ParamType.STRING,
            description="Callsign filter (ILIKE pattern match).",
            required=False,
        ),
        ParamDefinition(
            name="min_altitude",
            type=ParamType.NUMBER,
            description="Minimum altitude in feet. Filters flights where min_altitude_ft >= this value.",
            required=False,
        ),
        ParamDefinition(
            name="max_altitude",
            type=ParamType.NUMBER,
            description="Maximum altitude in feet. Filters flights where max_altitude_ft <= this value.",
            required=False,
        ),
        ParamDefinition(
            name="polygon",
            type=ParamType.JSON_OBJECT,
            description="Array of [lat, lon] coordinate pairs defining a geofence boundary.",
            required=False,
        ),
    ]

    outputs = [
        ParamDefinition(
            name="flights",
            type=ParamType.JSON_OBJECT,
            description="Array of flight record objects.",
        ),
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Array of flight_id strings for downstream cubes.",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Query flight_metadata with optional filters and return rows + flight_id list."""
        time_range_seconds = inputs.get("time_range_seconds", 604800)
        start_time = inputs.get("start_time")
        end_time = inputs.get("end_time")
        flight_ids_filter = inputs.get("flight_ids")
        callsign = inputs.get("callsign")
        min_altitude = inputs.get("min_altitude")
        max_altitude = inputs.get("max_altitude")
        polygon = inputs.get("polygon")

        # Build parameterized SQL
        sql_parts = [
            """
            SELECT
                flight_id, callsign, first_seen_ts, last_seen_ts,
                min_altitude_ft, max_altitude_ft,
                origin_airport, destination_airport,
                is_anomaly, is_military,
                start_lat, start_lon, end_lat, end_lon
            FROM research.flight_metadata
            WHERE 1=1
            """
        ]
        params: dict[str, Any] = {}

        # Time filters
        if start_time is not None and end_time is not None:
            # Absolute range
            start_epoch = int(float(start_time))
            end_epoch = int(float(end_time))
            sql_parts.append(
                "AND first_seen_ts <= :end_epoch AND last_seen_ts >= :start_epoch"
            )
            params["start_epoch"] = start_epoch
            params["end_epoch"] = end_epoch
        else:
            # Relative range
            cutoff = int(time.time()) - int(time_range_seconds or 604800)
            sql_parts.append("AND last_seen_ts >= :cutoff")
            params["cutoff"] = cutoff

        # flight_ids filter
        if flight_ids_filter:
            sql_parts.append("AND flight_id = ANY(:flight_ids_filter)")
            params["flight_ids_filter"] = list(flight_ids_filter)

        # callsign filter (ILIKE)
        if callsign:
            sql_parts.append("AND callsign ILIKE :callsign")
            params["callsign"] = f"%{callsign}%"

        # altitude filters
        if min_altitude is not None:
            sql_parts.append("AND min_altitude_ft >= :min_altitude")
            params["min_altitude"] = float(min_altitude)

        if max_altitude is not None:
            sql_parts.append("AND max_altitude_ft <= :max_altitude")
            params["max_altitude"] = float(max_altitude)

        # Safety cap before polygon filtering
        sql_parts.append("LIMIT 5000")

        full_sql = "\n".join(sql_parts)

        async with engine.connect() as conn:
            result = await conn.execute(text(full_sql), params)
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

        # Polygon filter (Python-side ray casting — PostGIS not available)
        if polygon and len(polygon) >= 3:
            # Get flight_ids of flights with track points inside polygon
            candidate_ids = [row["flight_id"] for row in rows]

            if candidate_ids:
                async with engine.connect() as conn:
                    track_result = await conn.execute(
                        text(
                            "SELECT DISTINCT flight_id, lat, lon "
                            "FROM research.normal_tracks "
                            "WHERE flight_id = ANY(:ids)"
                        ),
                        {"ids": candidate_ids},
                    )
                    track_rows = track_result.fetchall()

                # Build set of flight_ids that have a point inside polygon
                flights_in_polygon: set[str] = set()
                for track_row in track_rows:
                    fid, lat, lon = track_row[0], track_row[1], track_row[2]
                    if lat is not None and lon is not None:
                        if point_in_polygon(float(lat), float(lon), polygon):
                            flights_in_polygon.add(fid)

                rows = [row for row in rows if row["flight_id"] in flights_in_polygon]

        return {
            "flights": rows,
            "flight_ids": [row["flight_id"] for row in rows],
        }
