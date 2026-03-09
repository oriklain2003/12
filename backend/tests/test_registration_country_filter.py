"""Tests for RegistrationCountryFilterCube — ICAO24 hex country resolution and filtering.

Tests cover:
- Cube metadata (id, category, input/output names)
- Empty hex_list guard
- Include mode (only matching countries pass)
- Exclude mode (matching countries removed)
- Region expansion (black/gray group shortcuts)
- Unknown hex handling (conservative rules per STATE.md decision)
- Tail prefix fallback via public.aircraft DB query
- Empty countries+regions passthrough (no filter applied with warning)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Helpers
# ============================================================


def make_mock_engine_multi(call_results):
    """Create a mock engine that returns different results per DB call.

    call_results: list of lists of tuples. Each entry is the fetchall() return
                  for sequential connect() calls.
    """
    mock_engine = MagicMock()
    call_index = [0]

    def make_ctx():
        idx = call_index[0]
        call_index[0] += 1
        rows = call_results[idx] if idx < len(call_results) else []

        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_conn.execute = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        return mock_ctx

    mock_engine.connect.side_effect = make_ctx
    return mock_engine


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """RegistrationCountryFilterCube has correct cube_id and category."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube
    from app.schemas.cube import CubeCategory

    cube = RegistrationCountryFilterCube()
    assert cube.cube_id == "registration_country_filter"
    assert cube.name == "Registration Country Filter"
    assert cube.category == CubeCategory.FILTER


def test_cube_inputs():
    """RegistrationCountryFilterCube has expected input parameters."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube

    cube = RegistrationCountryFilterCube()
    input_names = {p.name for p in cube.inputs}
    assert "hex_list" in input_names
    assert "countries" in input_names
    assert "regions" in input_names
    assert "filter_mode" in input_names
    assert "full_result" in input_names


def test_cube_outputs():
    """RegistrationCountryFilterCube has expected output parameters."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube

    cube = RegistrationCountryFilterCube()
    output_names = {p.name for p in cube.outputs}
    assert "flight_ids" in output_names
    assert "count" in output_names


# ============================================================
# Empty hex_list guard
# ============================================================


@pytest.mark.asyncio
async def test_empty_hex_list_guard():
    """Empty hex_list returns empty result without DB call."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube

    cube = RegistrationCountryFilterCube()
    mock_engine = make_mock_engine_multi([])

    with patch("app.cubes.registration_country_filter.engine", mock_engine):
        result = await cube.execute()

    assert result["flight_ids"] == []
    assert result["count"] == 0
    mock_engine.connect.assert_not_called()


# ============================================================
# Include mode
# ============================================================


@pytest.mark.asyncio
async def test_include_mode():
    """Include mode keeps only hexes matching target countries."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube

    cube = RegistrationCountryFilterCube()

    # 730000 is Iran (black), A00001 is United States (other)
    # No unresolved hexes, so no DB calls needed for aircraft table
    # But the cube does a second pass for hex_range hexes
    mock_engine = make_mock_engine_multi([
        [],  # second pass: no aircraft rows for hex_range hexes
    ])

    with patch("app.cubes.registration_country_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["730001", "A00001"],
            countries=["Iran"],
            filter_mode="include",
        )

    assert "730001" in result["flight_ids"]
    assert "A00001" not in result["flight_ids"]
    assert result["count"] == 1


# ============================================================
# Exclude mode
# ============================================================


@pytest.mark.asyncio
async def test_exclude_mode():
    """Exclude mode removes hexes matching target countries."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube

    cube = RegistrationCountryFilterCube()

    mock_engine = make_mock_engine_multi([
        [],  # second pass aircraft query
    ])

    with patch("app.cubes.registration_country_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["730001", "A00001"],
            countries=["Iran"],
            filter_mode="exclude",
        )

    assert "730001" not in result["flight_ids"]
    assert "A00001" in result["flight_ids"]
    assert result["count"] == 1


# ============================================================
# Region expansion
# ============================================================


@pytest.mark.asyncio
async def test_region_expansion_black():
    """regions=['black'] expands to all black-list countries and filters accordingly."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube

    cube = RegistrationCountryFilterCube()

    # 730001 = Iran (black), 738001 = Israel (other), 778001 = Syria (black)
    mock_engine = make_mock_engine_multi([
        [],  # second pass
    ])

    with patch("app.cubes.registration_country_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["730001", "738001", "778001"],
            regions=["black"],
            filter_mode="include",
        )

    assert "730001" in result["flight_ids"]  # Iran - black
    assert "778001" in result["flight_ids"]  # Syria - black
    assert "738001" not in result["flight_ids"]  # Israel - other
    assert result["count"] == 2


