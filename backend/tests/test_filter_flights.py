"""Tests for FilterFlightsCube — two-tier behavioral filter.

Tests cover:
- Empty input guard
- Tier 1 duration filtering from full_result metadata
- Tier 2 altitude/speed filtering from SQL aggregate results
- AND logic — all active filters must pass
- Polygon filtering with point_in_polygon
- Flights without track data are excluded
- Cube metadata (cube_id, category, inputs, outputs)
- Catalog registration and pipeline type contracts
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


# ============================================================
# Helpers
# ============================================================

def make_full_result(flights: list[dict]) -> dict:
    """Build a __full_result__ bundle like AllFlights would produce."""
    return {
        "flights": flights,
        "flight_ids": [f["flight_id"] for f in flights],
    }


def make_flight(flight_id: str, first_seen_ts: int = 1_000_000, last_seen_ts: int = 1_003_600) -> dict:
    """Build a minimal flight metadata dict (1 hour by default)."""
    return {
        "flight_id": flight_id,
        "first_seen_ts": first_seen_ts,
        "last_seen_ts": last_seen_ts,
        "callsign": f"CS{flight_id}",
    }


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """Test: FilterFlightsCube has correct cube_id, name, description, and category."""
    from app.cubes.filter_flights import FilterFlightsCube
    from app.schemas.cube import CubeCategory

    cube = FilterFlightsCube()
    assert cube.cube_id == "filter_flights"
    assert cube.name == "Filter Flights"
    assert cube.description != ""
    assert cube.category == CubeCategory.FILTER


def test_cube_inputs_defined():
    """Test: FilterFlightsCube has all 8 required inputs."""
    from app.cubes.filter_flights import FilterFlightsCube

    cube = FilterFlightsCube()
    input_names = {p.name for p in cube.inputs}
    expected = {
        "full_result",
        "flight_ids",
        "max_altitude_ft",
        "min_speed_knots",
        "max_speed_knots",
        "min_duration_minutes",
        "max_duration_minutes",
        "polygon",
    }
    assert expected <= input_names


def test_cube_outputs_defined():
    """Test: FilterFlightsCube has filtered_flight_ids and filtered_flights outputs."""
    from app.cubes.filter_flights import FilterFlightsCube

    cube = FilterFlightsCube()
    output_names = {p.name for p in cube.outputs}
    assert "filtered_flight_ids" in output_names
    assert "filtered_flights" in output_names


def test_full_result_input_accepts_full_result():
    """Test: full_result input has accepts_full_result=True."""
    from app.cubes.filter_flights import FilterFlightsCube

    cube = FilterFlightsCube()
    full_result_param = next(p for p in cube.inputs if p.name == "full_result")
    assert full_result_param.accepts_full_result is True


def test_polygon_input_widget_hint():
    """Test: polygon input has widget_hint='polygon'."""
    from app.cubes.filter_flights import FilterFlightsCube

    cube = FilterFlightsCube()
    polygon_param = next(p for p in cube.inputs if p.name == "polygon")
    assert polygon_param.widget_hint == "polygon"


# ============================================================
# Empty input guard
# ============================================================


@pytest.mark.asyncio
async def test_empty_flight_ids_returns_empty():
    """Test: No flight_ids input and no full_result returns empty results."""
    from app.cubes.filter_flights import FilterFlightsCube

    cube = FilterFlightsCube()
    result = await cube.execute()
    assert result["filtered_flight_ids"] == []
    assert result["filtered_flights"] == []


@pytest.mark.asyncio
async def test_empty_full_result_flights_returns_empty():
    """Test: full_result with empty flights list returns empty results."""
    from app.cubes.filter_flights import FilterFlightsCube

    cube = FilterFlightsCube()
    result = await cube.execute(full_result=make_full_result([]))
    assert result["filtered_flight_ids"] == []
    assert result["filtered_flights"] == []


# ============================================================
# Tier 1: Duration filtering (metadata — no DB query)
# ============================================================


@pytest.mark.asyncio
async def test_min_duration_filter_excludes_short_flights():
    """Test: min_duration_minutes excludes flights shorter than threshold (Tier 1 — no DB)."""
    from app.cubes.filter_flights import FilterFlightsCube

    # Flight A: 30 min duration — should be excluded (< 60 min)
    # Flight B: 90 min duration — should pass
    flights = [
        make_flight("A", first_seen_ts=1_000_000, last_seen_ts=1_001_800),  # 30 min
        make_flight("B", first_seen_ts=1_000_000, last_seen_ts=1_005_400),  # 90 min
    ]

    # Mock the DB call for track-data confirmation (Tier 2 presence check)
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("B",)]
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)

    cube = FilterFlightsCube()
    with patch("app.cubes.filter_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(
            full_result=make_full_result(flights),
            min_duration_minutes=60,
        )

    assert "A" not in result["filtered_flight_ids"]
    assert "B" in result["filtered_flight_ids"]


@pytest.mark.asyncio
async def test_max_duration_filter_excludes_long_flights():
    """Test: max_duration_minutes excludes flights longer than threshold (Tier 1 — no DB)."""
    from app.cubes.filter_flights import FilterFlightsCube

    flights = [
        make_flight("A", first_seen_ts=1_000_000, last_seen_ts=1_001_800),  # 30 min — should pass
        make_flight("B", first_seen_ts=1_000_000, last_seen_ts=1_010_800),  # 180 min — should be excluded
    ]

    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("A",)]
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)

    cube = FilterFlightsCube()
    with patch("app.cubes.filter_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(
            full_result=make_full_result(flights),
            max_duration_minutes=120,
        )

    assert "A" in result["filtered_flight_ids"]
    assert "B" not in result["filtered_flight_ids"]


@pytest.mark.asyncio
async def test_duration_filter_excludes_flights_missing_timestamps():
    """Test: Flights missing first_seen_ts/last_seen_ts are excluded by duration filter."""
    from app.cubes.filter_flights import FilterFlightsCube

    flights = [
        {"flight_id": "A", "callsign": "CSA"},  # No timestamps — should be excluded
        make_flight("B", first_seen_ts=1_000_000, last_seen_ts=1_005_400),  # 90 min — should pass
    ]

    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("B",)]
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)

    cube = FilterFlightsCube()
    with patch("app.cubes.filter_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(
            full_result=make_full_result(flights),
            min_duration_minutes=60,
        )

    assert "A" not in result["filtered_flight_ids"]
    assert "B" in result["filtered_flight_ids"]


# ============================================================
# Tier 2: Altitude / speed filtering (SQL aggregate)
# ============================================================


@pytest.mark.asyncio
async def test_max_altitude_filter_excludes_high_flights():
    """Test: max_altitude_ft excludes flights whose max track altitude exceeds threshold."""
    from app.cubes.filter_flights import FilterFlightsCube

    flights = [
        make_flight("A"),  # max_alt = 35000 — should be excluded
        make_flight("B"),  # max_alt = 10000 — should pass
    ]

    # Mock SQL GROUP BY result: (flight_id, max_alt, max_speed)
    mock_conn = AsyncMock()
    mock_rows = [("A", 35000, 400), ("B", 10000, 200)]
    mock_result = MagicMock()
    mock_result.keys.return_value = ["flight_id", "max_alt", "max_speed"]
    mock_result.fetchall.return_value = mock_rows
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)

    cube = FilterFlightsCube()
    with patch("app.cubes.filter_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(
            full_result=make_full_result(flights),
            max_altitude_ft=20000,
        )

    assert "A" not in result["filtered_flight_ids"]
    assert "B" in result["filtered_flight_ids"]


@pytest.mark.asyncio
async def test_min_speed_filter_excludes_slow_flights():
    """Test: min_speed_knots excludes flights that never reach the threshold speed."""
    from app.cubes.filter_flights import FilterFlightsCube

    flights = [
        make_flight("A"),  # max_speed = 50 — should be excluded (never reaches 100)
        make_flight("B"),  # max_speed = 250 — should pass
    ]

    mock_conn = AsyncMock()
    mock_rows = [("A", 5000, 50), ("B", 15000, 250)]
    mock_result = MagicMock()
    mock_result.keys.return_value = ["flight_id", "max_alt", "max_speed"]
    mock_result.fetchall.return_value = mock_rows
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)

    cube = FilterFlightsCube()
    with patch("app.cubes.filter_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(
            full_result=make_full_result(flights),
            min_speed_knots=100,
        )

    assert "A" not in result["filtered_flight_ids"]
    assert "B" in result["filtered_flight_ids"]


@pytest.mark.asyncio
async def test_max_speed_filter_excludes_fast_flights():
    """Test: max_speed_knots excludes flights that exceed the threshold speed."""
    from app.cubes.filter_flights import FilterFlightsCube

    flights = [
        make_flight("A"),  # max_speed = 600 — should be excluded
        make_flight("B"),  # max_speed = 250 — should pass
    ]

    mock_conn = AsyncMock()
    mock_rows = [("A", 35000, 600), ("B", 15000, 250)]
    mock_result = MagicMock()
    mock_result.keys.return_value = ["flight_id", "max_alt", "max_speed"]
    mock_result.fetchall.return_value = mock_rows
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)

    cube = FilterFlightsCube()
    with patch("app.cubes.filter_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(
            full_result=make_full_result(flights),
            max_speed_knots=500,
        )

    assert "A" not in result["filtered_flight_ids"]
    assert "B" in result["filtered_flight_ids"]


@pytest.mark.asyncio
async def test_flights_without_track_data_excluded():
    """Test: Flights with no rows in normal_tracks are excluded even with no filters active."""
    from app.cubes.filter_flights import FilterFlightsCube

    flights = [
        make_flight("A"),  # Has track data
        make_flight("B"),  # No track data — should be excluded
    ]

    # B is absent from the track query result
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("A",)]  # Only A has track data
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)

    cube = FilterFlightsCube()
    with patch("app.cubes.filter_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(full_result=make_full_result(flights))

    assert "A" in result["filtered_flight_ids"]
    assert "B" not in result["filtered_flight_ids"]


@pytest.mark.asyncio
async def test_and_logic_multiple_filters():
    """Test: Flight must pass ALL active filters — AND logic."""
    from app.cubes.filter_flights import FilterFlightsCube

    flights = [
        # A: passes altitude, fails speed
        make_flight("A"),
        # B: fails altitude, passes speed
        make_flight("B"),
        # C: passes both
        make_flight("C"),
    ]

    mock_conn = AsyncMock()
    mock_rows = [
        ("A", 10000, 50),    # Low alt ✓, low speed ✗ (min_speed=100)
        ("B", 40000, 250),   # High alt ✗ (max=30000), fast speed ✓
        ("C", 10000, 250),   # Low alt ✓, fast speed ✓
    ]
    mock_result = MagicMock()
    mock_result.keys.return_value = ["flight_id", "max_alt", "max_speed"]
    mock_result.fetchall.return_value = mock_rows
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)

    cube = FilterFlightsCube()
    with patch("app.cubes.filter_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(
            full_result=make_full_result(flights),
            max_altitude_ft=30000,
            min_speed_knots=100,
        )

    assert "A" not in result["filtered_flight_ids"]  # fails speed
    assert "B" not in result["filtered_flight_ids"]  # fails altitude
    assert "C" in result["filtered_flight_ids"]       # passes both


@pytest.mark.asyncio
async def test_output_filtered_flights_is_subset_of_input():
    """Test: filtered_flights contains only the subset of original flight metadata."""
    from app.cubes.filter_flights import FilterFlightsCube

    flights = [
        make_flight("A"),
        make_flight("B"),
    ]

    mock_conn = AsyncMock()
    mock_rows = [("A", 5000, 200)]  # Only A has track data
    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_rows
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)

    cube = FilterFlightsCube()
    with patch("app.cubes.filter_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(full_result=make_full_result(flights))

    # filtered_flights is the subset from original metadata (not new DB data)
    assert len(result["filtered_flights"]) == 1
    assert result["filtered_flights"][0]["flight_id"] == "A"
    assert result["filtered_flights"][0]["callsign"] == "CSA"


# ============================================================
# Polygon filtering
# ============================================================


@pytest.mark.asyncio
async def test_polygon_filter_includes_flights_with_point_inside():
    """Test: Polygon filter includes flights that have at least one track point inside polygon."""
    from app.cubes.filter_flights import FilterFlightsCube

    flights = [
        make_flight("A"),  # Has point inside polygon
        make_flight("B"),  # Has only points outside polygon
    ]

    # Simple square polygon: lat 0-10, lon 0-10
    polygon = [[0, 0], [0, 10], [10, 10], [10, 0]]

    # Track points: A inside (5,5), B outside (20,20)
    mock_track_rows = [
        ("A", 5.0, 5.0),    # Inside polygon
        ("B", 20.0, 20.0),  # Outside polygon
    ]

    # First call: GROUP BY to check track data existence
    mock_track_result = MagicMock()
    mock_track_result.fetchall.return_value = [("A",), ("B",)]  # Both have tracks initially

    # Second call: polygon query returning track points
    mock_polygon_result = MagicMock()
    mock_polygon_result.fetchall.return_value = mock_track_rows

    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(side_effect=[mock_track_result, mock_polygon_result])

    cube = FilterFlightsCube()
    with patch("app.cubes.filter_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(
            full_result=make_full_result(flights),
            polygon=polygon,
        )

    assert "A" in result["filtered_flight_ids"]
    assert "B" not in result["filtered_flight_ids"]


@pytest.mark.asyncio
async def test_no_filters_returns_all_flights_with_track_data():
    """Test: With no filters active, all flights that have track data are returned."""
    from app.cubes.filter_flights import FilterFlightsCube

    flights = [
        make_flight("A"),
        make_flight("B"),
        make_flight("C"),
    ]

    mock_conn = AsyncMock()
    mock_result = MagicMock()
    # All 3 have track data
    mock_result.fetchall.return_value = [("A",), ("B",), ("C",)]
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)

    cube = FilterFlightsCube()
    with patch("app.cubes.filter_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(full_result=make_full_result(flights))

    assert set(result["filtered_flight_ids"]) == {"A", "B", "C"}


# ============================================================
# Task 2: Catalog registration and pipeline compatibility
# ============================================================


def test_filter_flights_in_catalog():
    """Test: filter_flights appears in registry catalog under FILTER category."""
    from app.engine.registry import registry
    from app.schemas.cube import CubeCategory

    catalog = registry.catalog()
    cube_ids = [c.cube_id for c in catalog]
    assert "filter_flights" in cube_ids

    filter_cube_def = next(c for c in catalog if c.cube_id == "filter_flights")
    assert filter_cube_def.category == CubeCategory.FILTER


def test_catalog_filter_flights_has_correct_inputs():
    """Test: filter_flights in catalog has full_result and other expected inputs."""
    from app.engine.registry import registry

    catalog = registry.catalog()
    filter_cube_def = next(c for c in catalog if c.cube_id == "filter_flights")
    input_names = {p.name for p in filter_cube_def.inputs}

    assert "full_result" in input_names
    assert "flight_ids" in input_names
    assert "max_altitude_ft" in input_names
    assert "min_duration_minutes" in input_names
    assert "polygon" in input_names


def test_catalog_filter_flights_has_correct_outputs():
    """Test: filter_flights in catalog has filtered_flight_ids and filtered_flights + __full_result__."""
    from app.engine.registry import registry

    catalog = registry.catalog()
    filter_cube_def = next(c for c in catalog if c.cube_id == "filter_flights")
    output_names = {p.name for p in filter_cube_def.outputs}

    assert "filtered_flight_ids" in output_names
    assert "filtered_flights" in output_names
    assert "__full_result__" in output_names  # Auto-appended by BaseCube.definition


def test_pipeline_type_contracts():
    """Test: AllFlights -> FilterFlights -> GetAnomalies type contracts are compatible."""
    from app.cubes.all_flights import AllFlightsCube
    from app.cubes.filter_flights import FilterFlightsCube
    from app.cubes.get_anomalies import GetAnomaliesCube
    from app.schemas.cube import ParamType

    all_flights = AllFlightsCube()
    filter_cube = FilterFlightsCube()
    get_anomalies = GetAnomaliesCube()

    # AllFlights produces flight_ids (LIST_OF_STRINGS)
    af_output_map = {p.name: p for p in all_flights.outputs}
    assert af_output_map["flight_ids"].type == ParamType.LIST_OF_STRINGS

    # FilterFlights accepts full_result (JSON_OBJECT, accepts_full_result=True)
    ff_input_map = {p.name: p for p in filter_cube.inputs}
    assert ff_input_map["full_result"].type == ParamType.JSON_OBJECT
    assert ff_input_map["full_result"].accepts_full_result is True

    # FilterFlights produces filtered_flight_ids (LIST_OF_STRINGS)
    ff_output_map = {p.name: p for p in filter_cube.outputs}
    assert ff_output_map["filtered_flight_ids"].type == ParamType.LIST_OF_STRINGS
    assert ff_output_map["filtered_flights"].type == ParamType.JSON_OBJECT

    # GetAnomalies accepts flight_ids (LIST_OF_STRINGS)
    ga_input_map = {p.name: p for p in get_anomalies.inputs}
    assert ga_input_map["flight_ids"].type == ParamType.LIST_OF_STRINGS
