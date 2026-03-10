"""AreaSpatialFilterCube: dual-provider polygon spatial filter with movement classification.

Supports two data providers:
- FR provider: queries research.normal_tracks (identifier: flight_id, bigint timestamp)
- Alison provider: queries public.positions (identifier: hex, timestamptz ts)

For each input flight, determines whether any positions fall inside a user-drawn polygon,
computes entry/exit times and duration, and classifies movement as:
  - landing:  flight descended into the area and touched down (on_ground transition or low alt + descending)
  - takeoff:  flight departed from within the area (on_ground transition or low alt + ascending)
  - cruise:   flight transited the area at altitude (default when no landing/takeoff signals)

Coordinate conventions:
- Polygon input: [[lat, lon], ...] (aviation/user convention, same as PolygonMapWidget)
- Shapely/GeoJSON: (lon, lat) i.e. (x, y) — conversion happens at Shapely boundary only
"""

import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

import shapely
from shapely.geometry import Polygon
from sqlalchemy import text

from app.cubes.base import BaseCube
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType

logger = logging.getLogger(__name__)

# Vertical speed threshold for FR classification (ft/min).
# |vspeed| > this value indicates significant climb/descent.
VSPEED_THRESHOLD_FT_MIN = 300


def classify_movement_alison(
    positions_in_area: list[dict[str, Any]],
    altitude_threshold_ft: float,
) -> str:
    """Classify movement from Alison position sequence within polygon.

    Args:
        positions_in_area: Temporally ordered positions with valid lat/lon that are
            inside the polygon. May include on_ground=True rows without lat/lon.
        altitude_threshold_ft: Altitude (feet) below which landing/takeoff is considered.

    Priority:
        1. on_ground transitions (most reliable — False->True = landing, True->False = takeoff)
        2. alt_baro + baro_rate fallback
        3. Default: "cruise"
    """
    # Priority 1: Check on_ground transitions
    for i in range(1, len(positions_in_area)):
        prev_g = positions_in_area[i - 1].get("on_ground")
        curr_g = positions_in_area[i].get("on_ground")
        if prev_g is False and curr_g is True:
            return "landing"
        if prev_g is True and curr_g is False:
            return "takeoff"

    # Priority 2: Fall back to altitude + baro_rate
    alts = [p["alt_baro"] for p in positions_in_area if p.get("alt_baro") is not None]
    rates = [p["baro_rate"] for p in positions_in_area if p.get("baro_rate") is not None]

    if alts and max(alts) < altitude_threshold_ft:
        avg_rate = sum(rates) / len(rates) if rates else 0
        if avg_rate < -VSPEED_THRESHOLD_FT_MIN:
            return "landing"
        if avg_rate > VSPEED_THRESHOLD_FT_MIN:
            return "takeoff"

    return "cruise"


def classify_movement_fr(
    positions_in_area: list[dict[str, Any]],
    altitude_threshold_ft: float,
) -> str:
    """Classify movement from FR track sequence within polygon.

    No on_ground column available — infer from alt + vspeed.

    Args:
        positions_in_area: Temporally ordered positions inside the polygon.
        altitude_threshold_ft: Altitude (feet) below which landing/takeoff is considered.
    """
    alts = [p["alt"] for p in positions_in_area if p.get("alt") is not None]
    vspeeds = [p["vspeed"] for p in positions_in_area if p.get("vspeed") is not None]

    if not alts:
        return "cruise"  # no altitude data — ambiguous, default to cruise

    avg_alt = sum(alts) / len(alts)
    avg_vspeed = sum(vspeeds) / len(vspeeds) if vspeeds else 0

    if avg_alt < altitude_threshold_ft:
        if avg_vspeed < -VSPEED_THRESHOLD_FT_MIN:
            return "landing"
        if avg_vspeed > VSPEED_THRESHOLD_FT_MIN:
            return "takeoff"

    return "cruise"


