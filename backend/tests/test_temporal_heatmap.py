"""Tests for TemporalHeatmapCube — time-bucket aggregation of flight activity.

Tests cover:
- Cube metadata (id, category, input/output names)
- Hourly buckets (flights at same hour aggregate correctly)
- Day-of-week buckets
- Peak detection (highest count bucket identified)
- Empty input handling
- full_result wrapping
"""

import pytest
from datetime import datetime, timezone


def make_flight(first_seen_ts: float, hex_addr: str = "ABC123") -> dict:
    """Build a minimal flight dict with first_seen_ts as epoch seconds."""
    return {"hex": hex_addr, "first_seen_ts": first_seen_ts}


def epoch(year, month, day, hour=0, minute=0):
    """Helper to get epoch seconds for a UTC datetime."""
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp()


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """TemporalHeatmapCube has correct cube_id, name, and category."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube
    from app.schemas.cube import CubeCategory

    cube = TemporalHeatmapCube()
    assert cube.cube_id == "temporal_heatmap"
    assert cube.name == "Temporal Heatmap"
    assert cube.category == CubeCategory.AGGREGATION


def test_cube_inputs():
    """TemporalHeatmapCube has the required inputs."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()
    input_names = {p.name for p in cube.inputs}
    assert "flights" in input_names
    assert "granularity" in input_names


def test_cube_outputs():
    """TemporalHeatmapCube has the required outputs."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()
    output_names = {p.name for p in cube.outputs}
    assert "buckets" in output_names
    assert "peak" in output_names
    assert "total_flights" in output_names


def test_flights_input_accepts_full_result():
    """flights input has accepts_full_result=True."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()
    flights_param = next(p for p in cube.inputs if p.name == "flights")
    assert flights_param.accepts_full_result is True


# ============================================================
# Hourly buckets
# ============================================================


@pytest.mark.asyncio
async def test_hourly_buckets_aggregation():
    """Flights at the same hour are counted together."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()

    flights = [
        make_flight(epoch(2025, 6, 1, 10, 0)),   # hour 10
        make_flight(epoch(2025, 6, 1, 10, 30)),   # hour 10
        make_flight(epoch(2025, 6, 1, 10, 59)),   # hour 10
        make_flight(epoch(2025, 6, 2, 14, 0)),    # hour 14
    ]

    result = await cube.execute(flights=flights, granularity="hourly")

    assert result["total_flights"] == 4
    buckets = result["buckets"]
    assert len(buckets) == 2  # only hours with count > 0

    bucket_map = {b["hour"]: b["count"] for b in buckets}
    assert bucket_map[10] == 3
    assert bucket_map[14] == 1


@pytest.mark.asyncio
async def test_hourly_buckets_only_nonzero():
    """Hourly mode only returns hours with count > 0."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()

    flights = [make_flight(epoch(2025, 6, 1, 5, 0))]
    result = await cube.execute(flights=flights, granularity="hourly")

    assert len(result["buckets"]) == 1
    assert result["buckets"][0]["hour"] == 5
    assert result["buckets"][0]["count"] == 1


# ============================================================
# Daily buckets
# ============================================================


@pytest.mark.asyncio
async def test_daily_buckets_aggregation():
    """Flights on the same weekday are counted together."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()

    # 2025-06-02 is a Monday (weekday=0), 2025-06-03 is Tuesday (weekday=1)
    flights = [
        make_flight(epoch(2025, 6, 2, 8, 0)),    # Monday
        make_flight(epoch(2025, 6, 9, 12, 0)),    # Monday (next week)
        make_flight(epoch(2025, 6, 3, 10, 0)),    # Tuesday
    ]

    result = await cube.execute(flights=flights, granularity="daily")

    assert result["total_flights"] == 3
    buckets = result["buckets"]
    assert len(buckets) == 2

    bucket_map = {b["day"]: b for b in buckets}
    assert bucket_map[0]["count"] == 2
    assert bucket_map[0]["day_name"] == "Monday"
    assert bucket_map[1]["count"] == 1
    assert bucket_map[1]["day_name"] == "Tuesday"


@pytest.mark.asyncio
async def test_daily_buckets_only_nonzero():
    """Daily mode only returns days with count > 0."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()

    # 2025-06-07 is a Saturday (weekday=5)
    flights = [make_flight(epoch(2025, 6, 7, 15, 0))]
    result = await cube.execute(flights=flights, granularity="daily")

    assert len(result["buckets"]) == 1
    assert result["buckets"][0]["day"] == 5
    assert result["buckets"][0]["day_name"] == "Saturday"


