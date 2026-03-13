"""Tests for SignalHealthAnalyzerCube.

Tests cover:
- Cube metadata (cube_id, category)
- Input/output definitions
- Empty hex_list guard
- full_result extraction (hex_list and flight_ids keys)
- Basic detection orchestration (rule-based + Kalman, batch architecture)
- classify_mode filtering (anomaly, Stable)
- target_phase filtering (takeoff altitude filter)
- stats_summary output
- n_severe_alt_div in kalman events
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.cubes.signal_health_analyzer import SignalHealthAnalyzerCube, kalman_event_from_result
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
    assert input_names == {"hex_list", "full_result", "target_phase", "classify_mode", "lookback_hours"}


def test_cube_outputs(cube):
    """Cube has flight_ids, count, events, stats_summary outputs."""
    output_names = {p.name for p in cube.outputs}
    assert output_names == {"flight_ids", "count", "events", "stats_summary"}


def test_no_analyze_hex_method(cube):
    """_analyze_hex is removed — batch architecture does not use per-hex method."""
    assert not hasattr(cube, "_analyze_hex")


# ============================================================
# kalman_event_from_result helper
# ============================================================


def test_kalman_event_n_severe_alt_div():
    """kalman_event_from_result includes n_severe_alt_div field."""
    result = {
        "classification": "anomalous",
        "alt_divergence": [{"severe": True}, {"severe": False}, {"severe": True}],
        "kalman_results": [],
        "jumps": [],
        "physics": {},
        "start": "2026-01-01T00:00:00",
        "end": "2026-01-01T01:00:00",
    }
    ev = kalman_event_from_result("abc123", result)
    assert "n_severe_alt_div" in ev
    assert ev["n_severe_alt_div"] == 2
    assert ev["n_alt_divergence"] == 3


def test_kalman_event_zero_severe():
    """n_severe_alt_div is 0 when no severe alt divergences."""
    result = {
        "classification": "anomalous",
        "alt_divergence": [{"severe": False}, {"severe": False}],
        "kalman_results": [{"flagged": True}],
        "jumps": [],
        "physics": {"confidence": 0.3},
        "start": "x",
        "end": "y",
    }
    ev = kalman_event_from_result("hex1", result)
    assert ev["n_severe_alt_div"] == 0
    assert ev["n_alt_divergence"] == 2
    assert ev["n_flagged"] == 1


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
    with patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_integrity_events_batch_async", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_shutdowns_batch_async", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.fetch_positions_batch_async", new_callable=AsyncMock, return_value={}):
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
    with patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_integrity_events_batch_async", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_shutdowns_batch_async", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.fetch_positions_batch_async", new_callable=AsyncMock, return_value={}):
        result = await cube.execute(
            hex_list=[],
            full_result={"flight_ids": ["aaa111"]},
            classify_mode=["Stable"],
        )
    assert result["count"] == 1
    assert result["flight_ids"] == ["aaa111"]


# ============================================================
# Basic detection orchestration (batch architecture)
# ============================================================


SAMPLE_INTEGRITY_EVENT = {
    "hex": "abc123",
    "source": "integrity_drop",
    "start_ts": "2026-01-01T00:00:00",
    "end_ts": "2026-01-01T00:10:00",
    "duration_s": 600,
    "entry_lat": 32.0,
    "entry_lon": 34.0,
    "exit_lat": 32.1,
    "exit_lon": 34.1,
    "last_alt_baro": 30000,
    "nacp_zero": True,
    "nic_zero": False,
    "nic_low_7": False,
    "gva_zero": False,
    "nacv_high": False,
    "has_gps_ok_before": True,
    "median_rssi": -10.0,
    "mean_seen_pos": 3.0,
    "msg_rate": 1.0,
    "mean_alt_divergence_ft": None,
    "max_alt_divergence_ft": None,
    "version": 2,
    "region": "LLLL",
    "n_reports": 5,
}


@pytest.mark.asyncio
async def test_basic_detection(cube):
    """Cube orchestrates rule-based and Kalman layers, combines results."""
    mock_score = MagicMock(side_effect=lambda ev, _: {**ev, "jamming_score": 5, "spoofing_score": 0, "coverage_score": 0, "in_coverage_hole": False, "evidence": ""})
    mock_classify = MagicMock(return_value="gps_jamming")
    mock_kalman_classify = AsyncMock(return_value={"classification": "normal"})

    with patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_integrity_events_batch_async",
               new_callable=AsyncMock, return_value={"abc123": [SAMPLE_INTEGRITY_EVENT]}), \
         patch("app.cubes.signal_health_analyzer.detect_shutdowns_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.fetch_positions_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.score_event", mock_score), \
         patch("app.cubes.signal_health_analyzer.classify_event", mock_classify), \
         patch("app.cubes.signal_health_analyzer.classify_flight_async", mock_kalman_classify):
        result = await cube.execute(hex_list=["abc123"])

    assert result["count"] == 1
    assert "abc123" in result["flight_ids"]
    assert len(result["events"]) == 1
    assert result["events"][0]["category"] == "gps_jamming"
    assert result["stats_summary"] == {"gps_jamming": 1}


@pytest.mark.asyncio
async def test_kalman_non_normal_event(cube):
    """Non-normal Kalman classification generates a kalman event in output."""
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

    with patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_integrity_events_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_shutdowns_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.fetch_positions_batch_async",
               new_callable=AsyncMock, return_value={"abc123": [{"ts": "t", "lat": 1.0, "lon": 1.0}]}), \
         patch("app.cubes.signal_health_analyzer.classify_flight_async", mock_kalman_classify):
        result = await cube.execute(hex_list=["abc123"])

    assert result["count"] == 1
    assert len(result["events"]) == 1
    ev = result["events"][0]
    assert ev["source"] == "kalman"
    assert ev["category"] == "gps_spoofing"
    assert ev["n_flagged"] == 1
    assert ev["n_jumps"] == 1
    assert ev["physics_confidence"] == 0.8
    assert "n_severe_alt_div" in ev


@pytest.mark.asyncio
async def test_kalman_skipped_when_no_positions(cube):
    """Kalman analysis is skipped for hexes with no pre-fetched positions."""
    mock_kalman_classify = AsyncMock(return_value={"classification": "gps_spoofing"})

    with patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_integrity_events_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_shutdowns_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.fetch_positions_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.classify_flight_async", mock_kalman_classify):
        result = await cube.execute(hex_list=["abc123"])

    # No positions → Kalman not called → hex is stable
    mock_kalman_classify.assert_not_called()
    assert result["count"] == 0


# ============================================================
# classify_mode filtering
# ============================================================


@pytest.mark.asyncio
async def test_classify_mode_anomaly(cube):
    """classify_mode=['Jamming'] only returns jamming-category events."""
    jamming_event = {**SAMPLE_INTEGRITY_EVENT, "hex": "abc123"}
    coverage_event = {**SAMPLE_INTEGRITY_EVENT, "hex": "def456"}

    mock_score = MagicMock(side_effect=lambda ev, _: {**ev, "jamming_score": 5, "spoofing_score": 0, "coverage_score": 0, "in_coverage_hole": False, "evidence": ""})

    def mock_classify_fn(ev):
        if ev.get("hex") == "abc123":
            return "gps_jamming"
        return "coverage_hole"

    mock_classify = MagicMock(side_effect=mock_classify_fn)

    with patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_integrity_events_batch_async",
               new_callable=AsyncMock, return_value={
                   "abc123": [jamming_event],
                   "def456": [coverage_event],
               }), \
         patch("app.cubes.signal_health_analyzer.detect_shutdowns_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.fetch_positions_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.score_event", mock_score), \
         patch("app.cubes.signal_health_analyzer.classify_event", mock_classify):
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
    mock_score = MagicMock(side_effect=lambda ev, _: {**ev, "jamming_score": 5, "spoofing_score": 0, "coverage_score": 0, "in_coverage_hole": False, "evidence": ""})
    mock_classify = MagicMock(return_value="gps_jamming")

    with patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_integrity_events_batch_async",
               new_callable=AsyncMock, return_value={
                   "abc123": [SAMPLE_INTEGRITY_EVENT],
               }), \
         patch("app.cubes.signal_health_analyzer.detect_shutdowns_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.fetch_positions_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.score_event", mock_score), \
         patch("app.cubes.signal_health_analyzer.classify_event", mock_classify):
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
    high_alt_event = {**SAMPLE_INTEGRITY_EVENT, "last_alt_baro": 30000}
    low_alt_event = {**SAMPLE_INTEGRITY_EVENT, "last_alt_baro": 3000}

    mock_score = MagicMock(side_effect=lambda ev, _: ev)
    mock_classify = MagicMock(return_value="gps_jamming")
    mock_kalman = AsyncMock(return_value={"classification": "normal"})

    with patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_integrity_events_batch_async",
               new_callable=AsyncMock, return_value={
                   "abc123": [high_alt_event, low_alt_event],
               }), \
         patch("app.cubes.signal_health_analyzer.detect_shutdowns_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.fetch_positions_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.score_event", mock_score), \
         patch("app.cubes.signal_health_analyzer.classify_event", mock_classify), \
         patch("app.cubes.signal_health_analyzer.classify_flight_async", mock_kalman):
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
    event_a = {**SAMPLE_INTEGRITY_EVENT, "hex": "a"}
    event_b = {**SAMPLE_INTEGRITY_EVENT, "hex": "b"}
    event_c = {**SAMPLE_INTEGRITY_EVENT, "hex": "c"}

    def mock_classify_fn(ev):
        if ev.get("hex") in ("a", "b"):
            return "gps_jamming"
        return "gps_spoofing"

    mock_score = MagicMock(side_effect=lambda ev, _: {**ev, "jamming_score": 5, "spoofing_score": 0, "coverage_score": 0, "in_coverage_hole": False, "evidence": ""})
    mock_classify = MagicMock(side_effect=mock_classify_fn)

    with patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_integrity_events_batch_async",
               new_callable=AsyncMock, return_value={
                   "a": [event_a],
                   "b": [event_b],
                   "c": [event_c],
               }), \
         patch("app.cubes.signal_health_analyzer.detect_shutdowns_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.fetch_positions_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.score_event", mock_score), \
         patch("app.cubes.signal_health_analyzer.classify_event", mock_classify):
        result = await cube.execute(hex_list=["a", "b", "c"])

    assert result["stats_summary"] == {"gps_jamming": 2, "gps_spoofing": 1}


# ============================================================
# Error handling
# ============================================================


@pytest.mark.asyncio
async def test_per_hex_error_skips_hex(cube):
    """An error during per-hex processing skips the hex with a warning."""
    def bad_score(ev, baseline):
        raise RuntimeError("simulated error")

    with patch("app.cubes.signal_health_analyzer.get_coverage_baseline", new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.detect_integrity_events_batch_async",
               new_callable=AsyncMock, return_value={"abc123": [SAMPLE_INTEGRITY_EVENT]}), \
         patch("app.cubes.signal_health_analyzer.detect_shutdowns_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.fetch_positions_batch_async",
               new_callable=AsyncMock, return_value={}), \
         patch("app.cubes.signal_health_analyzer.score_event", MagicMock(side_effect=bad_score)):
        result = await cube.execute(hex_list=["abc123"])

    # Error hex should be silently skipped — returns empty
    assert result["count"] == 0
    assert result["events"] == []
