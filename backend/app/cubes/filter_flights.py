"""FilterFlightsCube: behavioral filter sitting between AllFlights and downstream cubes.

Two-tier filtering strategy:
  Tier 1 — metadata only (first_seen_ts / last_seen_ts from full_result): duration range
  Tier 2 — SQL aggregate on research.normal_tracks: altitude and speed thresholds
  Polygon — bounding-box SQL pre-filter + Python ray-casting (same pattern as AllFlights)

Flights with no track data in normal_tracks are always excluded.
Only flights passing ALL active thresholds are included (AND logic).
"""

import logging
from typing import Any

from sqlalchemy import text

from app.cubes.all_flights import point_in_polygon
from app.cubes.base import BaseCube
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType

logger = logging.getLogger(__name__)


class FilterFlightsCube(BaseCube):
    """Behavioral filter for flight metadata — bridges AllFlights to analysis cubes."""

    cube_id = "filter_flights"
    name = "Filter Flights"
    description = (
        "Filter a set of flights by duration, altitude, speed, and/or geofence. "
        "Accepts the full result from AllFlights and applies AND logic across all active thresholds."
    )
    category = CubeCategory.FILTER

    inputs = [
        ParamDefinition(
            name="full_result",
            type=ParamType.JSON_OBJECT,
            required=False,
            accepts_full_result=True,
            description="Full result bundle from AllFlights (contains 'flights' and 'flight_ids' keys).",
        ),
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            required=False,
            description="Direct list of flight_ids. Used as fallback when full_result is not connected.",
        ),
        ParamDefinition(
            name="max_altitude_ft",
            type=ParamType.NUMBER,
            required=False,
            description="Exclude flights whose MAX(alt) in normal_tracks exceeds this value (feet).",
        ),
        ParamDefinition(
            name="min_speed_knots",
            type=ParamType.NUMBER,
            required=False,
            description="Exclude flights that never reach this speed — MAX(gspeed) must be >= threshold.",
        ),
        ParamDefinition(
            name="max_speed_knots",
            type=ParamType.NUMBER,
            required=False,
            description="Exclude flights that exceed this speed — MAX(gspeed) must be <= threshold.",
        ),
        ParamDefinition(
            name="min_duration_minutes",
            type=ParamType.NUMBER,
            required=False,
            description="Exclude flights shorter than this duration (computed from first/last seen timestamps).",
        ),
        ParamDefinition(
            name="max_duration_minutes",
            type=ParamType.NUMBER,
            required=False,
            description="Exclude flights longer than this duration (computed from first/last seen timestamps).",
        ),
        ParamDefinition(
            name="polygon",
            type=ParamType.JSON_OBJECT,
            required=False,
            widget_hint="polygon",
            description="Geofence as [[lat, lon], ...] array. Flights must have at least one track point inside.",
        ),
    ]

    outputs = [
        ParamDefinition(
            name="filtered_flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Flight IDs that passed all active filters.",
        ),
        ParamDefinition(
            name="filtered_flights",
            type=ParamType.JSON_OBJECT,
            description="Subset of the input flight metadata records that passed all filters.",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Apply two-tier filtering and return surviving flights."""

        # ----------------------------------------------------------------
        # Step 1: Extract flights and flight_ids from inputs
        # ----------------------------------------------------------------
        full_result = inputs.get("full_result")
        direct_flight_ids = inputs.get("flight_ids")

        flights_metadata: list[dict] = []
        if full_result and isinstance(full_result, dict):
            flights_metadata = full_result.get("flights") or []
            flight_ids_list: list[str] = full_result.get("flight_ids") or [
                f["flight_id"] for f in flights_metadata if "flight_id" in f
            ]
        elif direct_flight_ids:
            flight_ids_list = list(direct_flight_ids)
        else:
            return {"filtered_flight_ids": [], "filtered_flights": []}

        if not flight_ids_list:
            return {"filtered_flight_ids": [], "filtered_flights": []}

        # Build an index for quick metadata lookup
        metadata_index: dict[str, dict] = {f["flight_id"]: f for f in flights_metadata if "flight_id" in f}

        # Working set of surviving flight IDs
        passing_ids: set[str] = set(flight_ids_list)

        # ----------------------------------------------------------------
        # Step 2: Tier 1 — duration filter (metadata, no DB query)
        # ----------------------------------------------------------------
        min_duration_minutes = inputs.get("min_duration_minutes")
        max_duration_minutes = inputs.get("max_duration_minutes")

        if min_duration_minutes is not None or max_duration_minutes is not None:
            surviving: set[str] = set()
            for fid in passing_ids:
                flight = metadata_index.get(fid)
                if flight is None:
                    # No metadata — cannot compute duration, exclude
                    continue
                first_seen = flight.get("first_seen_ts")
                last_seen = flight.get("last_seen_ts")
                if first_seen is None or last_seen is None:
                    # Missing timestamps — exclude
                    continue
                duration_minutes = (last_seen - first_seen) / 60.0
                if min_duration_minutes is not None and duration_minutes < min_duration_minutes:
                    continue
                if max_duration_minutes is not None and duration_minutes > max_duration_minutes:
                    continue
                surviving.add(fid)
            passing_ids = surviving

        # Early exit if nothing survived Tier 1
        if not passing_ids:
            return {"filtered_flight_ids": [], "filtered_flights": []}

        # ----------------------------------------------------------------
        # Step 3: Tier 2 — track data confirmation + altitude/speed filters
        # ----------------------------------------------------------------
        max_altitude_ft = inputs.get("max_altitude_ft")
        min_speed_knots = inputs.get("min_speed_knots")
        max_speed_knots = inputs.get("max_speed_knots")

        has_track_filters = any(v is not None for v in [max_altitude_ft, min_speed_knots, max_speed_knots])

        if has_track_filters:
            # Run GROUP BY aggregate query to get per-flight max_alt and max_speed
            query = text(
                """
                SELECT flight_id, MAX(alt) AS max_alt, MAX(gspeed) AS max_speed
                FROM research.normal_tracks
                WHERE flight_id = ANY(:flight_ids)
                GROUP BY flight_id
                """
            )
            ids_list = list(passing_ids)
            logger.info(
                "FilterFlights Tier 2 query: GROUP BY on %d flight_ids (max_alt=%s, min_speed=%s, max_speed=%s)",
                len(ids_list),
                max_altitude_ft,
                min_speed_knots,
                max_speed_knots,
            )
            async with engine.connect() as conn:
                result = await conn.execute(query, {"flight_ids": ids_list})
                rows = result.fetchall()

            # Build stats dict keyed by flight_id
            track_stats: dict[str, dict] = {}
            for row in rows:
                fid, max_alt, max_speed = row[0], row[1], row[2]
                track_stats[fid] = {"max_alt": max_alt, "max_speed": max_speed}

            # Apply filters — flights missing from track_stats have no track data (exclude)
            surviving = set()
            for fid in passing_ids:
                stats = track_stats.get(fid)
                if stats is None:
                    # No track data — exclude
                    continue
                if max_altitude_ft is not None and (stats["max_alt"] or 0) > max_altitude_ft:
                    continue
                if min_speed_knots is not None and (stats["max_speed"] or 0) < min_speed_knots:
                    continue
                if max_speed_knots is not None and (stats["max_speed"] or 0) > max_speed_knots:
                    continue
                surviving.add(fid)
            passing_ids = surviving

        else:
            # No altitude/speed filters — still need to confirm track data exists
            query = text(
                "SELECT DISTINCT flight_id FROM research.normal_tracks WHERE flight_id = ANY(:ids)"
            )
            ids_list = list(passing_ids)
            logger.info(
                "FilterFlights track presence check: %d flight_ids", len(ids_list)
            )
            async with engine.connect() as conn:
                result = await conn.execute(query, {"ids": ids_list})
                rows = result.fetchall()

            flights_with_tracks: set[str] = {row[0] for row in rows}
            passing_ids = passing_ids & flights_with_tracks

        # Early exit if nothing survived Tier 2
        if not passing_ids:
            return {"filtered_flight_ids": [], "filtered_flights": []}

        # ----------------------------------------------------------------
        # Step 4: Polygon filter (if polygon provided with >= 3 points)
        # ----------------------------------------------------------------
        polygon = inputs.get("polygon")

        if polygon and len(polygon) >= 3:
            # Bounding box pre-filter
            poly_lats = [p[0] for p in polygon]
            poly_lons = [p[1] for p in polygon]
            bbox_min_lat = min(poly_lats)
            bbox_max_lat = max(poly_lats)
            bbox_min_lon = min(poly_lons)
            bbox_max_lon = max(poly_lons)

            ids_list = list(passing_ids)
            logger.info(
                "FilterFlights polygon query: %d flight_ids, bbox=[%.4f,%.4f,%.4f,%.4f]",
                len(ids_list),
                bbox_min_lat,
                bbox_max_lat,
                bbox_min_lon,
                bbox_max_lon,
            )

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
                        "ids": ids_list,
                        "bbox_min_lat": bbox_min_lat,
                        "bbox_max_lat": bbox_max_lat,
                        "bbox_min_lon": bbox_min_lon,
                        "bbox_max_lon": bbox_max_lon,
                    },
                )
                track_rows = track_result.fetchall()

            # Ray-casting: flight passes if ANY point is inside polygon (early-exit per flight)
            flights_in_polygon: set[str] = set()
            for track_row in track_rows:
                fid, lat, lon = track_row[0], track_row[1], track_row[2]
                if fid in flights_in_polygon:
                    continue  # Already confirmed — skip remaining points
                if lat is not None and lon is not None:
                    if point_in_polygon(float(lat), float(lon), polygon):
                        flights_in_polygon.add(fid)

            passing_ids = passing_ids & flights_in_polygon

        # ----------------------------------------------------------------
        # Step 5: Build output — filter original metadata down to passing_ids
        # ----------------------------------------------------------------
        filtered_flight_ids = list(passing_ids)
        filtered_flights = [metadata_index[fid] for fid in filtered_flight_ids if fid in metadata_index]

        return {
            "filtered_flight_ids": filtered_flight_ids,
            "filtered_flights": filtered_flights,
        }
