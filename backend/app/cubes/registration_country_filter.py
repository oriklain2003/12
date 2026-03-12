"""RegistrationCountryFilterCube: Alison-only country-based aircraft filter.

Resolves ICAO24 hex addresses to registration countries using:
1. Primary: ICAO24 hex range lookup (icao24_lookup.ICAO24_RANGES)
2. Secondary: Tail number prefix matching via public.aircraft + TAIL_PREFIXES

Supports include/exclude filter modes and region group shortcuts (black, gray).

Alison provider only -- expects hex addresses as identifiers.
"""

import logging
from typing import Any

from sqlalchemy import text

from app.cubes.base import BaseCube
from app.cubes.icao24_lookup import expand_regions, resolve_country_from_hex, resolve_country_from_registration
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType

logger = logging.getLogger(__name__)


class RegistrationCountryFilterCube(BaseCube):
    """Filter aircraft by registration country via ICAO24 hex prefix and tail number prefix.

    Alison provider only. Uses two resolution methods:
    - Primary: ICAO24 hex range lookup (narrowest-first for accuracy)
    - Secondary: Tail number prefix from public.aircraft registration column

    Supports include/exclude modes and region group shortcuts (black/gray).
    Unresolvable hexes included in Full Result with country=null.
    """

    cube_id = "registration_country_filter"
    name = "Registration Country Filter"
    description = (
        "Filter aircraft by registration country via ICAO24 hex prefix and tail number prefix. "
        "Alison provider only."
    )
    category = CubeCategory.FILTER

    inputs = [
        ParamDefinition(
            name="full_result",
            type=ParamType.JSON_OBJECT,
            required=False,
            accepts_full_result=True,
            description=(
                "Full result bundle from upstream cube (Alison Flights). "
                "Used to extract hex_list when connected."
            ),
        ),
        ParamDefinition(
            name="hex_list",
            type=ParamType.LIST_OF_STRINGS,
            required=False,
            description=(
                "Direct list of ICAO24 hex addresses. "
                "Used as fallback when full_result is not connected."
            ),
        ),
        ParamDefinition(
            name="filter_mode",
            type=ParamType.STRING,
            required=False,
            default="include",
            widget_hint="select",
            options=["include", "exclude"],
            description=(
                "Filter mode. "
                "'include' keeps only aircraft matching target countries; "
                "'exclude' removes aircraft matching target countries."
            ),
        ),
        ParamDefinition(
            name="countries",
            type=ParamType.LIST_OF_STRINGS,
            required=False,
            widget_hint="tags",
            description=(
                "Country names to match (e.g., ['Iran', 'Syria']). "
                "Combined with region group expansion."
            ),
        ),
        ParamDefinition(
            name="regions",
            type=ParamType.LIST_OF_STRINGS,
            required=False,
            widget_hint="tags",
            options=["black", "gray"],
            description=(
                "Region group tags to expand to country sets "
                "(e.g., ['black', 'gray']). "
                "Combined with direct country names."
            ),
        ),
    ]

    outputs = [
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Hex addresses that passed the country filter.",
        ),
        ParamDefinition(
            name="count",
            type=ParamType.NUMBER,
            description="Number of hex addresses that passed the filter.",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Filter aircraft hexes by registration country."""

        filter_mode = str(inputs.get("filter_mode") or "include").lower()

        # ----------------------------------------------------------------
        # Step 1: Extract hex_list from inputs
        # ----------------------------------------------------------------
        full_result = inputs.get("full_result")
        hex_list: list[str] = []

        if full_result and isinstance(full_result, dict):
            raw = full_result.get("hex_list") or []
            hex_list = [str(x) for x in raw if x is not None]

        # Fallback to direct hex_list input
        if not hex_list:
            raw = inputs.get("hex_list") or []
            hex_list = [str(x) for x in (raw or []) if x is not None]

        # Empty guard
        if not hex_list:
            logger.info("RegistrationCountryFilter: no hex_list — returning empty result")
            return {"flight_ids": [], "count": 0, "country_details": {}}

        # ----------------------------------------------------------------
        # Step 2: Build target country set
        # ----------------------------------------------------------------
        countries_input: list[str] = inputs.get("countries") or []
        regions_input: list[str] = inputs.get("regions") or []

        target_countries: set[str] = set(countries_input)
        target_countries |= expand_regions(regions_input)

        # No filter criteria — pass all hexes through with a warning
        if not target_countries:
            logger.warning(
                "RegistrationCountryFilter: no countries or regions specified — "
                "passing all %d hexes through (no filter applied)",
                len(hex_list),
            )
            # Resolve countries for metadata but don't filter
            resolved_countries: dict[str, dict[str, Any]] = {}
            for hex_addr in hex_list:
                result = resolve_country_from_hex(hex_addr)
                if result:
                    country, region = result
                    resolved_countries[hex_addr] = {
                        "country": country,
                        "region": region,
                        "match_type": "hex_range",
                    }
                else:
                    resolved_countries[hex_addr] = {
                        "country": None,
                        "region": None,
                        "match_type": "unknown",
                    }
            rows = [
                {"hex": h, **info}
                for h, info in resolved_countries.items()
            ]
            return {
                "flight_ids": list(hex_list),
                "count": len(hex_list),
                "country_details": resolved_countries,
                "rows": rows,
            }

        # ----------------------------------------------------------------
        # Step 3: Primary resolution — ICAO24 hex range lookup
        # ----------------------------------------------------------------
        resolved_countries = {}

        for hex_addr in hex_list:
            result = resolve_country_from_hex(hex_addr)
            if result:
                country, region = result
                resolved_countries[hex_addr] = {
                    "country": country,
                    "region": region,
                    "match_type": "hex_range",
                }
            else:
                # Will be filled or left as unknown in secondary check
                resolved_countries[hex_addr] = {
                    "country": None,
                    "region": None,
                    "match_type": "unknown",
                }

        # ----------------------------------------------------------------
        # Step 4: Secondary resolution — tail number prefix via public.aircraft
        # ----------------------------------------------------------------
        # Find hexes that still need resolution (unknown from hex range)
        unresolved_hexes = [
            h for h, info in resolved_countries.items()
            if info["country"] is None
        ]

        if unresolved_hexes:
            logger.info(
                "RegistrationCountryFilter: querying public.aircraft for %d unresolved hexes",
                len(unresolved_hexes),
            )
            try:
                async with engine.connect() as conn:
                    db_result = await conn.execute(
                        text(
                            "SELECT hex, registration "
                            "FROM public.aircraft "
                            "WHERE hex = ANY(:hex_list)"
                        ),
                        {"hex_list": unresolved_hexes},
                    )
                    aircraft_rows = db_result.fetchall()

                for row in aircraft_rows:
                    hex_addr = row[0]
                    registration = row[1]
                    country_from_reg = resolve_country_from_registration(registration)
                    if country_from_reg and hex_addr in resolved_countries:
                        resolved_countries[hex_addr]["country"] = country_from_reg
                        resolved_countries[hex_addr]["match_type"] = "tail_prefix"
                        resolved_countries[hex_addr]["registration"] = registration

            except Exception as exc:
                logger.warning(
                    "RegistrationCountryFilter: public.aircraft query failed: %s", exc
                )

        # Collect hexes that had both hex_range AND tail_prefix resolution
        # (those already had hex_range set from Step 3; check if tail confirms same country)
        # For hexes resolved by hex_range, also do secondary check to upgrade match_type
        resolved_hexes_by_range = [
            h for h, info in resolved_countries.items()
            if info["match_type"] == "hex_range"
        ]
        if resolved_hexes_by_range:
            try:
                async with engine.connect() as conn:
                    db_result = await conn.execute(
                        text(
                            "SELECT hex, registration "
                            "FROM public.aircraft "
                            "WHERE hex = ANY(:hex_list)"
                        ),
                        {"hex_list": resolved_hexes_by_range},
                    )
                    aircraft_rows = db_result.fetchall()

                for row in aircraft_rows:
                    hex_addr = row[0]
                    registration = row[1]
                    country_from_reg = resolve_country_from_registration(registration)
                    if country_from_reg and hex_addr in resolved_countries:
                        # Both methods resolved — upgrade to "both"
                        resolved_countries[hex_addr]["match_type"] = "both"
                        resolved_countries[hex_addr]["registration"] = registration

            except Exception as exc:
                logger.warning(
                    "RegistrationCountryFilter: secondary aircraft query for hex_range hexes failed: %s",
                    exc,
                )

        # ----------------------------------------------------------------
        # Step 5: Apply filter_mode
        # ----------------------------------------------------------------
        passing_hexes: list[str] = []

        for hex_addr in hex_list:
            info = resolved_countries.get(hex_addr, {})
            country = info.get("country")

            if filter_mode == "include":
                # Keep hex if its country is in target set
                # Unknown country (None): exclude in include mode (conservative)
                if country and country in target_countries:
                    passing_hexes.append(hex_addr)
            else:
                # exclude mode: keep hex if its country is NOT in target set
                # Unknown country (None): keep in exclude mode (conservative — don't exclude unknowns)
                if country is None or country not in target_countries:
                    passing_hexes.append(hex_addr)

        logger.info(
            "RegistrationCountryFilter: mode=%s, target_countries=%s, "
            "%d/%d hexes passed",
            filter_mode,
            sorted(target_countries),
            len(passing_hexes),
            len(hex_list),
        )

        # Build rows for table display — only passing hexes with their details
        rows = [
            {"hex": h, **resolved_countries.get(h, {})}
            for h in passing_hexes
        ]
        return {
            "flight_ids": passing_hexes,
            "count": len(passing_hexes),
            "country_details": resolved_countries,
            "rows": rows,
        }
