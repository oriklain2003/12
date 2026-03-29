"""Shared historical flight query utilities for behavioral cubes.

Provides batch-async functions to look up flight history by callsign or route.
All functions deduplicate input and use asyncio.gather() for concurrent DB queries.

Per D-04: returns flight metadata rows (same shape as AllFlights output).
Per D-05: located in cubes/utils/.
Per D-06: deduplication handled internally.
"""

import asyncio
import logging
from typing import Any

from sqlalchemy import text

from app.database import engine
from app.cubes.utils.time_utils import epoch_cutoff

logger = logging.getLogger(__name__)

# Columns matching research.flight_metadata (same shape as AllFlights output per D-04)
_HISTORY_COLUMNS = """
    flight_id, callsign, first_seen_ts, last_seen_ts,
    start_lat, start_lon, end_lat, end_lon,
    origin_airport, destination_airport
""".strip()


async def get_callsign_history(
    callsigns: list[str],
    lookback_seconds: int = 604800,
) -> dict[str, list[dict[str, Any]]]:
    """Return historical flight metadata rows keyed by callsign.

    Deduplicates input callsigns, fires one async query per unique callsign
    via asyncio.gather(), returns results as {callsign: [row_dicts]}.

    Args:
        callsigns: List of callsigns to look up (duplicates are ignored).
        lookback_seconds: How far back to query. Default 604800 (7 days per D-02).

    Returns:
        Dict mapping each queried callsign to its list of flight metadata dicts.
    """
    unique = list(set(callsigns))
    if not unique:
        return {}

    cutoff = epoch_cutoff(lookback_seconds)

    async def _fetch_one(callsign: str) -> tuple[str, list[dict[str, Any]]]:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"""
                    SELECT {_HISTORY_COLUMNS}
                    FROM research.flight_metadata
                    WHERE callsign = :callsign
                      AND last_seen_ts >= :cutoff
                    ORDER BY first_seen_ts
                """),
                {"callsign": callsign, "cutoff": cutoff},
            )
            cols = list(result.keys())
            rows = [dict(zip(cols, row)) for row in result.fetchall()]
        return callsign, rows

    results = await asyncio.gather(*[_fetch_one(cs) for cs in unique])
    return dict(results)


async def get_route_history(
    routes: list[tuple[str, str]],
    lookback_seconds: int = 604800,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Return historical flight metadata rows keyed by (origin, destination) pair.

    Deduplicates input routes, fires one async query per unique route
    via asyncio.gather(), returns results as {(origin, dest): [row_dicts]}.

    Args:
        routes: List of (origin_airport, destination_airport) tuples.
        lookback_seconds: How far back to query. Default 604800 (7 days per D-02).

    Returns:
        Dict mapping each (origin, dest) tuple to its list of flight metadata dicts.
    """
    unique = list(set(routes))
    if not unique:
        return {}

    cutoff = epoch_cutoff(lookback_seconds)

    async def _fetch_one(
        route: tuple[str, str],
    ) -> tuple[tuple[str, str], list[dict[str, Any]]]:
        origin, destination = route
        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"""
                    SELECT {_HISTORY_COLUMNS}
                    FROM research.flight_metadata
                    WHERE origin_airport = :origin
                      AND destination_airport = :destination
                      AND last_seen_ts >= :cutoff
                    ORDER BY first_seen_ts
                """),
                {"origin": origin, "destination": destination, "cutoff": cutoff},
            )
            cols = list(result.keys())
            rows = [dict(zip(cols, row)) for row in result.fetchall()]
        return route, rows

    results = await asyncio.gather(*[_fetch_one(r) for r in unique])
    return dict(results)
