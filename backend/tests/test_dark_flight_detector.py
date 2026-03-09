"""Tests for DarkFlightDetectorCube — transponder gap detection.

Tests cover:
- Cube metadata (id, category, input/output names)
- Gap detection with mocked positions (30-min gap detected)
- No gaps below threshold (5-min intervals, min_gap=15)
- Suspicion score higher for airborne gaps
- Full_result fallback for hex_list extraction
- Empty input guard
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch


# ============================================================
# Helpers
# ============================================================


def make_position(hex_addr: str, ts: datetime, lat: float, lon: float, alt_baro: float = 0, on_ground: bool = False):
    """Build a position dict matching DB row structure."""
    return {
        "hex": hex_addr,
        "ts": ts,
        "lat": lat,
        "lon": lon,
        "alt_baro": alt_baro,
        "on_ground": on_ground,
    }


def positions_to_rows(positions: list[dict]) -> list[tuple]:
    """Convert position dicts to DB-style tuples (hex, ts, lat, lon, alt_baro, on_ground)."""
    return [(p["hex"], p["ts"], p["lat"], p["lon"], p["alt_baro"], p["on_ground"]) for p in positions]


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """DarkFlightDetectorCube has correct cube_id, name, and category."""
    from app.cubes.dark_flight_detector import DarkFlightDetectorCube
    from app.schemas.cube import CubeCategory

    cube = DarkFlightDetectorCube()
    assert cube.cube_id == "dark_flight_detector"
    assert cube.name == "Dark Flight Detector"
    assert cube.category == CubeCategory.ANALYSIS


def test_cube_inputs():
    """DarkFlightDetectorCube has the required inputs."""
    from app.cubes.dark_flight_detector import DarkFlightDetectorCube

    cube = DarkFlightDetectorCube()
    input_names = {p.name for p in cube.inputs}
    assert "hex_list" in input_names
    assert "full_result" in input_names
    assert "min_gap_minutes" in input_names
    assert "lookback_hours" in input_names


def test_cube_outputs():
    """DarkFlightDetectorCube has the required outputs."""
    from app.cubes.dark_flight_detector import DarkFlightDetectorCube

    cube = DarkFlightDetectorCube()
    output_names = {p.name for p in cube.outputs}
    assert "flight_ids" in output_names
    assert "gap_events" in output_names
    assert "count" in output_names


def test_full_result_input_accepts_full_result():
    """full_result input has accepts_full_result=True."""
    from app.cubes.dark_flight_detector import DarkFlightDetectorCube

    cube = DarkFlightDetectorCube()
    full_result_param = next(p for p in cube.inputs if p.name == "full_result")
    assert full_result_param.accepts_full_result is True


# ============================================================
# Gap detection
# ============================================================


@pytest.mark.asyncio
async def test_detects_30_minute_gap():
    """A 30-minute gap between positions is detected with default min_gap_minutes=15."""
    from app.cubes.dark_flight_detector import DarkFlightDetectorCube

    cube = DarkFlightDetectorCube()
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    positions = [
        make_position("ABC123", now, 32.0, 34.0, alt_baro=5000),
        make_position("ABC123", now + timedelta(minutes=5), 32.1, 34.1, alt_baro=5500),
        # 30-minute gap here
        make_position("ABC123", now + timedelta(minutes=35), 32.5, 34.5, alt_baro=6000),
        make_position("ABC123", now + timedelta(minutes=40), 32.6, 34.6, alt_baro=6200),
    ]

    with patch.object(cube, "_query_positions", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = positions
        result = await cube.execute(hex_list=["ABC123"])

    assert result["count"] == 1
    assert "ABC123" in result["flight_ids"]
    assert len(result["gap_events"]) == 1

    event = result["gap_events"][0]
    assert event["hex"] == "ABC123"
    assert event["gap_minutes"] == pytest.approx(30.0, abs=0.1)
    assert event["airborne"] is True  # alt > 1000ft on both sides


@pytest.mark.asyncio
async def test_no_gaps_below_threshold():
    """5-minute intervals with min_gap=15 produce no gap events."""
    from app.cubes.dark_flight_detector import DarkFlightDetectorCube

    cube = DarkFlightDetectorCube()
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Create positions every 5 minutes — no gap exceeds 15 min
    positions = [
        make_position("ABC123", now + timedelta(minutes=i * 5), 32.0, 34.0, alt_baro=5000)
        for i in range(10)
    ]

    with patch.object(cube, "_query_positions", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = positions
        result = await cube.execute(hex_list=["ABC123"], min_gap_minutes=15)

    assert result["count"] == 0
    assert result["flight_ids"] == []
    assert result["gap_events"] == []


@pytest.mark.asyncio
async def test_airborne_gap_higher_suspicion_than_ground():
    """Airborne gaps (alt > 1000ft) get higher suspicion scores than ground gaps."""
    from app.cubes.dark_flight_detector import DarkFlightDetectorCube

    cube = DarkFlightDetectorCube()
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Aircraft A: airborne gap (high altitude on both sides)
    airborne_positions = [
        make_position("AIR001", now, 32.0, 34.0, alt_baro=15000),
        # 30-minute gap
        make_position("AIR001", now + timedelta(minutes=30), 32.5, 34.5, alt_baro=14000),
    ]

    # Aircraft B: ground gap (low altitude on both sides)
    ground_positions = [
        make_position("GND001", now, 32.0, 34.0, alt_baro=100, on_ground=True),
        # 30-minute gap
        make_position("GND001", now + timedelta(minutes=30), 32.0, 34.0, alt_baro=50, on_ground=True),
    ]

    all_positions = airborne_positions + ground_positions

    with patch.object(cube, "_query_positions", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = all_positions
        result = await cube.execute(hex_list=["AIR001", "GND001"], min_gap_minutes=15)

    assert result["count"] == 2

    air_event = next(e for e in result["gap_events"] if e["hex"] == "AIR001")
    gnd_event = next(e for e in result["gap_events"] if e["hex"] == "GND001")

    assert air_event["airborne"] is True
    assert gnd_event["airborne"] is False
    assert air_event["suspicion_score"] > gnd_event["suspicion_score"]


@pytest.mark.asyncio
async def test_suspicion_score_capped_at_one():
    """Suspicion score is capped at 1.0 even for very long airborne gaps."""
    from app.cubes.dark_flight_detector import DarkFlightDetectorCube

    cube = DarkFlightDetectorCube()
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Very long airborne gap: 300 minutes
    positions = [
        make_position("ABC123", now, 32.0, 34.0, alt_baro=30000),
        make_position("ABC123", now + timedelta(minutes=300), 33.0, 35.0, alt_baro=28000),
    ]

    with patch.object(cube, "_query_positions", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = positions
        result = await cube.execute(hex_list=["ABC123"], min_gap_minutes=15)

    event = result["gap_events"][0]
    assert event["suspicion_score"] <= 1.0


@pytest.mark.asyncio
async def test_gap_event_fields():
    """Each gap event contains all required fields."""
    from app.cubes.dark_flight_detector import DarkFlightDetectorCube

    cube = DarkFlightDetectorCube()
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    positions = [
        make_position("ABC123", now, 32.0, 34.0, alt_baro=5000),
        make_position("ABC123", now + timedelta(minutes=30), 32.5, 34.5, alt_baro=6000),
    ]

    with patch.object(cube, "_query_positions", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = positions
        result = await cube.execute(hex_list=["ABC123"], min_gap_minutes=15)

    event = result["gap_events"][0]
    required_fields = {
        "hex", "start_ts", "end_ts", "gap_minutes",
        "alt_before_ft", "alt_after_ft", "airborne", "suspicion_score",
        "lat_before", "lon_before", "lat_after", "lon_after",
    }
    assert required_fields <= set(event.keys())


# ============================================================
# Full result fallback
# ============================================================


@pytest.mark.asyncio
async def test_extracts_hex_list_from_full_result():
    """hex_list is extracted from full_result when not provided directly."""
    from app.cubes.dark_flight_detector import DarkFlightDetectorCube

    cube = DarkFlightDetectorCube()
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    positions = [
        make_position("ABC123", now, 32.0, 34.0, alt_baro=5000),
        make_position("ABC123", now + timedelta(minutes=30), 32.5, 34.5, alt_baro=6000),
    ]

    with patch.object(cube, "_query_positions", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = positions
        result = await cube.execute(
            full_result={"hex_list": ["ABC123"], "count": 1},
            min_gap_minutes=15,
        )

    assert result["count"] == 1
    assert "ABC123" in result["flight_ids"]


# ============================================================
# Empty input guard
# ============================================================


@pytest.mark.asyncio
async def test_empty_hex_list_returns_empty():
    """No hex_list and no full_result returns empty results."""
    from app.cubes.dark_flight_detector import DarkFlightDetectorCube

    cube = DarkFlightDetectorCube()
    result = await cube.execute()

    assert result["flight_ids"] == []
    assert result["gap_events"] == []
    assert result["count"] == 0


# ============================================================
# Multiple aircraft
# ============================================================


@pytest.mark.asyncio
async def test_multiple_aircraft_independent_detection():
    """Gaps are detected independently per aircraft."""
    from app.cubes.dark_flight_detector import DarkFlightDetectorCube

    cube = DarkFlightDetectorCube()
    now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    positions = [
        # Aircraft A: has a 30-min gap
        make_position("AAA", now, 32.0, 34.0, alt_baro=5000),
        make_position("AAA", now + timedelta(minutes=30), 32.5, 34.5, alt_baro=6000),
        # Aircraft B: no gap (positions 5 min apart)
        make_position("BBB", now, 33.0, 35.0, alt_baro=3000),
        make_position("BBB", now + timedelta(minutes=5), 33.1, 35.1, alt_baro=3100),
        make_position("BBB", now + timedelta(minutes=10), 33.2, 35.2, alt_baro=3200),
    ]

    with patch.object(cube, "_query_positions", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = positions
        result = await cube.execute(hex_list=["AAA", "BBB"], min_gap_minutes=15)

    assert result["count"] == 1
    assert "AAA" in result["flight_ids"]
    assert "BBB" not in result["flight_ids"]
