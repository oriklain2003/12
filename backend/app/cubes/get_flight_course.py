"""GetFlightCourse cube: returns flight track points or LineStrings from normal_tracks."""

import collections
import logging
from typing import Any

logger = logging.getLogger("flow.cubes.get_flight_course")

from sqlalchemy import text

from app.cubes.base import BaseCube
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class GetFlightCourseCube(BaseCube):
    """Returns flight track data from research.normal_tracks as GeoJSON points or lines."""

    cube_id = "get_flight_course"
    name = "Get Flight Course"
    description = "Get flight track points or lines from normal_tracks"
    category = CubeCategory.DATA_SOURCE

    inputs = [
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Flight IDs to query.",
            required=True,
        ),
        ParamDefinition(
            name="output_mode",
            type=ParamType.STRING,
            description='Output mode: "points" (one row per track point) or "lines" (one row per flight as LineString).',
            required=True,
            default="points",
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
            description="Unique flight IDs present in the results.",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Query normal_tracks and return GeoJSON points or linestrings."""
        raw_ids = inputs.get("flight_ids") or []
        if isinstance(raw_ids, str):
            raw_ids = [s.strip() for s in raw_ids.split(",") if s.strip()]
        flight_ids: list[str] = list(raw_ids)
        output_mode: str = inputs.get("output_mode") or "points"

        logger.info("GetFlightCourse raw_ids=%r flight_ids=%r output_mode=%s", raw_ids, flight_ids, output_mode)

        # Guard empty flight_ids early to avoid PostgreSQL ANY() error with empty array
        if not flight_ids:
            logger.info("GetFlightCourse: flight_ids is empty, returning early")
            return {"tracks": [], "flight_ids": []}

        sql = """
            SELECT flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source
            FROM research.normal_tracks
            WHERE flight_id = ANY(:flight_ids)
            ORDER BY flight_id, timestamp
        """

        async with engine.connect() as conn:
            result = await conn.execute(text(sql), {"flight_ids": list(flight_ids)})
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
    """Group rows by flight_id and build GeoJSON LineString per flight."""
    # Group by flight_id preserving ORDER BY flight_id, timestamp from SQL
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[row["flight_id"]].append(row)

    lines = []
    for flight_id, pts in groups.items():
        # Filter to rows with valid coordinates
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
