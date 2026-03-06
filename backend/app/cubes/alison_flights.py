"""AlisonFlightsCube: queries Alison provider aircraft from public schema.

Joins public.aircraft with public.positions to produce per-aircraft summaries.
Outputs a hex_list for downstream filter cubes (squawk_filter, registration_country_filter).
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)

from app.cubes.all_flights import point_in_polygon
from app.cubes.base import BaseCube
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class AlisonFlightsCube(BaseCube):
    """Data source cube querying the Alison provider (public schema).

    Joins public.aircraft with public.positions, aggregates per hex,
    and returns a hex_list for downstream filter cubes.
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
            description="Callsign filter (ILIKE pattern match on positions.flight).",
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
            description="Minimum altitude in feet (filters on positions.alt_baro).",
            required=False,
        ),
        ParamDefinition(
            name="max_altitude",
            type=ParamType.NUMBER,
            description="Maximum altitude in feet (filters on positions.alt_baro).",
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
            name="min_lat",
            type=ParamType.NUMBER,
            description="Bounding box — minimum latitude.",
            required=False,
        ),
        ParamDefinition(
            name="max_lat",
            type=ParamType.NUMBER,
            description="Bounding box — maximum latitude.",
            required=False,
        ),
        ParamDefinition(
            name="min_lon",
            type=ParamType.NUMBER,
            description="Bounding box — minimum longitude.",
            required=False,
        ),
        ParamDefinition(
            name="max_lon",
            type=ParamType.NUMBER,
            description="Bounding box — maximum longitude.",
            required=False,
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
        """Query public.aircraft joined with public.positions and return flight summaries."""
        time_range_seconds = inputs.get("time_range_seconds", 604800)
        start_time = inputs.get("start_time")
        end_time = inputs.get("end_time")
        hex_filter = inputs.get("hex_filter")
        callsign = inputs.get("callsign")
        aircraft_type = inputs.get("aircraft_type")
        min_altitude = inputs.get("min_altitude")
        max_altitude = inputs.get("max_altitude")
        polygon = inputs.get("polygon")
        min_lat = inputs.get("min_lat")
        max_lat = inputs.get("max_lat")
        min_lon = inputs.get("min_lon")
        max_lon = inputs.get("max_lon")

        # Build parameterized SQL using CTE: aggregate positions first, then
        # join aircraft for metadata. This avoids the expensive cross-product
        # of joining 46M positions with 35K aircraft before GROUP BY.
        pos_where: list[str] = []
        aircraft_where: list[str] = []
        params: dict[str, Any] = {}

        # --- Time filters ---
        # p.ts is a timestamp column, so pass datetime objects (not int epochs)
        if start_time is not None and end_time is not None:
            start_dt = datetime.fromtimestamp(int(float(start_time)), tz=timezone.utc)
            end_dt = datetime.fromtimestamp(int(float(end_time)), tz=timezone.utc)
            pos_where.append("ts BETWEEN :start_epoch AND :end_epoch")
            params["start_epoch"] = start_dt
            params["end_epoch"] = end_dt
        else:
            cutoff_epoch = int(time.time()) - int(time_range_seconds or 604800)
            cutoff_dt = datetime.fromtimestamp(cutoff_epoch, tz=timezone.utc)
            pos_where.append("ts >= :cutoff")
            params["cutoff"] = cutoff_dt

        # --- hex_filter ---
        if hex_filter:
            pos_where.append("hex = ANY(:hex_filter)")
            params["hex_filter"] = list(hex_filter)

        # --- callsign ILIKE ---
        if callsign:
            pos_where.append("flight ILIKE :callsign")
            params["callsign"] = f"%{callsign}%"

        # --- aircraft_type ILIKE (applied on aircraft table in outer query) ---
        if aircraft_type:
            aircraft_where.append("a.icao_type ILIKE :aircraft_type")
            params["aircraft_type"] = f"%{aircraft_type}%"

        # --- altitude filters ---
        if min_altitude is not None:
            pos_where.append("alt_baro >= :min_altitude")
            params["min_altitude"] = float(min_altitude)

        if max_altitude is not None:
            pos_where.append("alt_baro <= :max_altitude")
            params["max_altitude"] = float(max_altitude)

        # --- bounding box filters ---
        if all(v is not None for v in [min_lat, max_lat, min_lon, max_lon]):
            pos_where.append(
                "lat BETWEEN :min_lat AND :max_lat AND lon BETWEEN :min_lon AND :max_lon"
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
            poly_lats = [p[0] for p in polygon]
            poly_lons = [p[1] for p in polygon]
            pos_where.append(
                "lat BETWEEN :min_lat AND :max_lat AND lon BETWEEN :min_lon AND :max_lon"
            )
            params.update(
                {
                    "min_lat": min(poly_lats),
                    "max_lat": max(poly_lats),
                    "min_lon": min(poly_lons),
                    "max_lon": max(poly_lons),
                }
            )

        # Build CTE: aggregate positions by hex first (fast scan with filters)
        pos_filter_clause = " AND ".join(pos_where) if pos_where else "TRUE"
        aircraft_filter_clause = (" AND " + " AND ".join(aircraft_where)) if aircraft_where else ""

        sql = f"""
            WITH recent AS (
                SELECT hex,
                       array_agg(DISTINCT flight) FILTER (WHERE flight IS NOT NULL) AS callsigns,
                       MIN(ts) AS first_seen_ts,
                       MAX(ts) AS last_seen_ts,
                       MIN(alt_baro) AS min_alt_baro,
                       MAX(alt_baro) AS max_alt_baro
                FROM public.positions
                WHERE {pos_filter_clause}
                GROUP BY hex
                LIMIT 5000
            )
            SELECT r.hex, a.registration, a.icao_type, a.type_description, a.category,
                   r.callsigns, r.first_seen_ts, r.last_seen_ts, r.min_alt_baro, r.max_alt_baro
            FROM recent r
            JOIN public.aircraft a ON r.hex = a.hex
            WHERE 1=1{aircraft_filter_clause}
        """

        full_sql = sql

        # Debug log with substituted params
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
        logger.info("AlisonFlights query:\n%s", debug_sql)

        async with engine.connect() as conn:
            result = await conn.execute(text(full_sql), params)
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

        # --- Polygon filter (Python-side ray casting, PostGIS not available) ---
        if polygon and len(polygon) >= 3:
            candidate_hexes = [row["hex"] for row in rows]

            if candidate_hexes:
                poly_lats = [p[0] for p in polygon]
                poly_lons = [p[1] for p in polygon]
                bbox_min_lat = min(poly_lats)
                bbox_max_lat = max(poly_lats)
                bbox_min_lon = min(poly_lons)
                bbox_max_lon = max(poly_lons)

                # Fetch positions for candidate hexes within bbox
                async with engine.connect() as conn:
                    pos_result = await conn.execute(
                        text(
                            "SELECT hex, lat, lon "
                            "FROM public.positions "
                            "WHERE hex = ANY(:candidate_hexes) "
                            "AND lat BETWEEN :bbox_min_lat AND :bbox_max_lat "
                            "AND lon BETWEEN :bbox_min_lon AND :bbox_max_lon"
                        ),
                        {
                            "candidate_hexes": candidate_hexes,
                            "bbox_min_lat": bbox_min_lat,
                            "bbox_max_lat": bbox_max_lat,
                            "bbox_min_lon": bbox_min_lon,
                            "bbox_max_lon": bbox_max_lon,
                        },
                    )
                    pos_rows = pos_result.fetchall()

                # Determine which hexes have at least one position inside the polygon
                hexes_in_polygon: set[str] = set()
                for pos_row in pos_rows:
                    hex_addr, lat, lon = pos_row[0], pos_row[1], pos_row[2]
                    if hex_addr in hexes_in_polygon:
                        continue  # early-exit: already confirmed inside
                    if lat is not None and lon is not None:
                        if point_in_polygon(float(lat), float(lon), polygon):
                            hexes_in_polygon.add(hex_addr)

                rows = [row for row in rows if row["hex"] in hexes_in_polygon]

        return {
            "flights": rows,
            "hex_list": [row["hex"] for row in rows],
        }
