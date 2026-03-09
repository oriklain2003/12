"""Tests for SignalHealthAnalyzerCube.

Tests cover:
- Cube metadata (cube_id, category)
- Input/output definitions
- Empty hex_list guard
- full_result extraction (hex_list and flight_ids keys)
- Basic detection orchestration (rule-based + Kalman)
- classify_mode filtering (anomaly, Stable)
- target_phase filtering (takeoff altitude filter)
- stats_summary output
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.cubes.signal_health_analyzer import SignalHealthAnalyzerCube
from app.schemas.cube import CubeCategory


@pytest.fixture
def cube():
    return SignalHealthAnalyzerCube()


# ============================================================
# Metadata tests
# ============================================================


def test_cube_metadata(cube):
    """cube_id is 'signal_health_analyzer' and category is ANALYSIS."""
    assert cube.cube_id == "signal_health_analyzer"
    assert cube.category == CubeCategory.ANALYSIS


def test_cube_inputs(cube):
    """Cube has hex_list, full_result, target_phase, classify_mode inputs."""
    input_names = {p.name for p in cube.inputs}
    assert input_names == {"hex_list", "full_result", "target_phase", "classify_mode"}


def test_cube_outputs(cube):
    """Cube has flight_ids, count, events, stats_summary outputs."""
    output_names = {p.name for p in cube.outputs}
    assert output_names == {"flight_ids", "count", "events", "stats_summary"}


# ============================================================
# Empty hex_list guard
# ============================================================


@pytest.mark.asyncio
async def test_empty_hex_list_guard(cube):
    """Empty hex_list returns empty result immediately."""
    result = await cube.execute(hex_list=[])
    assert result == {
        "flight_ids": [],
        "count": 0,
        "events": [],
        "stats_summary": {},
    }


@pytest.mark.asyncio
async def test_no_hex_list_returns_empty(cube):
    """No hex_list at all returns empty result."""
    result = await cube.execute()
    assert result["count"] == 0
    assert result["flight_ids"] == []


# ============================================================
# full_result extraction
# ============================================================


@pytest.mark.asyncio
async def test_full_result_extraction_hex_list(cube):
    """full_result with hex_list key extracts hexes correctly."""
    with patch.object(cube, "_analyze_hex", new_callable=AsyncMock, return_value=[]), \
         patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}):
        result = await cube.execute(
            hex_list=[],
            full_result={"hex_list": ["abc123", "def456"]},
            classify_mode=["Stable"],
        )
    # Both hexes are stable (no events) so Stable mode returns them
    assert result["count"] == 2
    assert sorted(result["flight_ids"]) == ["abc123", "def456"]


@pytest.mark.asyncio
async def test_full_result_extraction_flight_ids(cube):
    """full_result with flight_ids key (no hex_list) extracts hexes correctly."""
    with patch.object(cube, "_analyze_hex", new_callable=AsyncMock, return_value=[]), \
         patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}):
        result = await cube.execute(
            hex_list=[],
            full_result={"flight_ids": ["aaa111"]},
            classify_mode=["Stable"],
        )
    assert result["count"] == 1
    assert result["flight_ids"] == ["aaa111"]


# ============================================================
# Basic detection orchestration
# ============================================================


SAMPLE_INTEGRITY_EVENT = {
    "hex": "abc123",
    "source": "rule_based",
    "type": "gap_detection",
    "start_ts": "2026-01-01T00:00:00",
    "end_ts": "2026-01-01T00:10:00",
    "duration_s": 600,
    "entry_lat": 32.0,
    "entry_lon": 34.0,
    "exit_lat": 32.1,
    "exit_lon": 34.1,
    "last_alt_baro": 30000,
}


@pytest.mark.asyncio
async def test_basic_detection(cube):
    """Cube orchestrates rule-based and Kalman layers, combines results."""
    # Rule-based mocks
    mock_integrity = AsyncMock(return_value=[SAMPLE_INTEGRITY_EVENT])
    mock_shutdowns = AsyncMock(return_value=[])
    mock_coverage = AsyncMock(return_value={"avg_gap": 10})
    mock_score = MagicMock(side_effect=lambda ev, _: {**ev, "jamming_score": 5})
    mock_classify = MagicMock(return_value="gps_jamming")

    # Kalman mock - returns normal (no event generated)
    mock_kalman_classify = AsyncMock(return_value={"classification": "normal"})
    mock_fetch_time = AsyncMock(return_value=(1000, 2000))

    with patch("app.cubes.signal_health_analyzer.detect_integrity_events_async", mock_integrity), \
         patch("app.cubes.signal_health_analyzer.detect_transponder_shutdowns_async", mock_shutdowns), \
         patch("app.cubes.signal_health_analyzer.get_coverage_baseline", mock_coverage), \
         patch("app.cubes.signal_health_analyzer.score_event", mock_score), \
         patch("app.cubes.signal_health_analyzer.classify_event", mock_classify), \
         patch("app.cubes.signal_health_analyzer.classify_flight_async", mock_kalman_classify), \
         patch("app.cubes.signal_health_analyzer.fetch_time_range_async", mock_fetch_time):
        result = await cube.execute(hex_list=["abc123"])

    assert result["count"] == 1
    assert "abc123" in result["flight_ids"]
    assert len(result["events"]) == 1
    assert result["events"][0]["category"] == "gps_jamming"
    assert result["stats_summary"] == {"gps_jamming": 1}


@pytest.mark.asyncio
async def test_kalman_non_normal_event(cube):
    """Non-normal Kalman classification generates a kalman event in output."""
    mock_integrity = AsyncMock(return_value=[])
    mock_shutdowns = AsyncMock(return_value=[])
    mock_coverage = AsyncMock(return_value={})

    kalman_result = {
        "classification": "gps_spoofing",
        "kalman_results": [{"flagged": True}, {"flagged": False}],
        "jumps": [{"km": 60}],
        "alt_divergence": [],
        "physics": {"confidence": 0.8},
        "start": "2026-01-01T00:00:00",
        "end": "2026-01-01T01:00:00",
    }
    mock_kalman_classify = AsyncMock(return_value=kalman_result)
    mock_fetch_time = AsyncMock(return_value=(1000, 2000))

    with patch("app.cubes.signal_health_analyzer.detect_integrity_events_async", mock_integrity), \
         patch("app.cubes.signal_health_analyzer.detect_transponder_shutdowns_async", mock_shutdowns), \
         patch("app.cubes.signal_health_analyzer.get_coverage_baseline", mock_coverage), \
         patch("app.cubes.signal_health_analyzer.classify_flight_async", mock_kalman_classify), \
         patch("app.cubes.signal_health_analyzer.fetch_time_range_async", mock_fetch_time):
        result = await cube.execute(hex_list=["abc123"])

    assert result["count"] == 1
    assert len(result["events"]) == 1
    ev = result["events"][0]
    assert ev["source"] == "kalman"
    assert ev["category"] == "gps_spoofing"
    assert ev["n_flagged"] == 1
    assert ev["n_jumps"] == 1
    assert ev["physics_confidence"] == 0.8


# ============================================================
# classify_mode filtering
# ============================================================


@pytest.mark.asyncio
async def test_classify_mode_anomaly(cube):
    """classify_mode=['Jamming'] only returns jamming-category events."""
    jamming_event = {**SAMPLE_INTEGRITY_EVENT, "category": "gps_jamming", "jamming_score": 5}
    normal_event = {**SAMPLE_INTEGRITY_EVENT, "hex": "def456", "category": "coverage_hole"}

    async def mock_analyze(hex_code, baseline, phase):
        if hex_code == "abc123":
            return [jamming_event]
        elif hex_code == "def456":
            return [normal_event]
        return []

    with patch.object(cube, "_analyze_hex", side_effect=mock_analyze), \
         patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}):
        result = await cube.execute(
            hex_list=["abc123", "def456"],
            classify_mode=["Jamming"],
        )

    assert result["count"] == 1
    assert result["flight_ids"] == ["abc123"]
    assert all(ev["category"] == "gps_jamming" for ev in result["events"])


@pytest.mark.asyncio
async def test_classify_mode_stable(cube):
    """classify_mode=['Stable'] returns hexes with zero non-normal events."""
    # abc123 has events, def456 has none (stable)
    async def mock_analyze(hex_code, baseline, phase):
        if hex_code == "abc123":
            return [{"hex": "abc123", "category": "gps_jamming"}]
        return []  # def456 is stable

    with patch.object(cube, "_analyze_hex", side_effect=mock_analyze), \
         patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}):
        result = await cube.execute(
            hex_list=["abc123", "def456"],
            classify_mode=["Stable"],
        )

    # Only def456 is stable (zero events)
    assert result["flight_ids"] == ["def456"]
    assert result["count"] == 1
    assert result["events"] == []  # Stable mode returns no events


# ============================================================
# target_phase filtering
# ============================================================


@pytest.mark.asyncio
async def test_target_phase_takeoff_filters_high_altitude(cube):
    """target_phase='takeoff' filters out events with altitude >= 5000ft."""
    high_alt_event = {
        **SAMPLE_INTEGRITY_EVENT,
        "last_alt_baro": 30000,
        "category": "gps_jamming",
    }
    low_alt_event = {
        **SAMPLE_INTEGRITY_EVENT,
        "last_alt_baro": 3000,
        "category": "gps_jamming",
    }

    mock_integrity = AsyncMock(return_value=[high_alt_event, low_alt_event])
    mock_shutdowns = AsyncMock(return_value=[])
    mock_coverage = AsyncMock(return_value={})
    mock_score = MagicMock(side_effect=lambda ev, _: ev)
    mock_classify = MagicMock(return_value="gps_jamming")
    mock_kalman = AsyncMock(return_value={"classification": "normal"})
    mock_fetch_time = AsyncMock(return_value=(1000, 2000))

    with patch("app.cubes.signal_health_analyzer.detect_integrity_events_async", mock_integrity), \
         patch("app.cubes.signal_health_analyzer.detect_transponder_shutdowns_async", mock_shutdowns), \
         patch("app.cubes.signal_health_analyzer.get_coverage_baseline", mock_coverage), \
         patch("app.cubes.signal_health_analyzer.score_event", mock_score), \
         patch("app.cubes.signal_health_analyzer.classify_event", mock_classify), \
         patch("app.cubes.signal_health_analyzer.classify_flight_async", mock_kalman), \
         patch("app.cubes.signal_health_analyzer.fetch_time_range_async", mock_fetch_time):
        result = await cube.execute(
            hex_list=["abc123"],
            target_phase="takeoff",
        )

    # Only the low altitude event should pass through
    assert len(result["events"]) == 1
    assert result["events"][0]["last_alt_baro"] == 3000


# ============================================================
# stats_summary
# ============================================================


@pytest.mark.asyncio
async def test_stats_summary(cube):
    """stats_summary includes event counts by category."""
    events = [
        {"hex": "a", "category": "gps_jamming"},
        {"hex": "b", "category": "gps_jamming"},
        {"hex": "c", "category": "gps_spoofing"},
    ]

    async def mock_analyze(hex_code, baseline, phase):
        idx = {"a": 0, "b": 1, "c": 2}.get(hex_code)
        if idx is not None:
            return [events[idx]]
        return []

    with patch.object(cube, "_analyze_hex", side_effect=mock_analyze), \
         patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}):
        result = await cube.execute(hex_list=["a", "b", "c"])

    assert result["stats_summary"] == {"gps_jamming": 2, "gps_spoofing": 1}