# ============================================================
# Unknown hex handling (conservative rule)
# ============================================================


@pytest.mark.asyncio
async def test_unknown_hex_excluded_in_include_mode():
    """Unknown hex (not in any ICAO24 range) is excluded in include mode."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube

    cube = RegistrationCountryFilterCube()

    # FFFFFF is not in any known range
    mock_engine = make_mock_engine_multi([
        [],  # unresolved hexes aircraft query (FFFFFF)
        [],  # second pass for hex_range hexes (730001)
    ])

    with patch("app.cubes.registration_country_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["730001", "FFFFFF"],
            countries=["Iran"],
            filter_mode="include",
        )

    assert "730001" in result["flight_ids"]
    assert "FFFFFF" not in result["flight_ids"]


@pytest.mark.asyncio
async def test_unknown_hex_kept_in_exclude_mode():
    """Unknown hex (not in any ICAO24 range) is kept in exclude mode."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube

    cube = RegistrationCountryFilterCube()

    mock_engine = make_mock_engine_multi([
        [],  # unresolved hexes aircraft query
        [],  # second pass for hex_range hexes
    ])

    with patch("app.cubes.registration_country_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["730001", "FFFFFF"],
            countries=["Iran"],
            filter_mode="exclude",
        )

    assert "730001" not in result["flight_ids"]  # Iran excluded
    assert "FFFFFF" in result["flight_ids"]  # unknown kept


# ============================================================
# Tail prefix fallback
# ============================================================


@pytest.mark.asyncio
async def test_tail_prefix_fallback():
    """Unresolved hex resolved via public.aircraft tail number prefix."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube

    cube = RegistrationCountryFilterCube()

    # FFFFFF not in any hex range, but DB returns aircraft with EP- prefix (Iran)
    mock_engine = make_mock_engine_multi([
        [("FFFFFF", "EP-ABC")],  # unresolved hexes: aircraft query returns Iranian tail
        [],                       # second pass for hex_range hexes
    ])

    with patch("app.cubes.registration_country_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["FFFFFF"],
            countries=["Iran"],
            filter_mode="include",
        )

    assert "FFFFFF" in result["flight_ids"]
    assert result["count"] == 1
    assert result["country_details"]["FFFFFF"]["match_type"] == "tail_prefix"
    assert result["country_details"]["FFFFFF"]["country"] == "Iran"


# ============================================================
# Empty countries+regions passthrough
# ============================================================


@pytest.mark.asyncio
async def test_empty_countries_passthrough():
    """Empty countries+regions passes all hexes through (no filter) with metadata."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube

    cube = RegistrationCountryFilterCube()

    # No DB calls needed when no filtering (only hex range resolution)
    with patch("app.cubes.registration_country_filter.engine", MagicMock()):
        result = await cube.execute(
            hex_list=["730001", "A00001"],
            countries=[],
            regions=[],
            filter_mode="include",
        )

    # All hexes pass through
    assert "730001" in result["flight_ids"]
    assert "A00001" in result["flight_ids"]
    assert result["count"] == 2
    # Country metadata still resolved
    assert result["country_details"]["730001"]["country"] == "Iran"
    assert result["country_details"]["A00001"]["country"] == "United States"


# ============================================================
# Full result extraction
# ============================================================


@pytest.mark.asyncio
async def test_full_result_hex_list_extraction():
    """hex_list extracted from full_result when not provided directly."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube

    cube = RegistrationCountryFilterCube()

    mock_engine = make_mock_engine_multi([
        [],  # second pass
    ])

    with patch("app.cubes.registration_country_filter.engine", mock_engine):
        result = await cube.execute(
            full_result={"hex_list": ["730001"], "count": 1},
            countries=["Iran"],
            filter_mode="include",
        )

    assert "730001" in result["flight_ids"]
    assert result["count"] == 1


# ============================================================
# Both match type (hex_range + tail confirmation)
# ============================================================


@pytest.mark.asyncio
async def test_both_match_type_upgrade():
    """Hex resolved by hex_range gets upgraded to 'both' when tail also confirms."""
    from app.cubes.registration_country_filter import RegistrationCountryFilterCube

    cube = RegistrationCountryFilterCube()

    # 730001 is in Iran hex range. Second pass finds aircraft with EP- prefix.
    mock_engine = make_mock_engine_multi([
        [("730001", "EP-XYZ")],  # second pass for hex_range hexes
    ])

    with patch("app.cubes.registration_country_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["730001"],
            countries=["Iran"],
            filter_mode="include",
        )

    assert result["country_details"]["730001"]["match_type"] == "both"
