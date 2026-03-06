"""SquawkFilterCube: dual-provider squawk filter with code-change detection.

Supports two data providers:
- FR provider: queries research.normal_tracks (identifier: flight_id)
- Alison provider: queries public.positions (identifier: hex)

Two filter modes:
- custom: match user-specified squawk codes
- emergency: FR uses squawk codes 7500/7600/7700; Alison uses positions.emergency column

Code-change detection records timestamp of each squawk transition in Full Result.
"""

import logging
import time
from collections import defaultdict
from typing import Any

from sqlalchemy import text

from app.cubes.base import BaseCube
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType

logger = logging.getLogger(__name__)

# Emergency squawk codes for FR provider
EMERGENCY_CODES_FR = {"7500", "7600", "7700"}


class SquawkFilterCube(BaseCube):
    """Filter flights by transponder squawk codes with code-change detection."""

    cube_id = "squawk_filter"
    name = "Squawk Filter"
    description = (
        "Filter flights by transponder squawk codes with code-change detection. "
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
            name="mode",
            type=ParamType.STRING,
            required=False,
            default="custom",
            widget_hint="select",
            description=(
                "Filter mode. "
                "Options: 'custom' (user-specified squawk_codes) or "
                "'emergency' (preset — 7500/7600/7700 for FR; positions.emergency != none for Alison)."
            ),
        ),
        ParamDefinition(
            name="squawk_codes",
            type=ParamType.LIST_OF_STRINGS,
            required=False,
            description=(
                "Target squawk codes for custom mode (e.g., ['7500', '7700']). "
                "Ignored in emergency mode."
            ),
        ),
        ParamDefinition(
            name="lookback_hours",
            type=ParamType.NUMBER,
            required=False,
            default=24,
            description=(
                "Time window (hours) for Alison positions queries. "
                "Prevents full-table scans of the 46M-row positions table. "
                "Default: 24 hours."
            ),
        ),
    ]

    outputs = [
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description=(
                "IDs of flights with matching squawk — flight_id for FR provider, "
                "hex for Alison provider."
            ),
        ),
        ParamDefinition(
            name="count",
            type=ParamType.NUMBER,
            description="Number of matching flights.",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Filter flights by squawk codes and detect code-change transitions."""

        provider = str(inputs.get("provider") or "fr").lower()
        mode = str(inputs.get("mode") or "custom").lower()
        lookback_hours = float(inputs.get("lookback_hours") or 24)

        # ----------------------------------------------------------------
        # Step 1: Extract identifiers from inputs
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

        # Empty guard
        if not ids:
            logger.info("SquawkFilter: no identifiers — returning empty result")
            return {"flight_ids": [], "count": 0}

        # ----------------------------------------------------------------
        # Step 2: Determine target codes based on mode and provider
        # ----------------------------------------------------------------
        squawk_codes_input = inputs.get("squawk_codes") or []
        target_codes: set[str] = {str(c) for c in squawk_codes_input}

        if mode == "emergency":
            if provider == "fr":
                target_codes = EMERGENCY_CODES_FR
            # For Alison emergency mode, target_codes is unused — we use
            # the emergency column directly in the SQL query.

        elif mode == "custom":
            if not target_codes:
                logger.info("SquawkFilter: custom mode with empty squawk_codes — returning empty result")
                return {"flight_ids": [], "count": 0}

        # ----------------------------------------------------------------
        # Step 3: Query squawk history by provider
        # ----------------------------------------------------------------
        # Compute lookback cutoff as integer epoch (avoid SQL injection with interval)
        cutoff_epoch = int(time.time() - lookback_hours * 3600)

        rows: list[Any] = []

        logger.info(
            "SquawkFilter: provider=%s, mode=%s, ids=%d, target_codes=%s",
            provider,
            mode,
            len(ids),
            target_codes if mode == "custom" else "(emergency)",
        )

        if provider == "fr":
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        """
                        SELECT flight_id AS id,
                               squawk,
                               NULL AS emergency,
                               timestamp AS ts
                        FROM research.normal_tracks
                        WHERE flight_id = ANY(:ids)
                          AND squawk IS NOT NULL
                        ORDER BY flight_id, timestamp
                        LIMIT 100000
                        """
                    ),
                    {"ids": ids},
                )
                rows = result.fetchall()

        else:
            # Alison provider
            if mode == "emergency":
                async with engine.connect() as conn:
                    result = await conn.execute(
                        text(
                            """
                            SELECT hex AS id,
                                   squawk,
                                   emergency,
                                   ts
                            FROM public.positions
                            WHERE hex = ANY(:ids)
                              AND ts >= to_timestamp(:cutoff)
                              AND emergency IS NOT NULL
                              AND emergency != 'none'
                            ORDER BY hex, ts
                            LIMIT 100000
                            """
                        ),
                        {"ids": ids, "cutoff": cutoff_epoch},
                    )
                    rows = result.fetchall()
            else:
                # Custom mode for Alison
                async with engine.connect() as conn:
                    result = await conn.execute(
                        text(
                            """
                            SELECT hex AS id,
                                   squawk,
                                   emergency,
                                   ts
                            FROM public.positions
                            WHERE hex = ANY(:ids)
                              AND ts >= to_timestamp(:cutoff)
                              AND squawk IS NOT NULL
                            ORDER BY hex, ts
                            LIMIT 100000
                            """
                        ),
                        {"ids": ids, "cutoff": cutoff_epoch},
                    )
                    rows = result.fetchall()

        # ----------------------------------------------------------------
        # Step 4: Matching logic — group by identifier, check codes
        # ----------------------------------------------------------------
        # Group rows by identifier
        history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            fid = row[0]
            squawk_val = str(row[1]) if row[1] is not None else None
            emergency_val = row[2] if len(row) > 2 else None
            ts_val = row[3] if len(row) > 3 else None
            history[fid].append(
                {"squawk": squawk_val, "emergency": emergency_val, "ts": ts_val}
            )

        passing_ids: set[str] = set()
        per_flight_details: dict[str, dict[str, Any]] = {}

        for fid, position_rows in history.items():
            matched = False

            if mode == "emergency":
                if provider == "fr":
                    # FR emergency: match squawk codes 7500/7600/7700
                    matched = any(
                        r["squawk"] in target_codes for r in position_rows if r["squawk"]
                    )
                else:
                    # Alison emergency: any row has emergency != 'none' (already filtered by SQL)
                    matched = len(position_rows) > 0

            else:
                # Custom mode: any row squawk in target_codes
                matched = any(
                    r["squawk"] in target_codes for r in position_rows if r["squawk"]
                )

            if not matched:
                continue

            passing_ids.add(fid)

            # ----------------------------------------------------------------
            # Step 5: Code-change detection for matching flights
            # ----------------------------------------------------------------
            codes_seen: list[str] = []
            code_changes: list[dict[str, Any]] = []
            matched_codes: list[str] = []
            emergency_values: list[str] = []

            prev_code: str | None = None
            for r in position_rows:
                code = r["squawk"]
                em = r["emergency"]
                ts = r["ts"]

                if code is not None:
                    if code not in codes_seen:
                        codes_seen.append(code)
                    if code in target_codes or mode == "emergency":
                        if code not in matched_codes:
                            matched_codes.append(code)

                    # Detect code change (skip first — establishes baseline)
                    if prev_code is not None and code != prev_code:
                        code_changes.append(
                            {
                                "from": prev_code,
                                "to": code,
                                "ts": ts.isoformat() if hasattr(ts, "isoformat") else str(ts) if ts else None,
                            }
                        )
                    prev_code = code

                if em and em != "none":
                    if em not in emergency_values:
                        emergency_values.append(em)

            detail: dict[str, Any] = {
                "codes_seen": codes_seen,
                "code_changes": code_changes,
                "matched_codes": matched_codes,
            }
            if provider == "alison" and emergency_values:
                detail["emergency_values"] = emergency_values

            per_flight_details[fid] = detail

        logger.info(
            "SquawkFilter: %d/%d identifiers matched squawk criteria",
            len(passing_ids),
            len(ids),
        )

        return {
            "flight_ids": list(passing_ids),
            "count": len(passing_ids),
            "per_flight_details": per_flight_details,
        }
