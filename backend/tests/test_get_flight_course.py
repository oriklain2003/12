"""Tests for GetFlightCourseCube -- flight track points and LineStrings.

Tests cover:
- Cube metadata (id, category, input/output names)
- Points mode: GeoJSON Point geometry per row
- Lines mode: GeoJSON LineString geometry grouped by flight
- Empty/None flight_ids guard
- String flight_ids splitting
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """GetFlightCourseCube has correct cube_id, name, and category."""
    from app.cubes.get_flight_course import GetFlightCourseCube
    from app.schemas.cube import CubeCategory

    cube = GetFlightCourseCube()
    assert cube.cube_id == "get_flight_course"
    assert cube.name == "Get Flight Course"
    assert cube.category == CubeCategory.DATA_SOURCE


def test_cube_inputs():
    """GetFlightCourseCube has flight_ids and output_mode inputs."""
    from app.cubes.get_flight_course import GetFlightCourseCube

    cube = GetFlightCourseCube()
    input_names = {p.name for p in cube.inputs}
    assert "flight_ids" in input_names
    assert "output_mode" in input_names


def test_cube_outputs():
    """GetFlightCourseCube has tracks and flight_ids outputs."""
    from app.cubes.get_flight_course import GetFlightCourseCube

    cube = GetFlightCourseCube()
    output_names = {p.name for p in cube.outputs}
    assert "tracks" in output_names
    assert "flight_ids" in output_names


# ============================================================
# Helpers
# ============================================================


def _make_db_row(flight_id, ts, lat, lon, alt=5000, gspeed=200, vspeed=0,
                 track=90, squawk="1200", callsign="TST01", source="adsb"):
    """Build a tuple matching the SELECT column order in get_flight_course.py."""
    return (flight_id, ts, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source)


DB_COLUMNS = ["flight_id", "timestamp", "lat", "lon", "alt", "gspeed",
              "vspeed", "track", "squawk", "callsign", "source"]


def _mock_engine_connect(rows):
    """Create a patched async context manager for engine.connect()."""
    mock_result = MagicMock()
    mock_result.keys.return_value = DB_COLUMNS
    mock_result.fetchall.return_value = rows

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    return mock_cm, mock_conn


# ============================================================
# Points mode
# ============================================================


@pytest.mark.asyncio
async def test_points_mode():
    """Points mode returns GeoJSON Point geometry per position row."""
    from app.cubes.get_flight_course import GetFlightCourseCube

    cube = GetFlightCourseCube()

    rows = [
        _make_db_row("F1", "2025-06-01T12:00:00", 32.0, 34.0, alt=5000),
        _make_db_row("F1", "2025-06-01T12:05:00", 32.1, 34.1, alt=5500),
        _make_db_row("F2", "2025-06-01T12:00:00", 33.0, 35.0, alt=10000),
    ]

    mock_cm, mock_conn = _mock_engine_connect(rows)

    with patch("app.cubes.get_flight_course.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute(flight_ids=["F1", "F2"], output_mode="points")

    assert len(result["tracks"]) == 3
    assert set(result["flight_ids"]) == {"F1", "F2"}

    # Check GeoJSON Point geometry (lon, lat order)
    pt = result["tracks"][0]
    assert pt["geometry"]["type"] == "Point"
    assert pt["geometry"]["coordinates"] == [34.0, 32.0]  # [lon, lat]
    assert pt["flight_id"] == "F1"


# ============================================================
# Lines mode
# ============================================================


@pytest.mark.asyncio
async def test_lines_mode():
    """Lines mode returns GeoJSON LineString grouped by flight_id."""
    from app.cubes.get_flight_course import GetFlightCourseCube

    cube = GetFlightCourseCube()

    rows = [
        _make_db_row("F1", "2025-06-01T12:00:00", 32.0, 34.0, alt=5000),
        _make_db_row("F1", "2025-06-01T12:05:00", 32.1, 34.1, alt=5500),
        _make_db_row("F1", "2025-06-01T12:10:00", 32.2, 34.2, alt=6000),
        _make_db_row("F2", "2025-06-01T12:00:00", 33.0, 35.0, alt=10000),
        _make_db_row("F2", "2025-06-01T12:05:00", 33.1, 35.1, alt=10500),
    ]

    mock_cm, _ = _mock_engine_connect(rows)

    with patch("app.cubes.get_flight_course.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute(flight_ids=["F1", "F2"], output_mode="lines")

    assert len(result["tracks"]) == 2
    assert set(result["flight_ids"]) == {"F1", "F2"}

    f1_line = next(t for t in result["tracks"] if t["flight_id"] == "F1")
    assert f1_line["geometry"]["type"] == "LineString"
    assert len(f1_line["geometry"]["coordinates"]) == 3
    # Coordinates in [lon, lat] order
    assert f1_line["geometry"]["coordinates"][0] == [34.0, 32.0]

    # Verify altitude aggregation
    assert f1_line["min_alt"] == 5000
    assert f1_line["max_alt"] == 6000

    # Verify time fields
    assert f1_line["start_time"] == "2025-06-01T12:00:00"
    assert f1_line["end_time"] == "2025-06-01T12:10:00"


@pytest.mark.asyncio
async def test_lines_mode_skips_single_point_flights():
    """Lines mode skips flights with fewer than 2 valid points."""
    from app.cubes.get_flight_course import GetFlightCourseCube

    cube = GetFlightCourseCube()

    rows = [
        # Only one point for F1 -- cannot form a LineString
        _make_db_row("F1", "2025-06-01T12:00:00", 32.0, 34.0),
        # Two points for F2 -- valid LineString
        _make_db_row("F2", "2025-06-01T12:00:00", 33.0, 35.0),
        _make_db_row("F2", "2025-06-01T12:05:00", 33.1, 35.1),
    ]

    mock_cm, _ = _mock_engine_connect(rows)

    with patch("app.cubes.get_flight_course.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute(flight_ids=["F1", "F2"], output_mode="lines")

    assert len(result["tracks"]) == 1
    assert result["flight_ids"] == ["F2"]


# ============================================================
# Empty / None flight_ids guard
# ============================================================


@pytest.mark.asyncio
async def test_empty_flight_ids_returns_empty():
    """Empty flight_ids returns early with empty results (no DB query)."""
    from app.cubes.get_flight_course import GetFlightCourseCube

    cube = GetFlightCourseCube()

    with patch("app.cubes.get_flight_course.engine") as mock_engine:
        result = await cube.execute(flight_ids=[])

    # Engine should NOT have been called
    mock_engine.connect.assert_not_called()
    assert result == {"tracks": [], "flight_ids": []}


@pytest.mark.asyncio
async def test_none_flight_ids_returns_empty():
    """None flight_ids returns early with empty results."""
    from app.cubes.get_flight_course import GetFlightCourseCube

    cube = GetFlightCourseCube()

    with patch("app.cubes.get_flight_course.engine") as mock_engine:
        result = await cube.execute(flight_ids=None)

    mock_engine.connect.assert_not_called()
    assert result == {"tracks": [], "flight_ids": []}


@pytest.mark.asyncio
async def test_no_flight_ids_kwarg_returns_empty():
    """Missing flight_ids kwarg returns early with empty results."""
    from app.cubes.get_flight_course import GetFlightCourseCube

    cube = GetFlightCourseCube()

    with patch("app.cubes.get_flight_course.engine") as mock_engine:
        result = await cube.execute()

    mock_engine.connect.assert_not_called()
    assert result == {"tracks": [], "flight_ids": []}


# ============================================================
# String flight_ids splitting
# ============================================================


@pytest.mark.asyncio
async def test_string_flight_ids_split():
    """Comma-separated string flight_ids are correctly split and queried."""
    from app.cubes.get_flight_course import GetFlightCourseCube

    cube = GetFlightCourseCube()

    rows = [
        _make_db_row("F1", "2025-06-01T12:00:00", 32.0, 34.0),
        _make_db_row("F2", "2025-06-01T12:00:00", 33.0, 35.0),
    ]

    mock_cm, mock_conn = _mock_engine_connect(rows)

    with patch("app.cubes.get_flight_course.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute(flight_ids="F1, F2", output_mode="points")

    # Verify the split IDs were passed to the query
    call_args = mock_conn.execute.call_args
    params = call_args[1] if call_args[1] else call_args[0][1]
    assert set(params["flight_ids"]) == {"F1", "F2"}

    assert len(result["tracks"]) == 2


# ============================================================
# Points mode skips rows without lat/lon
# ============================================================


@pytest.mark.asyncio
async def test_points_mode_skips_null_coordinates():
    """Points mode skips rows where lat or lon is None."""
    from app.cubes.get_flight_course import GetFlightCourseCube

    cube = GetFlightCourseCube()

    rows = [
        _make_db_row("F1", "2025-06-01T12:00:00", 32.0, 34.0),
        _make_db_row("F1", "2025-06-01T12:05:00", None, None),  # Missing coords
    ]

    mock_cm, _ = _mock_engine_connect(rows)

    with patch("app.cubes.get_flight_course.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute(flight_ids=["F1"], output_mode="points")

    assert len(result["tracks"]) == 1
    assert result["tracks"][0]["geometry"]["coordinates"] == [34.0, 32.0]
