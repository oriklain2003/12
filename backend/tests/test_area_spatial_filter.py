"""Tests for AreaSpatialFilterCube — polygon spatial filter with movement classification.

Tests cover:
- Cube metadata (id, category, input/output names)
- Empty input guard (no flight_ids or hex_list)
- No polygon guard (missing/invalid polygon)
- FR provider polygon containment
- Alison provider polygon containment
- Movement classification: landing (on_ground transition)
- Movement classification: takeoff (on_ground transition)
- Movement classification: cruise (default, high altitude)
- FR movement classification via altitude + vspeed
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Helpers
# ============================================================

# A simple square polygon around lat=32, lon=34 (aviation [lat, lon] order)
# Covers roughly 31.9-32.1 lat, 33.9-34.1 lon
SQUARE_POLYGON = [
    [31.9, 33.9],
    [31.9, 34.1],
    [32.1, 34.1],
    [32.1, 33.9],
]


def make_mock_engine(rows):
    """Create a mock engine returning rows from a single DB call."""
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows

    mock_conn.execute = AsyncMock(return_value=mock_result)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_engine.connect.return_value = mock_ctx

    return mock_engine


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """AreaSpatialFilterCube has correct cube_id and category."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube
    from app.schemas.cube import CubeCategory

    cube = AreaSpatialFilterCube()
    assert cube.cube_id == "area_spatial_filter"
    assert cube.name == "Area Spatial Filter"
    assert cube.category == CubeCategory.FILTER


def test_cube_inputs():
    """AreaSpatialFilterCube has expected input parameters."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()
    input_names = {p.name for p in cube.inputs}
    assert "flight_ids" in input_names
    assert "hex_list" in input_names
    assert "polygon" in input_names
    assert "provider" in input_names
    assert "full_result" in input_names
    assert "altitude_threshold" in input_names


def test_cube_outputs():
    """AreaSpatialFilterCube has expected output parameters."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()
    output_names = {p.name for p in cube.outputs}
    assert "flight_ids" in output_names
    assert "hex_list" in output_names
    assert "count" in output_names
    assert "per_flight_details" in output_names


# ============================================================
# Empty input guard
# ============================================================


@pytest.mark.asyncio
async def test_empty_input_guard():
    """No flight_ids or hex_list returns empty result without DB call."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()
    mock_engine = make_mock_engine([])

    with patch("app.cubes.area_spatial_filter.engine", mock_engine):
        result = await cube.execute(polygon=SQUARE_POLYGON)

    assert result["flight_ids"] == []
    assert result["count"] == 0
    mock_engine.connect.assert_not_called()


# ============================================================
# No polygon guard
# ============================================================


@pytest.mark.asyncio
async def test_no_polygon_guard():
    """Missing polygon returns empty result."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()
    mock_engine = make_mock_engine([])

    with patch("app.cubes.area_spatial_filter.engine", mock_engine):
        result = await cube.execute(flight_ids=["FL001"])

    assert result["flight_ids"] == []
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_insufficient_polygon_vertices():
    """Polygon with fewer than 3 vertices returns empty result."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()
    mock_engine = make_mock_engine([])

    with patch("app.cubes.area_spatial_filter.engine", mock_engine):
        result = await cube.execute(
            flight_ids=["FL001"],
            polygon=[[32.0, 34.0], [32.1, 34.1]],  # only 2 points
        )

    assert result["flight_ids"] == []
    assert result["count"] == 0


# ============================================================
# FR provider polygon containment
# ============================================================


@pytest.mark.asyncio
async def test_fr_provider_polygon():
    """FR provider filters flights with positions inside polygon."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()

    # Rows: (flight_id, timestamp, lat, lon, alt, vspeed)
    rows = [
        # FL001: position inside polygon
        ("FL001", 1717243200, 32.0, 34.0, 30000, 0),
        # FL002: position outside polygon
        ("FL002", 1717243200, 40.0, 40.0, 30000, 0),
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.area_spatial_filter.engine", mock_engine):
        result = await cube.execute(
            flight_ids=["FL001", "FL002"],
            polygon=SQUARE_POLYGON,
            provider="fr",
        )

    assert "FL001" in result["flight_ids"]
    assert "FL002" not in result["flight_ids"]
    assert result["count"] == 1
    assert "FL001" in result["per_flight_details"]
    assert result["per_flight_details"]["FL001"]["movement_classification"] == "cruise"


# ============================================================
# Alison provider polygon containment
# ============================================================


@pytest.mark.asyncio
async def test_alison_provider_polygon():
    """Alison provider filters hex positions inside polygon."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()
    ts_inside = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Rows: (hex, ts, lat, lon, alt_baro, baro_rate, on_ground)
    rows = [
        # ABC123: inside polygon
        ("ABC123", ts_inside, 32.0, 34.0, 30000, 0, False),
        # DEF456: outside polygon
        ("DEF456", ts_inside, 50.0, 50.0, 30000, 0, False),
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.area_spatial_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["ABC123", "DEF456"],
            polygon=SQUARE_POLYGON,
            provider="alison",
        )

    assert "ABC123" in result["flight_ids"]
    assert "DEF456" not in result["flight_ids"]
    assert result["count"] == 1


# ============================================================
# Movement classification: landing (Alison on_ground transition)
# ============================================================


@pytest.mark.asyncio
async def test_movement_classification_landing():
    """Alison: on_ground False->True transition classifies as landing."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()
    ts1 = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2025, 6, 1, 12, 5, 0, tzinfo=timezone.utc)
    ts3 = datetime(2025, 6, 1, 12, 10, 0, tzinfo=timezone.utc)

    # Rows: (hex, ts, lat, lon, alt_baro, baro_rate, on_ground)
    rows = [
        ("HEX001", ts1, 32.0, 34.0, 2000, -500, False),
        ("HEX001", ts2, 32.0, 34.0, 500, -400, False),
        ("HEX001", ts3, 32.0, 34.0, 0, 0, True),  # touched down
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.area_spatial_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["HEX001"],
            polygon=SQUARE_POLYGON,
            provider="alison",
        )

    assert result["per_flight_details"]["HEX001"]["movement_classification"] == "landing"


