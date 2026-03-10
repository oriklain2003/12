"""DarkFlightDetectorCube: detects transponder transmission gaps (dark flights).

Queries public.positions for an aircraft's position timeline, identifies gaps
exceeding min_gap_minutes, and scores each gap for suspicion based on altitude
context (airborne vs ground).
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from app.cubes.base import BaseCube
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType

logger = logging.getLogger(__name__)

# Altitude threshold (feet) above which a gap is considered airborne.
AIRBORNE_ALT_THRESHOLD_FT = 1000


class DarkFlightDetectorCube(BaseCube):
    """Detect transponder transmission gaps and score them for suspicion."""

    cube_id = "dark_flight_detector"
    name = "Dark Flight Detector"
    description = (
        "Detects transponder transmission gaps (dark flights) for given aircraft. "
        "Identifies gaps exceeding a configurable threshold and scores each gap "
        "for suspicion based on altitude context."
    )
    category = CubeCategory.ANALYSIS

    inputs = [
        ParamDefinition(
            name="hex_list",
            type=ParamType.LIST_OF_STRINGS,
            required=True,
            description="ICAO24 hex addresses to analyze.",
        ),
        ParamDefinition(
            name="full_result",
            type=ParamType.JSON_OBJECT,
            required=False,
            accepts_full_result=True,
            description="Full result from upstream cube (contains 'hex_list' key).",
        ),
        ParamDefinition(
            name="min_gap_minutes",
            type=ParamType.NUMBER,
            required=False,
            default=15,
            description="Minimum gap duration in minutes to flag. Default: 15.",
        ),
        ParamDefinition(
            name="lookback_hours",
            type=ParamType.NUMBER,
            required=False,
            default=24,
            description="Time window to analyze in hours. Default: 24.",
        ),
    ]

    outputs = [
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Hex addresses with detected dark periods.",
        ),
        ParamDefinition(
            name="gap_events",
            type=ParamType.JSON_OBJECT,
            description="Array of gap event objects with timing and suspicion scores.",
        ),
        ParamDefinition(
            name="count",
            type=ParamType.NUMBER,
            description="Number of aircraft with dark periods.",
        ),
    ]

    async def _query_positions(
        self, hex_list: list[str], lookback_hours: float
    ) -> list[dict[str, Any]]:
        """Query public.positions for the given hex addresses within the lookback window."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT hex, ts, lat, lon, alt_baro
                    FROM public.positions
                    WHERE hex = ANY(:hex_list)
                      AND ts >= :cutoff
                    ORDER BY hex, ts
                    LIMIT 200000
                    """
                ),
                {"hex_list": hex_list, "cutoff": cutoff},
            )
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

        return rows

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Detect transponder gaps and score for suspicion."""
        min_gap_minutes = float(inputs.get("min_gap_minutes") or 15)
        lookback_hours = float(inputs.get("lookback_hours") or 24)

        # ---- Extract hex_list: direct input first, fall back to full_result ----
        hex_list: list[str] = []

        direct = inputs.get("hex_list")
        if direct:
            hex_list = [str(x) for x in direct if x is not None]

        if not hex_list:
            full_result = inputs.get("full_result")
            if full_result and isinstance(full_result, dict):
                raw = full_result.get("hex_list") or full_result.get("flight_ids") or []
                hex_list = [str(x) for x in raw if x is not None]

        if not hex_list:
            logger.info("DarkFlightDetector: no hex addresses — returning empty result")
            return {"flight_ids": [], "gap_events": [], "count": 0}

        # ---- Query positions ----
        positions = await self._query_positions(hex_list, lookback_hours)

        if not positions:
            logger.info("DarkFlightDetector: no positions found for %d hex addresses", len(hex_list))
            return {"flight_ids": [], "gap_events": [], "count": 0}

        # ---- Group by hex, sort by timestamp ----
        by_hex: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for pos in positions:
            by_hex[pos["hex"]].append(pos)

        # Sort each group by timestamp
        for hex_addr in by_hex:
            by_hex[hex_addr].sort(key=lambda p: p["ts"])

        # ---- Detect gaps ----
        gap_events: list[dict[str, Any]] = []
        hex_with_gaps: set[str] = set()

        for hex_addr, pos_list in by_hex.items():
            for i in range(1, len(pos_list)):
                prev = pos_list[i - 1]
                curr = pos_list[i]

                prev_ts = prev["ts"]
                curr_ts = curr["ts"]

                # Compute gap in minutes
                if hasattr(prev_ts, "timestamp"):
                    gap_seconds = (curr_ts - prev_ts).total_seconds()
                else:
                    gap_seconds = float(curr_ts - prev_ts)

                gap_minutes = gap_seconds / 60.0

                if gap_minutes < min_gap_minutes:
                    continue

                # ---- Determine airborne status ----
                alt_before = prev.get("alt_baro") or 0
                alt_after = curr.get("alt_baro") or 0
                airborne = (alt_before > AIRBORNE_ALT_THRESHOLD_FT or
                            alt_after > AIRBORNE_ALT_THRESHOLD_FT)

                # ---- Compute suspicion score ----
                duration_score = min(gap_minutes / 120.0, 1.0)
                airborne_bonus = 0.4 if airborne else 0.0
                suspicion_score = min(duration_score + airborne_bonus, 1.0)

                # ---- Format timestamps for output ----
                start_ts = prev_ts.isoformat() if hasattr(prev_ts, "isoformat") else str(prev_ts)
                end_ts = curr_ts.isoformat() if hasattr(curr_ts, "isoformat") else str(curr_ts)

                gap_events.append({
                    "hex": hex_addr,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "gap_minutes": round(gap_minutes, 1),
                    "alt_before_ft": alt_before,
                    "alt_after_ft": alt_after,
                    "airborne": airborne,
                    "suspicion_score": round(suspicion_score, 3),
                    "lat_before": prev.get("lat"),
                    "lon_before": prev.get("lon"),
                    "lat_after": curr.get("lat"),
                    "lon_after": curr.get("lon"),
                })
                hex_with_gaps.add(hex_addr)

        flight_ids = sorted(hex_with_gaps)
        gap_events.sort(key=lambda e: e["suspicion_score"], reverse=True)

        logger.info(
            "DarkFlightDetector: found %d gap events across %d aircraft",
            len(gap_events),
            len(flight_ids),
        )

        return {
            "flight_ids": flight_ids,
            "gap_events": gap_events,
            "count": len(flight_ids),
        }
