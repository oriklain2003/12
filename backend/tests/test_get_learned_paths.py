"""Tests for GetLearnedPathsCube -- learned flight path queries.

Tests cover:
- Cube metadata (id, category, input/output names)
- Basic query with GeoJSON coordinate order conversion (lat/lon -> lon/lat)
- Empty result handling
- Origin filter
- Polygon filter (spatial filtering)
- Coordinate order correctness (critical -- DB stores lat/lon, GeoJSON outputs lon/lat)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """GetLearnedPathsCube has correct cube_id, name, and category."""
    from app.cubes.get_learned_paths import GetLearnedPathsCube
    from app.schemas.cube import CubeCategory

    cube = GetLearnedPathsCube()
    assert cube.cube_id == "get_learned_paths"
    assert cube.name == "Get Learned Paths"
    assert cube.category == CubeCategory.DATA_SOURCE


def test_cube_inputs():
    """GetLearnedPathsCube has the expected inputs."""
    from app.cubes.get_learned_paths import GetLearnedPathsCube

    cube = GetLearnedPathsCube()
    input_names = {p.name for p in cube.inputs}
    assert "origin" in input_names
    assert "destination" in input_names
    assert "polygon" in input_names
    assert "path_id" in input_names
    assert "min_member_count" in input_names
    assert "output_geometry" in input_names
    assert "width_override" in input_names


def test_cube_outputs():
    """GetLearnedPathsCube has paths and path_ids outputs."""
    from app.cubes.get_learned_paths import GetLearnedPathsCube

    cube = GetLearnedPathsCube()
    output_names = {p.name for p in cube.outputs}
    assert "paths" in output_names
    assert "path_ids" in output_names


# ============================================================
# Helpers
# ============================================================

DB_COLUMNS = ["id", "origin", "destination", "centerline", "width_nm",
              "member_count", "min_alt_ft", "max_alt_ft"]


def _make_path_row(path_id, origin, destination, centerline_pts,
                   width_nm=2.0, member_count=10, min_alt=5000, max_alt=35000):
    """Build a tuple matching SELECT column order in get_learned_paths.py."""
    return (path_id, origin, destination, centerline_pts, width_nm,
            member_count, min_alt, max_alt)


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


# Sample centerline points (DB format: lat/lon dicts)
SAMPLE_CENTERLINE = [
    {"lat": 33.8, "lon": 35.5, "alt": 5000},
    {"lat": 34.0, "lon": 35.8, "alt": 15000},
    {"lat": 34.5, "lon": 36.5, "alt": 30000},
    {"lat": 34.8, "lon": 37.0, "alt": 25000},
]


# ============================================================
# Basic query
# ============================================================


@pytest.mark.asyncio
async def test_basic_query():
    """Basic query returns paths with correct structure and GeoJSON coordinate order."""
    from app.cubes.get_learned_paths import GetLearnedPathsCube

    cube = GetLearnedPathsCube()

    rows = [
        _make_path_row("PATH_A", "OLBA", "LCLK", SAMPLE_CENTERLINE),
    ]

    mock_cm, _ = _mock_engine_connect(rows)

    with patch("app.cubes.get_learned_paths.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute()

    assert len(result["paths"]) == 1
    assert result["path_ids"] == ["PATH_A"]

    path = result["paths"][0]
    assert path["id"] == "PATH_A"
    assert path["origin"] == "OLBA"
    assert path["destination"] == "LCLK"
    assert path["width_nm"] == 2.0
    assert path["member_count"] == 10
    assert path["geometry"]["type"] == "LineString"


# ============================================================
# Coordinate order conversion (critical)
# ============================================================


@pytest.mark.asyncio
async def test_coordinate_order_lat_lon_to_lon_lat():
    """DB stores lat/lon dicts; GeoJSON output must be [lon, lat] per RFC 7946."""
    from app.cubes.get_learned_paths import GetLearnedPathsCube

    cube = GetLearnedPathsCube()

    centerline = [
        {"lat": 32.0, "lon": 34.0, "alt": 5000},
        {"lat": 33.0, "lon": 35.0, "alt": 10000},
    ]

    rows = [_make_path_row("P1", "LLBG", "LCLK", centerline)]
    mock_cm, _ = _mock_engine_connect(rows)

    with patch("app.cubes.get_learned_paths.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute(output_geometry="centerline")

    coords = result["paths"][0]["geometry"]["coordinates"]
    # First point: DB has lat=32.0, lon=34.0 -> GeoJSON [34.0, 32.0]
    assert coords[0] == [34.0, 32.0], "GeoJSON coordinates must be [lon, lat]"
    assert coords[1] == [35.0, 33.0], "GeoJSON coordinates must be [lon, lat]"


# ============================================================
# Empty result
# ============================================================


@pytest.mark.asyncio
async def test_empty_result():
    """No paths returned -> empty list, empty path_ids."""
    from app.cubes.get_learned_paths import GetLearnedPathsCube

    cube = GetLearnedPathsCube()

    mock_cm, _ = _mock_engine_connect([])

    with patch("app.cubes.get_learned_paths.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute()

    assert result["paths"] == []
    assert result["path_ids"] == []


# ============================================================
# Origin filter
# ============================================================


@pytest.mark.asyncio
async def test_origin_filter_passes_param():
    """Origin filter is passed as ILIKE parameter to SQL query."""
    from app.cubes.get_learned_paths import GetLearnedPathsCube

    cube = GetLearnedPathsCube()

    rows = [_make_path_row("P1", "OLBA", "LCLK", SAMPLE_CENTERLINE)]
    mock_cm, mock_conn = _mock_engine_connect(rows)

    with patch("app.cubes.get_learned_paths.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute(origin="OLBA")

    # Verify origin was passed in SQL params
    call_args = mock_conn.execute.call_args
    sql_text = str(call_args[0][0])
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
    assert "origin" in params
    assert params["origin"] == "OLBA"
    assert "ILIKE :origin" in sql_text


@pytest.mark.asyncio
async def test_destination_filter_passes_param():
    """Destination filter is passed as ILIKE parameter to SQL query."""
    from app.cubes.get_learned_paths import GetLearnedPathsCube

    cube = GetLearnedPathsCube()

    rows = [_make_path_row("P1", "OLBA", "LCLK", SAMPLE_CENTERLINE)]
    mock_cm, mock_conn = _mock_engine_connect(rows)

    with patch("app.cubes.get_learned_paths.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute(destination="LCLK")

    call_args = mock_conn.execute.call_args
    sql_text = str(call_args[0][0])
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
    assert "destination" in params
    assert params["destination"] == "LCLK"
    assert "ILIKE :destination" in sql_text


# ============================================================
# Polygon filter
# ============================================================


@pytest.mark.asyncio
async def test_polygon_filter():
    """Polygon filter keeps paths whose centerline passes through the polygon."""
    from app.cubes.get_learned_paths import GetLearnedPathsCube

    cube = GetLearnedPathsCube()

    # Path A: centerline goes through a polygon around 34.0, 35.8
    path_a_centerline = [
        {"lat": 33.8, "lon": 35.5, "alt": 5000},
        {"lat": 34.0, "lon": 35.8, "alt": 15000},
        {"lat": 34.5, "lon": 36.5, "alt": 30000},
    ]

    # Path B: centerline is far away (lat=50, lon=50)
    path_b_centerline = [
        {"lat": 50.0, "lon": 50.0, "alt": 5000},
        {"lat": 50.5, "lon": 50.5, "alt": 10000},
    ]

    rows = [
        _make_path_row("PATH_A", "OLBA", "LCLK", path_a_centerline),
        _make_path_row("PATH_B", "EGLL", "LFPG", path_b_centerline),
    ]

    mock_cm, _ = _mock_engine_connect(rows)

    # Polygon around lat 33.5-34.5, lon 35.0-36.0 (enclosing Path A's points)
    polygon = [
        [33.5, 35.0],
        [33.5, 36.0],
        [34.5, 36.0],
        [34.5, 35.0],
    ]

    with patch("app.cubes.get_learned_paths.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute(polygon=polygon)

    assert len(result["paths"]) == 1
    assert result["path_ids"] == ["PATH_A"]


# ============================================================
# Path with fewer than 2 points skipped
# ============================================================


@pytest.mark.asyncio
async def test_single_point_path_skipped():
    """Paths with fewer than 2 valid centerline points are skipped."""
    from app.cubes.get_learned_paths import GetLearnedPathsCube

    cube = GetLearnedPathsCube()

    single_pt_centerline = [{"lat": 32.0, "lon": 34.0, "alt": 5000}]

    rows = [_make_path_row("P1", "OLBA", "LCLK", single_pt_centerline)]
    mock_cm, _ = _mock_engine_connect(rows)

    with patch("app.cubes.get_learned_paths.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute()

    assert result["paths"] == []
    assert result["path_ids"] == []


# ============================================================
# min_member_count filter
# ============================================================


@pytest.mark.asyncio
async def test_min_member_count_filter():
    """min_member_count is passed as SQL parameter."""
    from app.cubes.get_learned_paths import GetLearnedPathsCube

    cube = GetLearnedPathsCube()

    rows = [_make_path_row("P1", "OLBA", "LCLK", SAMPLE_CENTERLINE, member_count=20)]
    mock_cm, mock_conn = _mock_engine_connect(rows)

    with patch("app.cubes.get_learned_paths.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute(min_member_count=5)

    call_args = mock_conn.execute.call_args
    sql_text = str(call_args[0][0])
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
    assert "min_member_count" in params
    assert params["min_member_count"] == 5
    assert "member_count >= :min_member_count" in sql_text


# ============================================================
# Corridor output geometry
# ============================================================


@pytest.mark.asyncio
async def test_corridor_output_geometry():
    """Corridor mode returns buffered Polygon geometry."""
    from app.cubes.get_learned_paths import GetLearnedPathsCube

    cube = GetLearnedPathsCube()

    centerline = [
        {"lat": 32.0, "lon": 34.0, "alt": 5000},
        {"lat": 33.0, "lon": 35.0, "alt": 10000},
        {"lat": 34.0, "lon": 36.0, "alt": 15000},
    ]

    rows = [_make_path_row("P1", "OLBA", "LCLK", centerline, width_nm=4.0)]
    mock_cm, _ = _mock_engine_connect(rows)

    with patch("app.cubes.get_learned_paths.engine") as mock_engine:
        mock_engine.connect.return_value = mock_cm
        result = await cube.execute(output_geometry="corridor")

    path = result["paths"][0]
    assert path["geometry"]["type"] == "Polygon"
    # Polygon coordinates should be a list of rings
    assert len(path["geometry"]["coordinates"]) >= 1
