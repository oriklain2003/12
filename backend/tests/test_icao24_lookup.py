"""Tests for icao24_lookup module -- pure function ICAO24 hex/registration/region resolution.

Tests cover:
- resolve_country_from_hex: known hex ranges, unknown hex, case insensitivity
- resolve_country_from_registration: known prefixes, unknown registration, None input
- expand_regions: black/gray expansion, unknown tags ignored
- hex_to_int: valid and invalid hex strings
"""

import pytest


# ============================================================
# hex_to_int
# ============================================================


def test_hex_to_int_valid():
    """Converts valid hex string to integer."""
    from app.cubes.icao24_lookup import hex_to_int

    assert hex_to_int("730000") == 0x730000
    assert hex_to_int("A00000") == 0xA00000
    assert hex_to_int("000000") == 0


def test_hex_to_int_case_insensitive():
    """Hex conversion is case-insensitive."""
    from app.cubes.icao24_lookup import hex_to_int

    assert hex_to_int("abcdef") == hex_to_int("ABCDEF")


def test_hex_to_int_invalid():
    """Invalid hex string raises ValueError."""
    from app.cubes.icao24_lookup import hex_to_int

    with pytest.raises(ValueError):
        hex_to_int("ZZZZZZ")


# ============================================================
# resolve_country_from_hex
# ============================================================


def test_iran_hex():
    """Iran hex range (0x730000-0x737FFF) resolves correctly."""
    from app.cubes.icao24_lookup import resolve_country_from_hex

    result = resolve_country_from_hex("730000")
    assert result is not None
    assert result[0] == "Iran"
    assert result[1] == "black"


def test_us_hex():
    """US hex range (0xA00000-0xAFFFFF) resolves correctly."""
    from app.cubes.icao24_lookup import resolve_country_from_hex

    result = resolve_country_from_hex("A00000")
    assert result is not None
    assert result[0] == "United States"
    assert result[1] == "other"


def test_israel_hex():
    """Israel hex range (0x738000-0x73FFFF) resolves correctly."""
    from app.cubes.icao24_lookup import resolve_country_from_hex

    result = resolve_country_from_hex("738000")
    assert result is not None
    assert result[0] == "Israel"
    assert result[1] == "other"


def test_unknown_hex():
    """Out-of-range hex returns None."""
    from app.cubes.icao24_lookup import resolve_country_from_hex

    result = resolve_country_from_hex("000000")
    assert result is None


def test_hex_case_insensitive():
    """Lowercase hex resolves same as uppercase."""
    from app.cubes.icao24_lookup import resolve_country_from_hex

    lower = resolve_country_from_hex("730000")
    upper = resolve_country_from_hex("730000")
    mixed = resolve_country_from_hex("730000")
    assert lower == upper == mixed


def test_invalid_hex_returns_none():
    """Invalid hex string returns None (not an exception)."""
    from app.cubes.icao24_lookup import resolve_country_from_hex

    result = resolve_country_from_hex("ZZZZZZ")
    assert result is None


def test_gray_country_hex():
    """Saudi Arabia (gray) hex range resolves with gray tag."""
    from app.cubes.icao24_lookup import resolve_country_from_hex

    result = resolve_country_from_hex("710000")
    assert result is not None
    assert result[0] == "Saudi Arabia"
    assert result[1] == "gray"


def test_afghanistan_hex():
    """Afghanistan narrow range (0x700000-0x700FFF) resolves correctly."""
    from app.cubes.icao24_lookup import resolve_country_from_hex

    result = resolve_country_from_hex("700000")
    assert result is not None
    assert result[0] == "Afghanistan"
    assert result[1] == "black"


# ============================================================
# resolve_country_from_registration
# ============================================================


def test_us_registration():
    """US registration (N prefix, no dash) resolves correctly."""
    from app.cubes.icao24_lookup import resolve_country_from_registration

    result = resolve_country_from_registration("N12345")
    assert result == "United States"


def test_iran_registration():
    """Iran registration (EP- prefix) resolves correctly."""
    from app.cubes.icao24_lookup import resolve_country_from_registration

    result = resolve_country_from_registration("EP-ABC")
    assert result == "Iran"


def test_oman_registration():
    """Oman registration (A4O- prefix, 3 chars) resolves correctly."""
    from app.cubes.icao24_lookup import resolve_country_from_registration

    result = resolve_country_from_registration("A4O-XYZ")
    assert result == "Oman"


def test_unknown_registration():
    """Unknown registration prefix returns None."""
    from app.cubes.icao24_lookup import resolve_country_from_registration

    result = resolve_country_from_registration("ZZ-12345")
    assert result is None


def test_none_registration():
    """None registration returns None."""
    from app.cubes.icao24_lookup import resolve_country_from_registration

    result = resolve_country_from_registration(None)
    assert result is None


def test_empty_registration():
    """Empty string registration returns None."""
    from app.cubes.icao24_lookup import resolve_country_from_registration

    result = resolve_country_from_registration("")
    assert result is None


def test_registration_case_insensitive():
    """Registration lookup is case-insensitive."""
    from app.cubes.icao24_lookup import resolve_country_from_registration

    assert resolve_country_from_registration("ep-abc") == "Iran"
    assert resolve_country_from_registration("EP-ABC") == "Iran"


# ============================================================
# expand_regions
# ============================================================


def test_expand_black():
    """Expanding 'black' returns all black-list countries."""
    from app.cubes.icao24_lookup import expand_regions

    result = expand_regions(["black"])
    assert "Iran" in result
    assert "Syria" in result
    assert "Iraq" in result
    assert "Lebanon" in result
    assert "Yemen" in result
    assert "Pakistan" in result
    assert "Libya" in result
    assert "Algeria" in result
    assert "Afghanistan" in result
    assert "North Korea" in result
    # Israel is NOT in black list
    assert "Israel" not in result


def test_expand_gray():
    """Expanding 'gray' returns all gray-list countries."""
    from app.cubes.icao24_lookup import expand_regions

    result = expand_regions(["gray"])
    assert "Saudi Arabia" in result
    assert "Egypt" in result
    assert "Jordan" in result
    assert "Turkey" in result
    assert "UAE" in result
    assert "Qatar" in result
    assert "Oman" in result
    assert len(result) == 7


def test_expand_unknown_tag():
    """Unknown region tags are silently ignored (empty set)."""
    from app.cubes.icao24_lookup import expand_regions

    result = expand_regions(["France"])
    assert result == set()


def test_expand_mixed():
    """Mixed region tags expand correctly (known tags expanded, unknown ignored)."""
    from app.cubes.icao24_lookup import expand_regions

    result = expand_regions(["black", "gray"])
    # Should contain all black + gray countries
    assert "Iran" in result
    assert "Saudi Arabia" in result
    assert len(result) == 17  # 10 black + 7 gray


def test_expand_empty():
    """Empty list returns empty set."""
    from app.cubes.icao24_lookup import expand_regions

    result = expand_regions([])
    assert result == set()