# ============================================================
# Movement classification: takeoff (Alison on_ground transition)
# ============================================================


@pytest.mark.asyncio
async def test_movement_classification_takeoff():
    """Alison: on_ground True->False transition classifies as takeoff."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()
    ts1 = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2025, 6, 1, 12, 5, 0, tzinfo=timezone.utc)
    ts3 = datetime(2025, 6, 1, 12, 10, 0, tzinfo=timezone.utc)

    rows = [
        ("HEX001", ts1, 32.0, 34.0, 0, 0, True),     # on ground
        ("HEX001", ts2, 32.0, 34.0, 500, 600, False),  # lifted off
        ("HEX001", ts3, 32.0, 34.0, 2000, 500, False),
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.area_spatial_filter.engine", mock_engine):
        result = await cube.execute(
            hex_list=["HEX001"],
            polygon=SQUARE_POLYGON,
            provider="alison",
        )

    assert result["per_flight_details"]["HEX001"]["movement_classification"] == "takeoff"


# ============================================================
# Movement classification: cruise (FR provider, high altitude)
# ============================================================


@pytest.mark.asyncio
async def test_movement_classification_cruise_fr():
    """FR provider: high altitude with no significant vspeed classifies as cruise."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()

    rows = [
        ("FL001", 1717243200, 32.0, 34.0, 35000, 50),
        ("FL001", 1717243500, 32.01, 34.01, 35100, -20),
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.area_spatial_filter.engine", mock_engine):
        result = await cube.execute(
            flight_ids=["FL001"],
            polygon=SQUARE_POLYGON,
            provider="fr",
        )

    assert result["per_flight_details"]["FL001"]["movement_classification"] == "cruise"


# ============================================================
# FR movement classification: landing via altitude + vspeed
# ============================================================


@pytest.mark.asyncio
async def test_fr_movement_classification_landing():
    """FR provider: low altitude with strong descent classifies as landing."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()

    rows = [
        ("FL001", 1717243200, 32.0, 34.0, 800, -500),
        ("FL001", 1717243500, 32.01, 34.01, 400, -600),
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.area_spatial_filter.engine", mock_engine):
        result = await cube.execute(
            flight_ids=["FL001"],
            polygon=SQUARE_POLYGON,
            provider="fr",
            altitude_threshold=1000,
        )

    assert result["per_flight_details"]["FL001"]["movement_classification"] == "landing"


# ============================================================
# FR movement classification: takeoff via altitude + vspeed
# ============================================================


@pytest.mark.asyncio
async def test_fr_movement_classification_takeoff():
    """FR provider: low altitude with strong ascent classifies as takeoff."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()

    rows = [
        ("FL001", 1717243200, 32.0, 34.0, 200, 500),
        ("FL001", 1717243500, 32.01, 34.01, 600, 600),
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.area_spatial_filter.engine", mock_engine):
        result = await cube.execute(
            flight_ids=["FL001"],
            polygon=SQUARE_POLYGON,
            provider="fr",
            altitude_threshold=1000,
        )

    assert result["per_flight_details"]["FL001"]["movement_classification"] == "takeoff"


# ============================================================
# Per-flight details structure
# ============================================================


@pytest.mark.asyncio
async def test_per_flight_details_structure():
    """Per-flight details contain all required fields."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()

    rows = [
        ("FL001", 1717243200, 32.0, 34.0, 30000, 0),
        ("FL001", 1717243500, 32.01, 34.01, 30100, 0),
    ]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.area_spatial_filter.engine", mock_engine):
        result = await cube.execute(
            flight_ids=["FL001"],
            polygon=SQUARE_POLYGON,
            provider="fr",
        )

    detail = result["per_flight_details"]["FL001"]
    required_keys = {
        "entry_time", "exit_time", "time_in_area", "duration_seconds",
        "movement_classification", "positions_in_area",
        "entry_point", "exit_point", "path_in_area",
    }
    assert required_keys <= set(detail.keys())
    assert detail["positions_in_area"] == 2
    assert detail["duration_seconds"] == 300.0  # 5 min difference


# ============================================================
# Polygon coordinate swap (lat/lon -> lon/lat for Shapely)
# ============================================================


@pytest.mark.asyncio
async def test_polygon_lat_lon_order():
    """Polygon input uses [lat, lon] but Shapely checks use (lon, lat) internally."""
    from app.cubes.area_spatial_filter import AreaSpatialFilterCube

    cube = AreaSpatialFilterCube()

    # Point at (lat=32.0, lon=34.0) should be inside the SQUARE_POLYGON
    rows = [("FL001", 1717243200, 32.0, 34.0, 30000, 0)]

    mock_engine = make_mock_engine(rows)

    with patch("app.cubes.area_spatial_filter.engine", mock_engine):
        result = await cube.execute(
            flight_ids=["FL001"],
            polygon=SQUARE_POLYGON,
            provider="fr",
        )

    assert "FL001" in result["flight_ids"]
    assert result["count"] == 1