class AreaSpatialFilterCube(BaseCube):
    """Filter flights to only those that passed through a user-drawn polygon area.

    Returns filtered flight IDs with per-flight entry/exit times, duration, and
    movement classification (landing, takeoff, or cruise).
    """

    cube_id = "area_spatial_filter"
    name = "Area Spatial Filter"
    description = (
        "Filter flights to those that passed through a drawn polygon area. "
        "Computes entry/exit times, duration, and movement classification "
        "(landing, takeoff, cruise) for each matching flight. "
        "Supports FR and Alison providers."
    )
    category = CubeCategory.FILTER

    inputs = [
        ParamDefinition(
            name="full_result",
            type=ParamType.JSON_OBJECT,
            required=False,
            accepts_full_result=True,
            description=(
                "Full result bundle from upstream cube "
                "(contains 'flight_ids' key for FR, 'hex_list' key for Alison)."
            ),
        ),
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            required=False,
            description=(
                "Direct list of flight IDs for FR provider. "
                "Used as fallback when full_result is not connected."
            ),
        ),
        ParamDefinition(
            name="hex_list",
            type=ParamType.LIST_OF_STRINGS,
            required=False,
            description=(
                "Direct list of hex (ICAO24) identifiers for Alison provider. "
                "Used as fallback when full_result is not connected."
            ),
        ),
        ParamDefinition(
            name="provider",
            type=ParamType.STRING,
            required=False,
            default="fr",
            widget_hint="select",
            description=(
                "Data provider to query. "
                "Options: 'fr' (research.normal_tracks, uses flight_ids) or "
                "'alison' (public.positions, uses hex_list)."
            ),
        ),
        ParamDefinition(
            name="polygon",
            type=ParamType.JSON_OBJECT,
            required=False,
            widget_hint="polygon",
            description=(
                "Polygon vertices as [[lat, lon], ...] defining the area of interest. "
                "Can be drawn on the map widget or connected from an upstream cube."
            ),
        ),
        ParamDefinition(
            name="altitude_threshold",
            type=ParamType.NUMBER,
            required=False,
            default=1000,
            description=(
                "Altitude threshold in feet. Flights with average altitude below this "
                "value in the polygon area are candidates for landing/takeoff "
                "classification. Default: 1000ft."
            ),
        ),
        ParamDefinition(
            name="time_window_hours",
            type=ParamType.NUMBER,
            required=False,
            default=24,
            description=(
                "How far back to search for positions (hours). "
                "Only used with Alison provider. Default: 24 hours."
            ),
        ),
    ]

    outputs = [
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description=(
                "IDs of flights confirmed inside the polygon — "
                "flight_id for FR provider, hex for Alison provider."
            ),
        ),
        ParamDefinition(
            name="hex_list",
            type=ParamType.LIST_OF_STRINGS,
            description=(
                "Same as flight_ids, aliased as hex_list for Alison downstream consumers."
            ),
        ),
        ParamDefinition(
            name="count",
            type=ParamType.NUMBER,
            description="Number of matching flights with positions inside the polygon.",
        ),
        ParamDefinition(
            name="per_flight_details",
            type=ParamType.JSON_OBJECT,
            description=(
                "Per-flight spatial details keyed by flight ID. Each entry contains: "
                "entry_time, exit_time, time_in_area, duration_seconds, "
                "movement_classification (landing/takeoff/cruise), positions_in_area count, "
                "and path_in_area (GeoJSON LineString of the flight segment within the polygon)."
            ),
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Filter flights by polygon containment and compute movement classification."""

        provider = str(inputs.get("provider") or "fr").lower()
        altitude_threshold = float(inputs.get("altitude_threshold") or 1000)
        time_window_hours = float(inputs.get("time_window_hours") or 24)

        # ----------------------------------------------------------------
        # Step 1: Extract flight identifiers (dual-provider pattern)
        # ----------------------------------------------------------------
        full_result = inputs.get("full_result")
        ids: list[str] = []

        if full_result and isinstance(full_result, dict):
            if provider == "alison":
                raw = full_result.get("hex_list") or full_result.get("flight_ids") or []
            else:
                raw = full_result.get("flight_ids") or []
            ids = [str(x) for x in raw if x is not None]

        # Fallback to direct inputs if full_result didn't yield identifiers
        if not ids:
            if provider == "alison":
                raw = inputs.get("hex_list") or []
            else:
                raw = inputs.get("flight_ids") or []
            ids = [str(x) for x in (raw or []) if x is not None]

        if not ids:
            logger.info("AreaSpatialFilter: no identifiers — returning empty result")
            return {"flight_ids": [], "hex_list": [], "count": 0}

        # ----------------------------------------------------------------
        # Step 2: Parse and validate polygon
        # ----------------------------------------------------------------
        polygon_raw = inputs.get("polygon")
        if not polygon_raw or not isinstance(polygon_raw, list) or len(polygon_raw) < 3:
            logger.warning(
                "AreaSpatialFilter: polygon missing or has fewer than 3 vertices — returning empty result"
            )
            return {"flight_ids": [], "hex_list": [], "count": 0}

        # Normalize polygon vertices: expected as [[lat, lon], ...] or [{"lat": ..., "lon": ...}, ...]
        polygon: list[list[float]] = []
        for pt in polygon_raw:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                polygon.append([float(pt[0]), float(pt[1])])
            elif isinstance(pt, dict):
                polygon.append([float(pt["lat"]), float(pt["lon"])])

        if len(polygon) < 3:
            logger.warning("AreaSpatialFilter: polygon has fewer than 3 valid vertices — returning empty result")
            return {"flight_ids": [], "hex_list": [], "count": 0}

        # ----------------------------------------------------------------
        # Step 3: Build Shapely polygon and pre-compute spatial index
        # CRITICAL: Shapely uses (lon, lat) i.e. (x, y) — swap from [lat, lon] input
        # ----------------------------------------------------------------
        poly_shapely = Polygon([(lon, lat) for lat, lon in polygon])
        shapely.prepare(poly_shapely)  # one-time cost; amortizes over all PIP checks

        # ----------------------------------------------------------------
        # Step 4: Compute bounding box from polygon for SQL pre-filter
        # ----------------------------------------------------------------
        poly_lats = [pt[0] for pt in polygon]
        poly_lons = [pt[1] for pt in polygon]
        bbox_min_lat = min(poly_lats)
        bbox_max_lat = max(poly_lats)
        bbox_min_lon = min(poly_lons)
        bbox_max_lon = max(poly_lons)

        logger.info(
            "AreaSpatialFilter: provider=%s, ids=%d, bbox=[%.4f,%.4f,%.4f,%.4f]",
            provider,
            len(ids),
            bbox_min_lat,
            bbox_max_lat,
            bbox_min_lon,
            bbox_max_lon,
        )

        # ----------------------------------------------------------------
        # Step 5: Query positions by provider
        # ----------------------------------------------------------------
        rows: list[Any] = []

        if provider == "fr":
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        """
                        SELECT flight_id, timestamp, lat, lon, alt, vspeed
                        FROM research.normal_tracks
                        WHERE flight_id = ANY(:ids)
                          AND lat IS NOT NULL AND lon IS NOT NULL
                          AND lat BETWEEN :min_lat AND :max_lat
                          AND lon BETWEEN :min_lon AND :max_lon
                        ORDER BY flight_id, timestamp
                        LIMIT 200000
                        """
                    ),
                    {
                        "ids": ids,
                        "min_lat": bbox_min_lat,
                        "max_lat": bbox_max_lat,
                        "min_lon": bbox_min_lon,
                        "max_lon": bbox_max_lon,
                    },
                )
                rows = result.fetchall()

            if len(rows) >= 200000:
                logger.warning(
                    "AreaSpatialFilter (FR): hit 200000 position LIMIT — some positions may be missing"
                )

        else:
            # Alison provider — MUST include time filter to avoid full-table scan on 46M+ rows
            cutoff_epoch = int(time.time() - time_window_hours * 3600)

            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        """
                        SELECT hex, ts, lat, lon, alt_baro, baro_rate, on_ground
                        FROM public.positions
                        WHERE hex = ANY(:ids)
                          AND ts >= to_timestamp(:cutoff)
                          AND lat BETWEEN :min_lat AND :max_lat
                          AND lon BETWEEN :min_lon AND :max_lon
                        ORDER BY hex, ts
                        LIMIT 200000
                        """
                        # NOTE: No lat IS NOT NULL filter here — on_ground=True rows with
                        # null lat/lon are needed for movement classification signal
                    ),
                    {
                        "ids": ids,
                        "cutoff": cutoff_epoch,
                        "min_lat": bbox_min_lat,
                        "max_lat": bbox_max_lat,
                        "min_lon": bbox_min_lon,
                        "max_lon": bbox_max_lon,
                    },
                )
                rows = result.fetchall()

            if len(rows) >= 200000:
                logger.warning(
                    "AreaSpatialFilter (Alison): hit 200000 position LIMIT — some positions may be missing"
                )

        logger.info("AreaSpatialFilter: fetched %d position rows from DB", len(rows))

        # ----------------------------------------------------------------
        # Step 6: Group positions by flight/hex identifier
        # ----------------------------------------------------------------
        positions_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)

        if provider == "fr":
            for row in rows:
                fid = str(row[0])
                positions_by_id[fid].append(
                    {
                        "timestamp": row[1],
                        "lat": row[2],
                        "lon": row[3],
                        "alt": row[4],
                        "vspeed": row[5],
                    }
                )
        else:
            for row in rows:
                fid = str(row[0])
                positions_by_id[fid].append(
                    {
                        "ts": row[1],
                        "lat": row[2],
                        "lon": row[3],
                        "alt_baro": row[4],
                        "baro_rate": row[5],
                        "on_ground": row[6],
                    }
                )

        # ----------------------------------------------------------------
        # Step 7 & 8: Find polygon-inside positions and compute entry/exit times
        # ----------------------------------------------------------------
        matching_ids: list[str] = []
        per_flight_details: dict[str, dict[str, Any]] = {}

        for fid, pos_list in positions_by_id.items():
            inside_positions: list[dict[str, Any]] = []

            for pos in pos_list:
                lat = pos.get("lat")
                lon = pos.get("lon")
                # Skip null-coordinate positions for spatial containment check
                # (on_ground=True Alison rows commonly have null lat/lon)
                if lat is None or lon is None:
                    continue
                # Shapely uses (lon, lat) i.e. (x, y) — CRITICAL: must be lon first
                if shapely.contains_xy(poly_shapely, float(lon), float(lat)):
                    inside_positions.append(pos)

            if not inside_positions:
                logger.debug("AreaSpatialFilter: flight %s had zero positions inside polygon", fid)
                continue

            # Compute entry/exit times from the first/last inside positions
            entry_pos = inside_positions[0]
            exit_pos = inside_positions[-1]

            if provider == "fr":
                entry_ts_raw = entry_pos["timestamp"]
                exit_ts_raw = exit_pos["timestamp"]
                # FR timestamp is bigint Unix epoch seconds
                entry_time = datetime.utcfromtimestamp(entry_ts_raw).isoformat() + "Z"
                exit_time = datetime.utcfromtimestamp(exit_ts_raw).isoformat() + "Z"
                duration_seconds = float(exit_ts_raw - entry_ts_raw)
            else:
                entry_ts_raw = entry_pos["ts"]
                exit_ts_raw = exit_pos["ts"]
                # Alison ts is timestamptz — asyncpg returns Python datetime
                entry_time = entry_ts_raw.isoformat() if hasattr(entry_ts_raw, "isoformat") else str(entry_ts_raw)
                exit_time = exit_ts_raw.isoformat() if hasattr(exit_ts_raw, "isoformat") else str(exit_ts_raw)
                if hasattr(entry_ts_raw, "timestamp") and hasattr(exit_ts_raw, "timestamp"):
                    duration_seconds = float(exit_ts_raw.timestamp() - entry_ts_raw.timestamp())
                else:
                    duration_seconds = 0.0

            # Format duration as human-readable string
            if duration_seconds < 60:
                time_in_area = f"{int(duration_seconds)}s"
            elif duration_seconds < 3600:
                minutes = int(duration_seconds // 60)
                seconds = int(duration_seconds % 60)
                time_in_area = f"{minutes}m {seconds}s"
            else:
                hours = int(duration_seconds // 3600)
                minutes = int((duration_seconds % 3600) // 60)
                time_in_area = f"{hours}h {minutes}m"

            # ----------------------------------------------------------------
            # Step 9: Classify movement type
            # ----------------------------------------------------------------
            # For Alison: use ALL positions in temporal order (including null-coord rows)
            # so we capture on_ground transitions even when lat/lon are missing
            if provider == "fr":
                movement = classify_movement_fr(inside_positions, altitude_threshold)
            else:
                # Use all positions in the flight's time window for on_ground analysis
                # (not just inside_positions — transitions may occur outside bbox)
                movement = classify_movement_alison(pos_list, altitude_threshold)

            # Build GeoJSON LineString from inside positions (already collected, no extra query)
            path_coords = [
                [float(p["lon"]), float(p["lat"])]
                for p in inside_positions
                if p.get("lat") is not None and p.get("lon") is not None
            ]
            path_in_area = (
                {"type": "LineString", "coordinates": path_coords}
                if len(path_coords) >= 2
                else None
            )

            matching_ids.append(fid)
            per_flight_details[fid] = {
                "entry_time": entry_time,
                "exit_time": exit_time,
                "time_in_area": time_in_area,
                "duration_seconds": duration_seconds,
                "movement_classification": movement,
                "positions_in_area": len(inside_positions),
                "entry_point": [float(inside_positions[0]["lat"]), float(inside_positions[0]["lon"])],
                "exit_point": [float(inside_positions[-1]["lat"]), float(inside_positions[-1]["lon"])],
                "path_in_area": path_in_area,
            }

        logger.info(
            "AreaSpatialFilter: %d/%d identifiers had positions inside polygon",
            len(matching_ids),
            len(ids),
        )

        return {
            "flight_ids": matching_ids,
            "hex_list": matching_ids,  # alias for Alison downstream consumers
            "count": len(matching_ids),
            "per_flight_details": per_flight_details,
        }