# ============================================================
# Peak detection
# ============================================================


@pytest.mark.asyncio
async def test_peak_detection_hourly():
    """Peak is the bucket with the highest count (hourly)."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()

    flights = [
        make_flight(epoch(2025, 6, 1, 10, 0)),
        make_flight(epoch(2025, 6, 1, 10, 30)),
        make_flight(epoch(2025, 6, 1, 10, 59)),
        make_flight(epoch(2025, 6, 2, 14, 0)),
    ]

    result = await cube.execute(flights=flights, granularity="hourly")

    assert result["peak"]["hour"] == 10
    assert result["peak"]["count"] == 3


@pytest.mark.asyncio
async def test_peak_detection_daily():
    """Peak is the bucket with the highest count (daily)."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()

    flights = [
        make_flight(epoch(2025, 6, 2, 8, 0)),    # Monday
        make_flight(epoch(2025, 6, 9, 12, 0)),    # Monday
        make_flight(epoch(2025, 6, 3, 10, 0)),    # Tuesday
    ]

    result = await cube.execute(flights=flights, granularity="daily")

    assert result["peak"]["day"] == 0
    assert result["peak"]["day_name"] == "Monday"
    assert result["peak"]["count"] == 2


# ============================================================
# Empty input handling
# ============================================================


@pytest.mark.asyncio
async def test_empty_flights_returns_empty():
    """Empty or missing flights returns empty results."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()

    result = await cube.execute()
    assert result["buckets"] == []
    assert result["peak"] is None
    assert result["total_flights"] == 0


@pytest.mark.asyncio
async def test_empty_list_returns_empty():
    """An empty list of flights returns empty results."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()

    result = await cube.execute(flights=[])
    assert result["buckets"] == []
    assert result["peak"] is None
    assert result["total_flights"] == 0


# ============================================================
# Full result wrapping
# ============================================================


@pytest.mark.asyncio
async def test_full_result_with_flights_key():
    """Extracts flights from full_result dict with 'flights' key."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()

    flights_data = [
        make_flight(epoch(2025, 6, 1, 10, 0)),
        make_flight(epoch(2025, 6, 1, 10, 30)),
    ]

    result = await cube.execute(
        flights={"flights": flights_data, "count": 2},
        granularity="hourly",
    )

    assert result["total_flights"] == 2


@pytest.mark.asyncio
async def test_full_result_with_filtered_flights_key():
    """Extracts flights from full_result dict with 'filtered_flights' key."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()

    flights_data = [
        make_flight(epoch(2025, 6, 1, 14, 0)),
    ]

    result = await cube.execute(
        flights={"filtered_flights": flights_data, "total": 1},
        granularity="hourly",
    )

    assert result["total_flights"] == 1
    assert result["buckets"][0]["hour"] == 14


# ============================================================
# Default granularity
# ============================================================


@pytest.mark.asyncio
async def test_default_granularity_is_hourly():
    """When granularity is not specified, defaults to hourly."""
    from app.cubes.temporal_heatmap import TemporalHeatmapCube

    cube = TemporalHeatmapCube()

    flights = [make_flight(epoch(2025, 6, 1, 10, 0))]
    result = await cube.execute(flights=flights)

    # Should have hour key (hourly mode), not day key
    assert "hour" in result["buckets"][0]
    assert "day" not in result["buckets"][0]
