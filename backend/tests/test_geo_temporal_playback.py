"""Tests for GeoTemporalPlaybackCube -- passthrough visualization cube.

Tests cover:
- Cube metadata (id, category, widget, inputs, outputs)
- Data passes through unchanged
- Empty data input returns empty output
"""

import pytest


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """GeoTemporalPlaybackCube has correct cube_id, name, category, and widget."""
    from app.cubes.geo_temporal_playback import GeoTemporalPlaybackCube
    from app.schemas.cube import CubeCategory

    cube = GeoTemporalPlaybackCube()
    assert cube.cube_id == "geo_temporal_playback"
    assert cube.name == "Geo-Temporal Playback"
    assert cube.category == CubeCategory.OUTPUT
    assert cube.widget == "geo_playback"


def test_cube_inputs():
    """GeoTemporalPlaybackCube has expected inputs."""
    from app.cubes.geo_temporal_playback import GeoTemporalPlaybackCube

    cube = GeoTemporalPlaybackCube()
    input_names = {p.name for p in cube.inputs}
    assert "data" in input_names
    assert "geometry_column" in input_names
    assert "timestamp_column" in input_names


def test_cube_outputs():
    """GeoTemporalPlaybackCube has a 'data' output."""
    from app.cubes.geo_temporal_playback import GeoTemporalPlaybackCube

    cube = GeoTemporalPlaybackCube()
    output_names = {p.name for p in cube.outputs}
    assert "data" in output_names


def test_data_input_accepts_full_result():
    """data input has accepts_full_result=True."""
    from app.cubes.geo_temporal_playback import GeoTemporalPlaybackCube

    cube = GeoTemporalPlaybackCube()
    data_param = next(p for p in cube.inputs if p.name == "data")
    assert data_param.accepts_full_result is True


# ============================================================
# Execute behavior
# ============================================================


@pytest.mark.asyncio
async def test_passthrough():
    """Data flows through unchanged."""
    from app.cubes.geo_temporal_playback import GeoTemporalPlaybackCube

    cube = GeoTemporalPlaybackCube()
    input_data = [
        {"hex": "ABC", "lat": 32.0, "lon": 34.0, "timestamp": "2025-01-01T00:00:00Z"},
        {"hex": "DEF", "lat": 33.0, "lon": 35.0, "timestamp": "2025-01-01T01:00:00Z"},
    ]
    result = await cube.execute(data=input_data)
    assert result == {"data": input_data}


@pytest.mark.asyncio
async def test_empty_data():
    """Empty input returns empty output."""
    from app.cubes.geo_temporal_playback import GeoTemporalPlaybackCube

    cube = GeoTemporalPlaybackCube()
    result = await cube.execute(data=[])
    assert result == {"data": []}


@pytest.mark.asyncio
async def test_no_data_input():
    """No data argument defaults to empty list."""
    from app.cubes.geo_temporal_playback import GeoTemporalPlaybackCube

    cube = GeoTemporalPlaybackCube()
    result = await cube.execute()
    assert result == {"data": []}
