"""Tests for AllFlightsCube — data-source cube querying research.flight_metadata.

Tests cover:
- Cube metadata (cube_id, category, inputs, outputs)
- Basic query with mocked DB returning flight rows
- Empty result handling
- Absolute time range path
- Polygon filter path (two DB calls: metadata + tracks)
- Callsign filter
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Helpers
# ============================================================

FLIGHT_COLUMNS = [
    "flight_id", "callsign", "airline", "airline_code",
    "first_seen_ts", "last_seen_ts",
    "min_altitude_ft", "max_altitude_ft",
    "origin_airport", "destination_airport",
    "is_anomaly", "is_military",
    "start_lat", "start_lon", "end_lat", "end_lon",
]


def make_flight_row(flight_id: str, callsign: str = "TEST01",
                    start_lat: float = 32.0, start_lon: float = 34.0) -> tuple:
    """Build a raw DB row tuple matching FLIGHT_COLUMNS."""
    return (
        flight_id, callsign, "TestAir", "TA",
        1_700_000_000, 1_700_003_600,
        5000, 35000,
        "LLBG", "EGLL",
        False, False,
        start_lat, start_lon, 51.5, -0.1,
    )


def make_mock_conn(rows: list[tuple], columns: list[str] = None):
    """Create an async context manager mock for engine.connect()."""
    if columns is None:
        columns = FLIGHT_COLUMNS
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.keys.return_value = columns
    mock_result.fetchall.return_value = rows
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)
    return mock_conn


def make_multi_call_conn(call_results: list[tuple[list[str], list[tuple]]]):
    """Create a mock conn that returns different results for sequential DB calls."""
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    side_effects = []
    for columns, rows in call_results:
        mock_result = MagicMock()
        mock_result.keys.return_value = columns
        mock_result.fetchall.return_value = rows
        side_effects.append(mock_result)

    mock_conn.execute = AsyncMock(side_effect=side_effects)
    return mock_conn


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """AllFlightsCube has correct cube_id and category."""
    from app.cubes.all_flights import AllFlightsCube
    from app.schemas.cube import CubeCategory

    cube = AllFlightsCube()
    assert cube.cube_id == "all_flights"
    assert cube.category == CubeCategory.DATA_SOURCE
    assert cube.name == "All Flights"


def test_cube_inputs():
    """AllFlightsCube has expected input parameters."""
    from app.cubes.all_flights import AllFlightsCube

    cube = AllFlightsCube()
    input_names = {p.name for p in cube.inputs}
    expected = {
        "time_range_seconds", "start_time", "end_time",
        "flight_ids", "callsign",
        "min_altitude", "max_altitude",
        "polygon", "airport",
        "min_lat", "max_lat", "min_lon", "max_lon",
    }
    assert expected <= input_names


def test_cube_outputs():
    """AllFlightsCube has flights and flight_ids outputs."""
    from app.cubes.all_flights import AllFlightsCube

    cube = AllFlightsCube()
    output_names = {p.name for p in cube.outputs}
    assert "flights" in output_names
    assert "flight_ids" in output_names


# ============================================================
# Basic query
# ============================================================


@pytest.mark.asyncio
async def test_basic_query():
    """Basic query returns flight rows as dicts with correct structure."""
    from app.cubes.all_flights import AllFlightsCube

    rows = [
        make_flight_row("F001", "ELY001"),
        make_flight_row("F002", "BAW002"),
    ]
    mock_conn = make_mock_conn(rows)

    cube = AllFlightsCube()
    with patch("app.cubes.all_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(time_range_seconds=3600)

    assert len(result["flights"]) == 2
    assert result["flights"][0]["flight_id"] == "F001"
    assert result["flights"][0]["callsign"] == "ELY001"
    assert result["flight_ids"] == ["F001", "F002"]


@pytest.mark.asyncio
async def test_empty_result():
    """Empty DB result returns empty flights list and empty flight_ids."""
    from app.cubes.all_flights import AllFlightsCube

    mock_conn = make_mock_conn([])

    cube = AllFlightsCube()
    with patch("app.cubes.all_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(time_range_seconds=3600)

    assert result["flights"] == []
    assert result["flight_ids"] == []


# ============================================================
# Absolute time range
# ============================================================


@pytest.mark.asyncio
async def test_absolute_time_range():
    """Providing start_time and end_time uses absolute time path."""
    from app.cubes.all_flights import AllFlightsCube

    rows = [make_flight_row("F001")]
    mock_conn = make_mock_conn(rows)

    cube = AllFlightsCube()
    with patch("app.cubes.all_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(
            start_time="1700000000",
            end_time="1700100000",
        )

    assert len(result["flights"]) == 1
    # Verify the execute call included epoch params
    call_args = mock_conn.execute.call_args
    sql_params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("parameters", {})
    assert sql_params.get("start_epoch") == 1700000000
    assert sql_params.get("end_epoch") == 1700100000


# ============================================================
# Callsign filter
# ============================================================


@pytest.mark.asyncio
async def test_callsign_filter():
    """Callsign filter adds ILIKE parameter to query."""
    from app.cubes.all_flights import AllFlightsCube

    rows = [make_flight_row("F001", "ELY123")]
    mock_conn = make_mock_conn(rows)

    cube = AllFlightsCube()
    with patch("app.cubes.all_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(callsign="ELY", time_range_seconds=3600)

    assert len(result["flights"]) == 1
    call_args = mock_conn.execute.call_args
    sql_params = call_args[0][1] if len(call_args[0]) > 1 else {}
    assert sql_params.get("callsign") == "%ELY%"


# ============================================================
# Polygon filter (two DB calls)
# ============================================================


@pytest.mark.asyncio
async def test_polygon_filter():
    """Polygon filter triggers second DB call for track points and filters by ray-casting."""
    from app.cubes.all_flights import AllFlightsCube

    # Square polygon: lat 30-35, lon 33-36
    polygon = [[30, 33], [30, 36], [35, 36], [35, 33]]

    # First call: flight_metadata (both flights match bbox)
    metadata_rows = [
        make_flight_row("F001", start_lat=32.0, start_lon=34.0),
        make_flight_row("F002", start_lat=32.0, start_lon=34.0),
    ]

    # Second call: track points — F001 inside polygon, F002 outside
    track_columns = ["flight_id", "lat", "lon"]
    track_rows = [
        ("F001", 32.0, 34.5),   # Inside polygon
        ("F002", 50.0, 50.0),   # Outside polygon
    ]

    # Need separate connect() calls since the cube uses two `async with engine.connect()` blocks
    mock_conn1 = make_mock_conn(metadata_rows)
    mock_conn2 = make_mock_conn(track_rows, columns=track_columns)

    cube = AllFlightsCube()
    with patch("app.cubes.all_flights.engine") as mock_engine:
        mock_engine.connect.side_effect = [mock_conn1, mock_conn2]
        result = await cube.execute(polygon=polygon, time_range_seconds=3600)

    assert "F001" in result["flight_ids"]
    assert "F002" not in result["flight_ids"]
    assert len(result["flights"]) == 1


@pytest.mark.asyncio
async def test_polygon_empty_candidates():
    """Polygon filter with no metadata matches returns empty results (no second query)."""
    from app.cubes.all_flights import AllFlightsCube

    polygon = [[30, 33], [30, 36], [35, 36], [35, 33]]
    mock_conn = make_mock_conn([])

    cube = AllFlightsCube()
    with patch("app.cubes.all_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(polygon=polygon, time_range_seconds=3600)

    assert result["flights"] == []
    assert result["flight_ids"] == []
