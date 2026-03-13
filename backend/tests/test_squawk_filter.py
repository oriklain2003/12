"""Tests for SquawkFilterCube — dual-provider squawk filter with code-change detection.

Tests cover:
- Cube metadata (id, category, input/output names)
- Empty input guard (no identifiers)
- Custom mode with FR provider (squawk code matching)
- Custom mode with Alison provider (squawk code matching)
- Emergency mode with FR provider (7500/7600/7700 codes)
- Emergency mode with Alison provider (emergency column)
- Code-change detection (squawk transitions)
- Full result extraction (hex_list/flight_ids from full_result dict)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Helpers
# ============================================================


def make_mock_engine(rows):
    """Create a mock engine returning rows from a single DB call.

    rows: list of tuples matching (id, squawk, emergency, ts) structure.
    """
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows

    mock_conn.execute = AsyncMock(return_value=mock_result)

    # engine.connect() returns an async context manager
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_engine.connect.return_value = mock_ctx

    return mock_engine


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """SquawkFilterCube has correct cube_id, name, and category."""
    from app.cubes.squawk_filter import SquawkFilterCube
    from app.schemas.cube import CubeCategory

    cube = SquawkFilterCube()
    assert cube.cube_id == "squawk_filter"
    assert cube.name == "Squawk Filter"
    assert cube.category == CubeCategory.FILTER


def test_cube_inputs():
    """SquawkFilterCube has expected input parameters."""
    from app.cubes.squawk_filter import SquawkFilterCube

    cube = SquawkFilterCube()
    input_names = {p.name for p in cube.inputs}
    assert "flight_ids" in input_names
    assert "hex_list" in input_names
    assert "squawk_codes" in input_names
    assert "mode" in input_names
    assert "full_result" in input_names
    assert "provider" in input_names
    assert "lookback_hours" in input_names


def test_cube_outputs():
    """SquawkFilterCube has expected output parameters."""
    from app.cubes.squawk_filter import SquawkFilterCube

    cube = SquawkFilterCube()
    output_names = {p.name for p in cube.outputs}
    assert "flight_ids" in output_names
    assert "count" in output_names


def test_full_result_input_accepts_full_result():
    """full_result input has accepts_full_result=True."""
    from app.cubes.squawk_filter import SquawkFilterCube

    cube = SquawkFilterCube()
    full_result_param = next(p for p in cube.inputs if p.name == "full_result")
    assert full_result_param.accepts_full_result is True


# ============================================================
# Empty input guard
# ============================================================


@pytest.mark.asyncio
async def test_empty_input_guard():
    """No flight_ids AND no hex_list returns empty result without DB call."""
    from app.cubes.squawk_filter import SquawkFilterCube

    cube = SquawkFilterCube()
    mock_engine = make_mock_engine([])

    with patch("app.cubes.squawk_filter.engine", mock_engine):
        result = await cube.execute()

    assert result["flight_ids"] == []
    assert result["count"] == 0
    # Should NOT have queried DB
    mock_engine.connect.assert_not_called()


# ============================================================
# Custom mode — FR provider
# ============================================================


@pytest.mark.asyncio
async def test_custom_mode_fr_provider():
    """Custom mode with FR provider filters by user-specified squawk codes."""
    from app.cubes.squawk_filter import SquawkFilterCube
    from datetime import datetime

    cube = SquawkFilterCube()
    ts = datetime(2025, 6, 1, 12, 0, 0)

    # Rows: (id, squawk, emergency, ts)
    # SQL pushdown: squawk = ANY(:codes) with codes=["7700"] — only "7700" rows returned.
    # FL001 has a matching row; FL002 has no matching rows so it won't appear.
    rows = [
        ("FL001", "7700", None, ts),
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.squawk_filter.engine", mock_engine):
        result = await cube.execute(
            flight_ids=["FL001", "FL002"],
            squawk_codes=["7700"],
            mode="custom",
            provider="fr",
        )

    assert "FL001" in result["flight_ids"]
    assert "FL002" not in result["flight_ids"]
    assert result["count"] == 1


# ============================================================
# Custom mode — Alison provider
# ============================================================


@pytest.mark.asyncio
async def test_custom_mode_alison_provider():
    """Custom mode with Alison provider filters positions by squawk codes."""
    from app.cubes.squawk_filter import SquawkFilterCube
    from datetime import datetime

    cube = SquawkFilterCube()
    ts = datetime(2025, 6, 1, 12, 0, 0)

    # Rows: (hex, squawk, emergency, ts)
    # SQL pushdown: squawk = ANY(:codes) with codes=["7600"] — only "7600" rows returned.
    # DEF456 has no matching rows so it won't appear in results.
    rows = [
        ("ABC123", "7600", None, ts),
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.squawk_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["ABC123", "DEF456"],
            squawk_codes=["7600"],
            mode="custom",
            provider="alison",
        )

    assert "ABC123" in result["flight_ids"]
    assert "DEF456" not in result["flight_ids"]
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_custom_mode_empty_squawk_codes():
    """Custom mode with empty squawk_codes returns empty (no DB call)."""
    from app.cubes.squawk_filter import SquawkFilterCube

    cube = SquawkFilterCube()
    mock_engine = make_mock_engine([])

    with patch("app.cubes.squawk_filter.engine", mock_engine):
        result = await cube.execute(
            flight_ids=["FL001"],
            squawk_codes=[],
            mode="custom",
            provider="fr",
        )

    assert result["flight_ids"] == []
    assert result["count"] == 0
    mock_engine.connect.assert_not_called()


# ============================================================
# Emergency mode — FR provider
# ============================================================


@pytest.mark.asyncio
async def test_emergency_mode_fr():
    """Emergency mode with FR provider filters by 7500/7600/7700."""
    from app.cubes.squawk_filter import SquawkFilterCube
    from datetime import datetime

    cube = SquawkFilterCube()
    ts = datetime(2025, 6, 1, 12, 0, 0)

    # SQL pushdown: squawk = ANY(:codes) with codes=EMERGENCY_CODES_FR {"7500","7600","7700"}.
    # Only rows with emergency squawk codes are returned; "1200" is excluded by SQL.
    rows = [
        ("FL001", "7500", None, ts),  # hijack
        ("FL003", "7700", None, ts),  # general emergency
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.squawk_filter.engine", mock_engine):
        result = await cube.execute(
            flight_ids=["FL001", "FL002", "FL003"],
            mode="emergency",
            provider="fr",
        )

    assert "FL001" in result["flight_ids"]
    assert "FL003" in result["flight_ids"]
    assert "FL002" not in result["flight_ids"]
    assert result["count"] == 2


# ============================================================
# Emergency mode — Alison provider
# ============================================================


@pytest.mark.asyncio
async def test_emergency_mode_alison():
    """Emergency mode with Alison provider uses emergency column (SQL pre-filtered)."""
    from app.cubes.squawk_filter import SquawkFilterCube
    from datetime import datetime

    cube = SquawkFilterCube()
    ts = datetime(2025, 6, 1, 12, 0, 0)

    # In emergency mode for Alison, SQL already filters emergency IS NOT NULL AND != 'none'
    # So any rows returned represent matches
    rows = [
        ("HEX001", "7700", "general", ts),
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.squawk_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["HEX001", "HEX002"],
            mode="emergency",
            provider="alison",
        )

    # HEX001 had emergency rows -> matched
    # HEX002 had no rows returned -> not matched
    assert "HEX001" in result["flight_ids"]
    assert "HEX002" not in result["flight_ids"]
    assert result["count"] == 1


# ============================================================
# Code-change detection
# ============================================================


@pytest.mark.asyncio
async def test_code_change_detection():
    """Squawk transitions between consecutive positions are recorded."""
    from app.cubes.squawk_filter import SquawkFilterCube
    from datetime import datetime

    cube = SquawkFilterCube()
    ts1 = datetime(2025, 6, 1, 12, 0, 0)
    ts2 = datetime(2025, 6, 1, 12, 5, 0)
    ts3 = datetime(2025, 6, 1, 12, 10, 0)

    rows = [
        ("FL001", "1200", None, ts1),  # normal VFR
        ("FL001", "7700", None, ts2),  # changed to emergency
        ("FL001", "1200", None, ts3),  # back to normal
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.squawk_filter.engine", mock_engine):
        result = await cube.execute(
            flight_ids=["FL001"],
            squawk_codes=["7700"],
            mode="custom",
            provider="fr",
        )

    assert "FL001" in result["flight_ids"]
    details = result["per_flight_details"]["FL001"]
    assert len(details["code_changes"]) == 2
    assert details["code_changes"][0]["from"] == "1200"
    assert details["code_changes"][0]["to"] == "7700"
    assert details["code_changes"][1]["from"] == "7700"
    assert details["code_changes"][1]["to"] == "1200"
    assert "1200" in details["codes_seen"]
    assert "7700" in details["codes_seen"]


# ============================================================
# Full result extraction
# ============================================================


@pytest.mark.asyncio
async def test_full_result_extraction_flight_ids():
    """FR provider extracts flight_ids from full_result dict."""
    from app.cubes.squawk_filter import SquawkFilterCube
    from datetime import datetime

    cube = SquawkFilterCube()
    ts = datetime(2025, 6, 1, 12, 0, 0)

    rows = [("FL001", "7700", None, ts)]
    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.squawk_filter.engine", mock_engine):
        result = await cube.execute(
            full_result={"flight_ids": ["FL001"], "count": 1},
            squawk_codes=["7700"],
            mode="custom",
            provider="fr",
        )

    assert "FL001" in result["flight_ids"]
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_full_result_extraction_hex_list():
    """Alison provider extracts hex_list from full_result dict."""
    from app.cubes.squawk_filter import SquawkFilterCube
    from datetime import datetime

    cube = SquawkFilterCube()
    ts = datetime(2025, 6, 1, 12, 0, 0)

    rows = [("ABC123", "7600", None, ts)]
    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.squawk_filter.engine", mock_engine):
        result = await cube.execute(
            full_result={"hex_list": ["ABC123"], "count": 1},
            squawk_codes=["7600"],
            mode="custom",
            provider="alison",
        )

    assert "ABC123" in result["flight_ids"]
    assert result["count"] == 1


# ============================================================
# Emergency details in Alison mode
# ============================================================


@pytest.mark.asyncio
async def test_emergency_values_in_alison_details():
    """Alison emergency mode includes emergency_values in per_flight_details."""
    from app.cubes.squawk_filter import SquawkFilterCube
    from datetime import datetime

    cube = SquawkFilterCube()
    ts = datetime(2025, 6, 1, 12, 0, 0)

    rows = [
        ("HEX001", "7700", "general", ts),
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.squawk_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["HEX001"],
            mode="emergency",
            provider="alison",
        )

    details = result["per_flight_details"]["HEX001"]
    assert "emergency_values" in details
    assert "general" in details["emergency_values"]
