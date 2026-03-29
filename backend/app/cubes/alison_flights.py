"""AlisonFlightsCube: queries Alison provider aircraft from public schema.

Queries public.aircraft (35K rows) using last_seen for time filtering.
Only joins public.positions when callsign/altitude/polygon filters are provided.
Outputs a hex_list for downstream filter cubes.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)

from app.cubes.all_flights import point_in_polygon
from app.cubes.base import BaseCube
from app.cubes.utils.time_utils import validate_datetime_pair
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class AlisonFlightsCube(BaseCube):
    """Data source cube querying the Alison provider (public schema).

    Queries public.aircraft with last_seen time filter. Only touches
    positions when callsign/altitude/polygon filters require it.
    Returns hex_list for downstream cubes.
    """

    cube_id = "alison_flights"
    name = "Alison Flights"
    description = "Query aircraft from the Alison provider (public schema)"
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
            description="Absolute start time as epoch seconds string. Overrides relative if provided with end_time.",
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
            name="hex_filter",
            type=ParamType.LIST_OF_STRINGS,
            description="Filter to specific ICAO24 hex addresses.",
            required=False,
        ),
        ParamDefinition(
            name="callsign",
            type=ParamType.STRING,
            description="Callsign filter (ILIKE pattern match on positions.flight). Requires positions join.",
            required=False,
        ),
        ParamDefinition(
            name="aircraft_type",
            type=ParamType.STRING,
            description="Aircraft ICAO type code filter (ILIKE match on aircraft.icao_type).",
            required=False,
        ),
        ParamDefinition(
            name="min_altitude",
            type=ParamType.NUMBER,
            description="Minimum altitude in feet (filters on positions.alt_baro). Requires positions join.",
            required=False,
        ),
        ParamDefinition(
            name="max_altitude",
            type=ParamType.NUMBER,
            description="Maximum altitude in feet (filters on positions.alt_baro). Requires positions join.",
            required=False,
        ),
        ParamDefinition(
            name="polygon",
            type=ParamType.JSON_OBJECT,
            description="Array of [lat, lon] coordinate pairs defining a geofence boundary.",
            required=False,
            widget_hint="polygon",
        ),
    ]

    outputs = [
        ParamDefinition(
            name="flights",
            type=ParamType.JSON_OBJECT,
            description="Array of aircraft record objects (one per ICAO24 hex).",
        ),
        ParamDefinition(
            name="hex_list",
            type=ParamType.LIST_OF_STRINGS,
            description="ICAO24 hex addresses for downstream filter cubes.",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Query public.aircraft, optionally joining positions for advanced filters."""
        time_range_seconds = inputs.get("time_range_seconds", 604800)
        start_time = inputs.get("start_time")
        end_time = inputs.get("end_time")

        # ENHANCE-03: Partial datetime validation (per D-08, D-09)
        err = validate_datetime_pair(start_time, end_time)
        if err:
            return {**err, "flights": [], "hex_list": []}

        hex_filter = inputs.get("hex_filter")
        callsign = inputs.get("callsign")
        aircraft_type = inputs.get("aircraft_type")
        min_altitude = inputs.get("min_altitude")
        max_altitude = inputs.get("max_altitude")
        polygon = inputs.get("polygon")

        params: dict[str, Any] = {}

        # Time filter on aircraft.last_seen
        if start_time is not None and end_time is not None:
            ts_start = datetime.fromtimestamp(int(float(start_time)), tz=timezone.utc)
            ts_end = datetime.fromtimestamp(int(float(end_time)), tz=timezone.utc)
            params["ts_start"] = ts_start
            params["ts_end"] = ts_end
            time_clause = "a.last_seen BETWEEN :ts_start AND :ts_end"
        else:
            cutoff_epoch = int(time.time()) - int(time_range_seconds or 604800)
            params["cutoff"] = datetime.fromtimestamp(cutoff_epoch, tz=timezone.utc)
            time_clause = "a.last_seen >= :cutoff"

        # Check if we need to join positions (expensive)
        needs_positions = bool(callsign or min_altitude is not None or max_altitude is not None or (polygon and len(polygon) >= 3))

        # Aircraft WHERE clauses
        where: list[str] = [time_clause]
        if hex_filter:
            where.append("a.hex = ANY(:hex_filter)")
            params["hex_filter"] = list(hex_filter)
        if aircraft_type:
            where.append("a.icao_type ILIKE :aircraft_type")
            params["aircraft_type"] = f"%{aircraft_type}%"

        if not needs_positions:
            # Fast path: aircraft-only query
            where_sql = " AND ".join(where)
            sql = f"""
                SELECT a.hex, a.registration, a.icao_type, a.type_description, a.category
                FROM public.aircraft a
                WHERE {where_sql}
                LIMIT 50000
            """
        else:
            # Slow path: join positions for callsign/altitude/polygon filters
            # Build positions time filter
            if start_time is not None and end_time is not None:
                pos_time = "p.ts BETWEEN :ts_start AND :ts_end"
            else:
                pos_time = "p.ts >= :cutoff"

            pos_where: list[str] = [pos_time]
            if callsign:
                pos_where.append("p.flight ILIKE :callsign")
                params["callsign"] = f"%{callsign}%"
            if min_altitude is not None:
                pos_where.append("p.alt_baro >= :min_altitude")
                params["min_altitude"] = float(min_altitude)
            if max_altitude is not None:
                pos_where.append("p.alt_baro <= :max_altitude")
                params["max_altitude"] = float(max_altitude)
            if polygon and len(polygon) >= 3:
                poly_lats = [pt[0] for pt in polygon]
                poly_lons = [pt[1] for pt in polygon]
                pos_where.append(
                    "p.lat BETWEEN :poly_min_lat AND :poly_max_lat "
                    "AND p.lon BETWEEN :poly_min_lon AND :poly_max_lon"
                )
                params.update({
                    "poly_min_lat": min(poly_lats),
                    "poly_max_lat": max(poly_lats),
                    "poly_min_lon": min(poly_lons),
                    "poly_max_lon": max(poly_lons),
                })

            pos_filter = " AND ".join(pos_where)
            where_sql = " AND ".join(where)

            # Use EXISTS to check if aircraft has matching positions
            # without exploding rows — much faster than JOIN
            sql = f"""
                SELECT a.hex, a.registration, a.icao_type, a.type_description, a.category
                FROM public.aircraft a
                WHERE {where_sql}
                  AND EXISTS (
                      SELECT 1 FROM public.positions p
                      WHERE p.hex = a.hex AND {pos_filter}
                  )
                LIMIT 50000
            """

        debug_sql = sql
        for k, v in params.items():
            placeholder = f":{k}"
            if isinstance(v, str):
                debug_sql = debug_sql.replace(placeholder, f"'{v}'")
            elif isinstance(v, list):
                formatted = ", ".join(f"'{x}'" if isinstance(x, str) else str(x) for x in v)
                debug_sql = debug_sql.replace(placeholder, f"ARRAY[{formatted}]")
            else:
                debug_sql = debug_sql.replace(placeholder, str(v))
        logger.info("AlisonFlights query:\n%s", debug_sql)

        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

        # Polygon post-filter (Python ray-casting) for precise boundary check
        if polygon and len(polygon) >= 3 and rows:
            candidate_hexes = [row["hex"] for row in rows]
            async with engine.connect() as conn:
                pos_result = await conn.execute(
                    text(
                        "SELECT hex, lat, lon "
                        "FROM public.positions "
                        "WHERE hex = ANY(:candidate_hexes) "
                        "AND lat BETWEEN :poly_min_lat AND :poly_max_lat "
                        "AND lon BETWEEN :poly_min_lon AND :poly_max_lon"
                    ),
                    {
                        "candidate_hexes": candidate_hexes,
                        "poly_min_lat": params["poly_min_lat"],
                        "poly_max_lat": params["poly_max_lat"],
                        "poly_min_lon": params["poly_min_lon"],
                        "poly_max_lon": params["poly_max_lon"],
                    },
                )
                pos_rows = pos_result.fetchall()

            hexes_in_polygon: set[str] = set()
            for pos_row in pos_rows:
                hex_addr, lat, lon = pos_row[0], pos_row[1], pos_row[2]
                if hex_addr in hexes_in_polygon:
                    continue
                if lat is not None and lon is not None:
                    if point_in_polygon(float(lat), float(lon), polygon):
                        hexes_in_polygon.add(hex_addr)

            rows = [row for row in rows if row["hex"] in hexes_in_polygon]

        return {
            "flights": rows,
            "hex_list": [row["hex"] for row in rows],
        }
