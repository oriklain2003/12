"""GetPlaneCourse cube: returns aircraft track points or LineStrings from Alison (public.positions)."""

import collections
import logging
from typing import Any

logger = logging.getLogger("flow.cubes.get_plane_course")

from sqlalchemy import text

from app.cubes.base import BaseCube
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class GetPlaneCourseCube(BaseCube):
    """Returns aircraft track data from public.positions (Alison) as GeoJSON points or lines."""

    cube_id = "get_plane_course"
    name = "Get Plane Course"
    description = "Get aircraft track points or lines from Alison (public.positions)"
    category = CubeCategory.DATA_SOURCE

    inputs = [
        ParamDefinition(
            name="hex_list",
            type=ParamType.LIST_OF_STRINGS,
            description="ICAO24 hex addresses to query.",
            required=True,
        ),
        ParamDefinition(
            name="lookback_hours",
            type=ParamType.NUMBER,
            description="How far back to search for positions (hours). Default: 24.",
            required=False,
            default=24,
        ),
        ParamDefinition(
            name="output_mode",
            type=ParamType.STRING,
            description='Output mode: "points" (one row per track point) or "lines" (one row per aircraft as LineString).',
            required=False,
            default="points",
            widget_hint="select",
            options=["points", "lines"],
        ),
    ]

    outputs = [
        ParamDefinition(
            name="tracks",
            type=ParamType.JSON_OBJECT,
            description="Array of track data rows (GeoJSON geometry included).",
        ),
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Unique hex addresses present in the results.",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Query public.positions and return GeoJSON points or linestrings."""
        raw_ids = inputs.get("hex_list") or []
        if isinstance(raw_ids, str):
            raw_ids = [s.strip() for s in raw_ids.split(",") if s.strip()]
        hex_list: list[str] = list(raw_ids)
        output_mode: str = inputs.get("output_mode") or "points"
        lookback_hours: float = float(inputs.get("lookback_hours") or 24)

        logger.info(
            "GetPlaneCourse hex_list=%r output_mode=%s lookback_hours=%s",
            hex_list, output_mode, lookback_hours,
        )

        if not hex_list:
            logger.info("GetPlaneCourse: hex_list is empty, returning early")
            return {"tracks": [], "flight_ids": []}

        import time
        cutoff_epoch = int(time.time() - lookback_hours * 3600)

        sql = """
            SELECT hex AS flight_id,
                   EXTRACT(EPOCH FROM ts)::bigint AS timestamp,
                   lat, lon,
                   alt_baro AS alt,
                   gs AS gspeed,
                   baro_rate AS vspeed,
                   NULL::float AS track,
                   squawk,
                   flight AS callsign,
                   'alison' AS source
            FROM public.positions
            WHERE hex = ANY(:hex_list)
              AND ts >= to_timestamp(:cutoff)
            ORDER BY hex, ts
        """

        async with engine.connect() as conn:
            result = await conn.execute(
                text(sql), {"hex_list": hex_list, "cutoff": cutoff_epoch}
            )
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

        if output_mode == "lines":
            return _build_lines(rows)
        else:
            return _build_points(rows)


def _build_points(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Add GeoJSON Point geometry to each row; skip rows without valid lat/lon."""
    output_rows = []
    for row in rows:
        lat = row.get("lat")
        lon = row.get("lon")
        if lat is None or lon is None:
            continue
        row_out = dict(row)
        row_out["geometry"] = {"type": "Point", "coordinates": [float(lon), float(lat)]}
        output_rows.append(row_out)

    unique_ids = list(dict.fromkeys(r["flight_id"] for r in output_rows))
    return {"tracks": output_rows, "flight_ids": unique_ids}


def _build_lines(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group rows by hex and build GeoJSON LineString per aircraft."""
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[row["flight_id"]].append(row)

    lines = []
    for flight_id, pts in groups.items():
        valid_pts = [p for p in pts if p.get("lat") is not None and p.get("lon") is not None]
        if len(valid_pts) < 2:
            continue

        coords = [[float(p["lon"]), float(p["lat"])] for p in valid_pts]
        first_pt = valid_pts[0]

        alt_values = [float(p["alt"]) for p in valid_pts if p.get("alt") is not None]
        lines.append(
            {
                "flight_id": flight_id,
                "callsign": first_pt.get("callsign"),
                "geometry": {"type": "LineString", "coordinates": coords},
                "start_time": first_pt.get("timestamp"),
                "end_time": valid_pts[-1].get("timestamp"),
                "min_alt": min(alt_values) if alt_values else None,
                "max_alt": max(alt_values) if alt_values else None,
            }
        )

    return {"tracks": lines, "flight_ids": [line["flight_id"] for line in lines]}
