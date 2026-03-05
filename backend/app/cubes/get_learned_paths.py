"""GetLearnedPathsCube: queries public.learned_paths with optional filters.

Coordinate order convention:
  - DB stores centerline points as {lat, lon, alt} dicts (lat-first)
  - GeoJSON output uses [lon, lat] order (lon-first, per RFC 7946)
  - Shapely geometries use (x=lon, y=lat) convention

Actual public.learned_paths schema (inspected 2026-03-05):
  id          character varying   — path identifier e.g. "OLBA_LCLK_3_612e2f"
  origin      character varying   — origin airport ICAO code
  destination character varying   — destination airport ICAO code
  centerline  jsonb               — array of {lat, lon, alt} dicts
  width_nm    double precision    — corridor half-width in nautical miles
  member_count integer            — number of constituent flights
  min_alt_ft  double precision    — minimum altitude (may be null)
  max_alt_ft  double precision    — maximum altitude (may be null)
  created_at  timestamp           — creation timestamp
"""

from typing import Any

from shapely.geometry import LineString, mapping
from sqlalchemy import text

from app.cubes.all_flights import point_in_polygon
from app.cubes.base import BaseCube
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class GetLearnedPathsCube(BaseCube):
    """Queries public.learned_paths with optional filters and geometry output."""

    cube_id = "get_learned_paths"
    name = "Get Learned Paths"
    description = "Query learned flight paths with optional filtering and corridor generation"
    category = CubeCategory.DATA_SOURCE

    inputs = [
        ParamDefinition(
            name="origin",
            type=ParamType.STRING,
            description="Filter by origin airport ICAO code (exact match, case-insensitive).",
            required=False,
        ),
        ParamDefinition(
            name="destination",
            type=ParamType.STRING,
            description="Filter by destination airport ICAO code (exact match, case-insensitive).",
            required=False,
        ),
        ParamDefinition(
            name="path_id",
            type=ParamType.STRING,
            description="Filter to a specific path by ID.",
            required=False,
        ),
        ParamDefinition(
            name="polygon",
            type=ParamType.JSON_OBJECT,
            description="Geofence boundary as array of [lat, lon] pairs. Returns paths whose centerline passes through.",
            required=False,
            widget_hint="polygon",
        ),
        ParamDefinition(
            name="min_member_count",
            type=ParamType.NUMBER,
            description="Minimum member_count — filters out low-confidence paths.",
            required=False,
        ),
        ParamDefinition(
            name="output_geometry",
            type=ParamType.STRING,
            description='Output geometry type: "centerline" (GeoJSON LineString) or "corridor" (buffered GeoJSON Polygon). Default: centerline.',
            required=False,
            default="centerline",
        ),
        ParamDefinition(
            name="width_override",
            type=ParamType.NUMBER,
            description="Override corridor width in nautical miles. If not set, uses the path's width_nm value.",
            required=False,
        ),
    ]

    outputs = [
        ParamDefinition(
            name="paths",
            type=ParamType.JSON_OBJECT,
            description="Array of path objects with id, origin, destination, geometry, width_nm, member_count.",
        ),
        ParamDefinition(
            name="path_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Array of path ID strings for downstream cubes.",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Query learned_paths with optional filters and return paths with geometry."""
        origin = inputs.get("origin")
        destination = inputs.get("destination")
        path_id = inputs.get("path_id")
        polygon = inputs.get("polygon")
        min_member_count = inputs.get("min_member_count")
        output_geometry = inputs.get("output_geometry") or "centerline"
        width_override = inputs.get("width_override")

        # Build parameterized SQL
        sql_parts = [
            """
            SELECT
                id, origin, destination, centerline, width_nm, member_count,
                min_alt_ft, max_alt_ft
            FROM public.learned_paths
            WHERE 1=1
            """
        ]
        params: dict[str, Any] = {}

        if origin:
            sql_parts.append("AND origin ILIKE :origin")
            params["origin"] = origin

        if destination:
            sql_parts.append("AND destination ILIKE :destination")
            params["destination"] = destination

        if path_id:
            sql_parts.append("AND id = :path_id")
            params["path_id"] = path_id

        if min_member_count is not None:
            sql_parts.append("AND member_count >= :min_member_count")
            params["min_member_count"] = int(min_member_count)

        # Safety cap
        sql_parts.append("LIMIT 2000")

        full_sql = "\n".join(sql_parts)

        async with engine.connect() as conn:
            result = await conn.execute(text(full_sql), params)
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

        # Polygon filter (Python-side ray casting — PostGIS not available on Tracer 42 RDS)
        if polygon and len(polygon) >= 3:
            filtered_rows = []
            for row in rows:
                centerline_pts = row.get("centerline") or []
                # Keep path if any centerline point falls inside the polygon
                inside = False
                for pt in centerline_pts:
                    lat = pt.get("lat")
                    lon = pt.get("lon")
                    if lat is not None and lon is not None:
                        if point_in_polygon(float(lat), float(lon), polygon):
                            inside = True
                            break
                if inside:
                    filtered_rows.append(row)
            rows = filtered_rows

        # Build output rows with geometry
        output_rows = []
        for row in rows:
            centerline_pts = row.get("centerline") or []

            # Parse centerline coordinates from {lat, lon, alt} dicts
            coords = []
            for pt in centerline_pts:
                lat = pt.get("lat")
                lon = pt.get("lon")
                if lat is not None and lon is not None:
                    coords.append((float(lat), float(lon)))

            # Skip paths with fewer than 2 points (cannot form geometry)
            if len(coords) < 2:
                continue

            # Generate geometry based on output_geometry mode
            if output_geometry == "corridor":
                # Use Shapely to buffer the centerline into a corridor polygon
                # Shapely uses (x=lon, y=lat) convention
                shapely_coords = [(lon, lat) for lat, lon in coords]
                line = LineString(shapely_coords)

                # Width: prefer width_override, fall back to DB value
                width_nm = float(width_override) if width_override is not None else (row.get("width_nm") or 2.0)
                # 1 NM ≈ 1/60 degree; divide by 2 for half-width on each side
                buffer_deg = (width_nm / 2.0) / 60.0
                polygon_geom = line.buffer(buffer_deg, cap_style="flat", join_style="round")
                geometry = dict(mapping(polygon_geom))
            else:
                # Default: centerline mode — GeoJSON LineString
                # GeoJSON uses [lon, lat] order per RFC 7946
                geojson_coords = [[lon, lat] for lat, lon in coords]
                geometry = {
                    "type": "LineString",
                    "coordinates": geojson_coords,
                }

            output_row = {
                "id": row["id"],
                "origin": row["origin"],
                "destination": row["destination"],
                "geometry": geometry,
                "width_nm": row.get("width_nm"),
                "member_count": row.get("member_count"),
                "min_alt_ft": row.get("min_alt_ft"),
                "max_alt_ft": row.get("max_alt_ft"),
            }
            output_rows.append(output_row)

        return {
            "paths": output_rows,
            "path_ids": [r["id"] for r in output_rows],
        }
