"""AllFlights cube: queries Tracer 42 research.flight_metadata with optional filters."""

import logging
import time
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)

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
            widget_hint="relative_time",
        ),
        ParamDefinition(
            name="start_time",
            type=ParamType.STRING,
            description="Absolute start time as epoch seconds string. Overrides relative if provided.",
            required=False,
            widget_hint="datetime",
        ),
        ParamDefinition(
            name="end_time",
            type=ParamType.STRING,
            description="Absolute end time as epoch seconds string.",
            required=False,
            widget_hint="datetime",
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
            widget_hint="polygon",
        ),
        ParamDefinition(
            name="airport",
            type=ParamType.STRING,
            description="Airport code filter (ILIKE — matches origin or destination).",
            required=False,
        ),
        ParamDefinition(
            name="min_lat",
            type=ParamType.NUMBER,
            description="Region bounding box — minimum latitude.",
            required=False,
        ),
        ParamDefinition(
            name="max_lat",
            type=ParamType.NUMBER,
            description="Region bounding box — maximum latitude.",
            required=False,
        ),
        ParamDefinition(
            name="min_lon",
            type=ParamType.NUMBER,
            description="Region bounding box — minimum longitude.",
            required=False,
        ),
        ParamDefinition(
            name="max_lon",
            type=ParamType.NUMBER,
            description="Region bounding box — maximum longitude.",
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
        # airport and bounding-box filters extracted inline below

        # Build parameterized SQL
        sql_parts = [
            """
            SELECT
                flight_id, callsign, airline, airline_code, first_seen_ts, last_seen_ts,
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

        # airport filter (ILIKE on origin or destination)
        airport = inputs.get("airport")
        if airport:
            sql_parts.append("AND (origin_airport ILIKE :airport OR destination_airport ILIKE :airport)")
            params["airport"] = f"%{airport}%"

        # bounding-box region filter
        min_lat = inputs.get("min_lat")
        max_lat = inputs.get("max_lat")
        min_lon = inputs.get("min_lon")
        max_lon = inputs.get("max_lon")
        if all(v is not None for v in [min_lat, max_lat, min_lon, max_lon]):
            sql_parts.append(
                "AND start_lat BETWEEN :min_lat AND :max_lat AND start_lon BETWEEN :min_lon AND :max_lon"
            )
            params.update(
                {
                    "min_lat": float(min_lat),
                    "max_lat": float(max_lat),
                    "min_lon": float(min_lon),
                    "max_lon": float(max_lon),
                }
            )
        elif polygon and len(polygon) >= 3:
            # Auto-derive bounding box from polygon to narrow flight_metadata candidates
            poly_lats = [p[0] for p in polygon]
            poly_lons = [p[1] for p in polygon]
            sql_parts.append(
                "AND start_lat BETWEEN :min_lat AND :max_lat AND start_lon BETWEEN :min_lon AND :max_lon"
            )
            params.update(
                {
                    "min_lat": min(poly_lats),
                    "max_lat": max(poly_lats),
                    "min_lon": min(poly_lons),
                    "max_lon": max(poly_lons),
                }
            )

        # Safety cap before polygon filtering
        sql_parts.append("LIMIT 5000")

        full_sql = "\n".join(sql_parts)

        # Log the executable query for debugging — substitute params inline
        debug_sql = full_sql
        for k, v in params.items():
            placeholder = f":{k}"
            if isinstance(v, str):
                debug_sql = debug_sql.replace(placeholder, f"'{v}'")
            elif isinstance(v, list):
                formatted = ", ".join(f"'{x}'" if isinstance(x, str) else str(x) for x in v)
                debug_sql = debug_sql.replace(placeholder, f"ARRAY[{formatted}]")
            else:
                debug_sql = debug_sql.replace(placeholder, str(v))
        logger.info("AllFlights query:\n%s", debug_sql)

        async with engine.connect() as conn:
            result = await conn.execute(text(full_sql), params)
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

        # Polygon filter (Python-side ray casting — PostGIS not available)
        if polygon and len(polygon) >= 3:
            candidate_ids = [row["flight_id"] for row in rows]

            if candidate_ids:
                # Derive bounding box from polygon for SQL pre-filter
                poly_lats = [p[0] for p in polygon]
                poly_lons = [p[1] for p in polygon]
                bbox_min_lat = min(poly_lats)
                bbox_max_lat = max(poly_lats)
                bbox_min_lon = min(poly_lons)
                bbox_max_lon = max(poly_lons)

                async with engine.connect() as conn:
                    track_result = await conn.execute(
                        text(
                            "SELECT flight_id, lat, lon "
                            "FROM research.normal_tracks "
                            "WHERE flight_id = ANY(:ids) "
                            "AND lat BETWEEN :bbox_min_lat AND :bbox_max_lat "
                            "AND lon BETWEEN :bbox_min_lon AND :bbox_max_lon"
                        ),
                        {
                            "ids": candidate_ids,
                            "bbox_min_lat": bbox_min_lat,
                            "bbox_max_lat": bbox_max_lat,
                            "bbox_min_lon": bbox_min_lon,
                            "bbox_max_lon": bbox_max_lon,
                        },
                    )
                    track_rows = track_result.fetchall()

                # Build set of flight_ids that have a point inside polygon
                # Early-exit: skip remaining points once a flight is confirmed
                flights_in_polygon: set[str] = set()
                for track_row in track_rows:
                    fid, lat, lon = track_row[0], track_row[1], track_row[2]
                    if fid in flights_in_polygon:
                        continue
                    if lat is not None and lon is not None:
                        if point_in_polygon(float(lat), float(lon), polygon):
                            flights_in_polygon.add(fid)

                rows = [row for row in rows if row["flight_id"] in flights_in_polygon]

        return {
            "flights": rows,
            "flight_ids": [row["flight_id"] for row in rows],
        }
