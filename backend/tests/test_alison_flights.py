"""Tests for AlisonFlightsCube — data-source cube querying public.aircraft.

Tests cover:
- Cube metadata (cube_id, category, inputs, outputs)
- Fast path: aircraft-only query (no positions join)
- Slow path: callsign triggers EXISTS subquery on positions
- Empty result handling
- Polygon filter path (positions join + ray-casting post-filter)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Helpers
# ============================================================

AIRCRAFT_COLUMNS = ["hex", "registration", "icao_type", "type_description", "category"]


def make_aircraft_row(hex_addr: str, registration: str = "4X-EHA",
                      icao_type: str = "B738") -> tuple:
    """Build a raw DB row tuple matching AIRCRAFT_COLUMNS."""
    return (hex_addr, registration, icao_type, "Boeing 737-800", "L2J")


def make_mock_conn(rows: list[tuple], columns: list[str] = None):
    """Create an async context manager mock for engine.connect()."""
    if columns is None:
        columns = AIRCRAFT_COLUMNS
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.keys.return_value = columns
    mock_result.fetchall.return_value = rows
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)
    return mock_conn


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """AlisonFlightsCube has correct cube_id and category."""
    from app.cubes.alison_flights import AlisonFlightsCube
    from app.schemas.cube import CubeCategory

    cube = AlisonFlightsCube()
    assert cube.cube_id == "alison_flights"
    assert cube.category == CubeCategory.DATA_SOURCE
    assert cube.name == "Alison Flights"


def test_cube_inputs():
    """AlisonFlightsCube has expected input parameters including time_range."""
    from app.cubes.alison_flights import AlisonFlightsCube

    cube = AlisonFlightsCube()
    input_names = {p.name for p in cube.inputs}
    expected = {
        "time_range_seconds", "start_time", "end_time",
        "hex_filter", "callsign", "aircraft_type",
        "min_altitude", "max_altitude", "polygon",
    }
    assert expected <= input_names


def test_cube_outputs():
    """AlisonFlightsCube has flights and hex_list outputs."""
    from app.cubes.alison_flights import AlisonFlightsCube

    cube = AlisonFlightsCube()
    output_names = {p.name for p in cube.outputs}
    assert "flights" in output_names
    assert "hex_list" in output_names


# ============================================================
# Fast path: aircraft-only query
# ============================================================


@pytest.mark.asyncio
async def test_fast_path():
    """No callsign/altitude/polygon uses fast path (aircraft-only, no positions join)."""
    from app.cubes.alison_flights import AlisonFlightsCube

    rows = [
        make_aircraft_row("A1B2C3"),
        make_aircraft_row("D4E5F6", "4X-EHB"),
    ]
    mock_conn = make_mock_conn(rows)

    cube = AlisonFlightsCube()
    with patch("app.cubes.alison_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(time_range_seconds=3600)

    assert len(result["flights"]) == 2
    assert result["flights"][0]["hex"] == "A1B2C3"
    assert result["hex_list"] == ["A1B2C3", "D4E5F6"]
    # Only one DB call for fast path
    assert mock_conn.execute.call_count == 1


@pytest.mark.asyncio
async def test_empty_result():
    """Empty DB result returns empty flights and hex_list."""
    from app.cubes.alison_flights import AlisonFlightsCube

    mock_conn = make_mock_conn([])

    cube = AlisonFlightsCube()
    with patch("app.cubes.alison_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(time_range_seconds=3600)

    assert result["flights"] == []
    assert result["hex_list"] == []


# ============================================================
# Slow path: callsign triggers positions join
# ============================================================


@pytest.mark.asyncio
async def test_slow_path_callsign():
    """Callsign filter triggers slow path with EXISTS subquery on positions."""
    from app.cubes.alison_flights import AlisonFlightsCube

    rows = [make_aircraft_row("A1B2C3")]
    mock_conn = make_mock_conn(rows)

    cube = AlisonFlightsCube()
    with patch("app.cubes.alison_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(callsign="ELY", time_range_seconds=3600)

    assert len(result["flights"]) == 1
    assert result["hex_list"] == ["A1B2C3"]
    # Verify callsign param was passed
    call_args = mock_conn.execute.call_args
    sql_params = call_args[0][1] if len(call_args[0]) > 1 else {}
    assert sql_params.get("callsign") == "%ELY%"


@pytest.mark.asyncio
async def test_slow_path_altitude():
    """Min/max altitude triggers slow path with positions join."""
    from app.cubes.alison_flights import AlisonFlightsCube

    rows = [make_aircraft_row("A1B2C3")]
    mock_conn = make_mock_conn(rows)

    cube = AlisonFlightsCube()
    with patch("app.cubes.alison_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(min_altitude=5000, time_range_seconds=3600)

    assert len(result["flights"]) == 1
    call_args = mock_conn.execute.call_args
    sql_params = call_args[0][1] if len(call_args[0]) > 1 else {}
    assert sql_params.get("min_altitude") == 5000.0


# ============================================================
# Polygon filter (slow path + post-filter)
# ============================================================


@pytest.mark.asyncio
async def test_polygon_filter():
    """Polygon filter triggers slow path and ray-casting post-filter."""
    from app.cubes.alison_flights import AlisonFlightsCube

    polygon = [[30, 33], [30, 36], [35, 36], [35, 33]]

    aircraft_rows = [
        make_aircraft_row("A1B2C3"),
        make_aircraft_row("D4E5F6"),
    ]

    # Track points for post-filter: A1B2C3 inside, D4E5F6 outside
    track_columns = ["hex", "lat", "lon"]
    track_rows = [
        ("A1B2C3", 32.0, 34.5),   # Inside polygon
        ("D4E5F6", 50.0, 50.0),   # Outside polygon
    ]

    mock_conn1 = make_mock_conn(aircraft_rows)
    mock_conn2 = make_mock_conn(track_rows, columns=track_columns)

    cube = AlisonFlightsCube()
    with patch("app.cubes.alison_flights.engine") as mock_engine:
        mock_engine.connect.side_effect = [mock_conn1, mock_conn2]
        result = await cube.execute(polygon=polygon, time_range_seconds=3600)

    assert "A1B2C3" in result["hex_list"]
    assert "D4E5F6" not in result["hex_list"]
    assert len(result["flights"]) == 1


@pytest.mark.asyncio
async def test_polygon_empty_aircraft():
    """Polygon with no aircraft matches skips position post-filter."""
    from app.cubes.alison_flights import AlisonFlightsCube

    polygon = [[30, 33], [30, 36], [35, 36], [35, 33]]
    mock_conn = make_mock_conn([])

    cube = AlisonFlightsCube()
    with patch("app.cubes.alison_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(polygon=polygon, time_range_seconds=3600)

    assert result["flights"] == []
    assert result["hex_list"] == []


# ============================================================
# Absolute time range
# ============================================================


@pytest.mark.asyncio
async def test_absolute_time_range():
    """Providing start_time and end_time uses absolute time filter."""
    from app.cubes.alison_flights import AlisonFlightsCube

    rows = [make_aircraft_row("A1B2C3")]
    mock_conn = make_mock_conn(rows)

    cube = AlisonFlightsCube()
    with patch("app.cubes.alison_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(
            start_time="1700000000",
            end_time="1700100000",
        )

    assert len(result["flights"]) == 1
    call_args = mock_conn.execute.call_args
    sql_params = call_args[0][1] if len(call_args[0]) > 1 else {}
    assert "ts_start" in sql_params
    assert "ts_end" in sql_params
