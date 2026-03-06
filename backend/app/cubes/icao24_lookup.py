"""ICAO24 hex address to country/region lookup tables.

This module provides static data structures and helper functions for resolving
ICAO24 Mode-S hex addresses (used in ADS-B transponders) to country names and
regional classification tags (black / gray / other).

Used by:
  - registration_country_filter cube (Plan 03)
  - Any future cube needing ICAO24-based country attribution

Data sources:
  - ICAO 24-bit address allocation by ICAO Annex 10 (hexadecimal blocks per country)
  - Regional classification: mydocs/black_countries.csv, mydocs/gray_countries.csv
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# ICAO24_RANGES
# Each entry: (low_int, high_int, country_name, region_tag)
# region_tag: "black" | "gray" | "other"
# Sorted narrowest-first (smallest range first) to handle overlap correctly.
# ---------------------------------------------------------------------------

ICAO24_RANGES: list[tuple[int, int, str, str]] = sorted(
    [
        # ---- Black countries (from mydocs/black_countries.csv) ----
        (0x700000, 0x700FFF, "Afghanistan", "black"),   # 4096 addresses
        (0x728000, 0x72FFFF, "Iraq", "black"),          # 32768 addresses
        (0x730000, 0x737FFF, "Iran", "black"),          # 32768 addresses
        (0x748000, 0x74FFFF, "Lebanon", "black"),       # 32768 addresses
        (0x760000, 0x767FFF, "Pakistan", "black"),      # 32768 addresses
        (0x778000, 0x77FFFF, "Syria", "black"),         # 32768 addresses
        (0x018000, 0x01FFFF, "Libya", "black"),         # 32768 addresses
        (0x0A0000, 0x0A7FFF, "Algeria", "black"),       # 32768 addresses
        (0x720000, 0x727FFF, "North Korea", "black"),   # 32768 addresses
        (0x890000, 0x890FFF, "Yemen", "black"),         # 4096 addresses

        # ---- Gray countries (from mydocs/gray_countries.csv) ----
        (0x710000, 0x717FFF, "Saudi Arabia", "gray"),   # 32768 addresses
        (0x010000, 0x017FFF, "Egypt", "gray"),          # 32768 addresses
        (0x740000, 0x747FFF, "Jordan", "gray"),         # 32768 addresses
        (0x4B8000, 0x4BFFFF, "Turkey", "gray"),         # 32768 addresses
        (0x896000, 0x896FFF, "UAE", "gray"),            # 4096 addresses
        (0x06C000, 0x06CFFF, "Qatar", "gray"),          # 4096 addresses
        (0x70C000, 0x70C3FF, "Oman", "gray"),           # 1024 addresses

        # ---- Common worldwide (region tag "other") ----
        (0x140000, 0x15FFFF, "Russia", "other"),        # 131072 addresses
        (0x780000, 0x7BFFFF, "China", "other"),         # 262144 addresses
        (0x738000, 0x73FFFF, "Israel", "other"),        # 32768 addresses
        (0xA00000, 0xAFFFFF, "United States", "other"), # 1048576 addresses
        (0x400000, 0x43FFFF, "United Kingdom", "other"),# 262144 addresses
        (0x380000, 0x3BFFFF, "France", "other"),        # 262144 addresses
        (0x3C0000, 0x3FFFFF, "Germany", "other"),       # 262144 addresses
        (0x800000, 0x83FFFF, "India", "other"),         # 262144 addresses
        (0x840000, 0x87FFFF, "Japan", "other"),         # 262144 addresses
        (0xE40000, 0xE7FFFF, "Brazil", "other"),        # 262144 addresses
    ],
    key=lambda r: r[1] - r[0],  # narrowest range first
)


# ---------------------------------------------------------------------------
# REGION_GROUPS
# Maps region tag -> set of country names in that region.
# ---------------------------------------------------------------------------

REGION_GROUPS: dict[str, set[str]] = {
    "black": {
        "Iran",
        "Syria",
        "Lebanon",
        "Iraq",
        "Yemen",
        "Pakistan",
        "Libya",
        "Algeria",
        "Afghanistan",
        "North Korea",
    },
    "gray": {
        "Saudi Arabia",
        "Egypt",
        "Jordan",
        "Turkey",
        "UAE",
        "Qatar",
        "Oman",
    },
}


# ---------------------------------------------------------------------------
# TAIL_PREFIXES
# Maps ICAO registration prefix -> country name.
# Longer prefixes are checked before shorter ones (handled in lookup function).
# ---------------------------------------------------------------------------

TAIL_PREFIXES: dict[str, str] = {
    # Black countries
    "EP-":  "Iran",
    "YK-":  "Syria",
    "OD-":  "Lebanon",
    "YI-":  "Iraq",
    "4W-":  "Yemen",
    "AP-":  "Pakistan",
    "5A-":  "Libya",
    "7T-":  "Algeria",
    "YA-":  "Afghanistan",
    "P-":   "North Korea",

    # Gray countries
    "HZ-":  "Saudi Arabia",
    "SU-":  "Egypt",
    "JY-":  "Jordan",
    "TC-":  "Turkey",
    "A6-":  "UAE",
    "A7-":  "Qatar",
    "A4O-": "Oman",

    # Common worldwide
    "RA-":  "Russia",
    "B-":   "China",
    "4X-":  "Israel",
    "N":    "United States",   # US prefix has no dash
    "G-":   "United Kingdom",
    "F-":   "France",
    "D-":   "Germany",
    "VT-":  "India",
    "JA-":  "Japan",
    "PR-":  "Brazil",
    "PT-":  "Brazil",
    "PP-":  "Brazil",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def hex_to_int(hex_str: str) -> int:
    """Convert an ICAO24 hex string (e.g. '730ABC') to integer.

    Args:
        hex_str: 6-character hexadecimal string (case-insensitive).

    Returns:
        Integer value of the hex address.

    Raises:
        ValueError: If hex_str is not a valid hexadecimal string.
    """
    return int(hex_str.strip(), 16)


def resolve_country_from_hex(hex_addr: str) -> tuple[str, str] | None:
    """Resolve an ICAO24 hex address to (country_name, region_tag).

    Searches ICAO24_RANGES (narrowest-first) and returns the first match.

    Args:
        hex_addr: ICAO24 hex string, e.g. '730ABC' or '730abc'.

    Returns:
        Tuple of (country_name, region_tag) if found, else None.
    """
    try:
        addr_int = hex_to_int(hex_addr)
    except ValueError:
        return None

    for low, high, country, region in ICAO24_RANGES:
        if low <= addr_int <= high:
            return (country, region)

    return None


def resolve_country_from_registration(registration: str | None) -> str | None:
    """Resolve an aircraft registration (tail number) to a country name.

    Performs longest-prefix-first matching against TAIL_PREFIXES.

    Args:
        registration: Aircraft registration string, e.g. 'EP-ABC' or 'N12345'.
                      None is accepted and returns None.

    Returns:
        Country name string if a prefix matches, else None.
    """
    if not registration:
        return None

    reg_upper = registration.upper().strip()

    # Try prefixes from longest to shortest for accurate matching
    sorted_prefixes = sorted(TAIL_PREFIXES.keys(), key=len, reverse=True)
    for prefix in sorted_prefixes:
        if reg_upper.startswith(prefix.upper()):
            return TAIL_PREFIXES[prefix]

    return None


def expand_regions(regions: list[str]) -> set[str]:
    """Expand a list of region tags to the full set of country names.

    Region tags "black" and "gray" expand via REGION_GROUPS.
    Unknown tags are silently ignored.

    Args:
        regions: List of region tag strings, e.g. ['black', 'gray'].

    Returns:
        Set of country name strings belonging to those regions.

    Example:
        >>> 'Iran' in expand_regions(['black'])
        True
    """
    result: set[str] = set()
    for region in regions:
        if region in REGION_GROUPS:
            result |= REGION_GROUPS[region]
    return result
