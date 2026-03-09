"""Tests for rule_based.py — GPS anomaly scoring and classification.

Tests cover:
- score_event: jamming, spoofing, transponder_off passthrough, normal scenarios
- classify_event: gps_jamming, gps_spoofing, coverage_hole, probable_jamming,
  transponder_off, ambiguous classifications
- detect_integrity_events_async: mock DB with integrity drops, empty result
- detect_transponder_shutdowns_async: mock DB with transponder gaps
- get_coverage_baseline: mock DB returning coverage stats
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Helpers
# ============================================================

def make_integrity_event(**overrides):
    """Build a scored integrity event dict with sensible defaults."""
    event = {
        "hex": "abc123",
        "source": "integrity_drop",
        "start_ts": "2026-01-01T00:00:00+00:00",
        "end_ts": "2026-01-01T00:05:00+00:00",
        "duration_s": 300.0,
        "n_reports": 50,
        "entry_lat": 32.0,
        "entry_lon": 34.0,
        "exit_lat": 32.1,
        "exit_lon": 34.1,
        "version": 2,
        "nacp_zero": False,
        "nic_zero": False,
        "nic_low_7": False,
        "gva_zero": False,
        "nacv_high": False,
        "has_gps_ok_before": False,
        "median_rssi": -5.0,
        "mean_seen_pos": 10.0,
        "msg_rate": 2.0,
        "mean_alt_divergence_ft": 200.0,
        "max_alt_divergence_ft": 300.0,
        "region": "IL",
    }
    event.update(overrides)
    return event


def empty_baseline():
    """Return an empty coverage baseline dict."""
    return {}


def baseline_with_hole(lat=32.0, lon=34.0):
    """Return a coverage baseline where the (lat, lon) cell is a coverage hole."""
    import math
    grid = 0.5
    lat_cell = math.floor(lat / grid) * grid
    lon_cell = math.floor(lon / grid) * grid
    return {
        (lat_cell, lon_cell): {
            "median_rssi": -25.0,
            "reports_per_hour": 3.0,
            "temporal_coverage": 0.2,
            "is_coverage_hole": True,
        }
    }


def baseline_no_hole(lat=32.0, lon=34.0):
    """Return a coverage baseline where the (lat, lon) cell is healthy."""
    import math
    grid = 0.5
    lat_cell = math.floor(lat / grid) * grid
    lon_cell = math.floor(lon / grid) * grid
    return {
        (lat_cell, lon_cell): {
            "median_rssi": -3.0,
            "reports_per_hour": 60.0,
            "temporal_coverage": 0.9,
            "is_coverage_hole": False,
        }
    }


# ============================================================
# score_event — pure function tests
# ============================================================


class TestScoreEvent:

    def test_score_event_jamming(self):
        """Event with strong jamming indicators -> high jamming_score (>=6), low spoofing."""
        from app.signal.rule_based import score_event

        event = make_integrity_event(
            version=2,
            nacp_zero=True,       # +3 (V2 weight)
            nic_zero=True,        # +2 (V2 weight)
            gva_zero=True,        # +1 (V2)
            nacv_high=True,       # +1
            has_gps_ok_before=True,  # +3
            median_rssi=-5.0,     # >-20 -> +1 jam
            mean_seen_pos=3.0,    # <5 -> +1
            msg_rate=2.0,         # >0 -> +1
            mean_alt_divergence_ft=200.0,  # below threshold, no spoofing points
        )
        baseline = baseline_no_hole()
        scored = score_event(event, baseline)

        assert scored["jamming_score"] >= 6
        assert scored["spoofing_score"] < 2
        assert scored["in_coverage_hole"] is False
        assert "evidence" in scored

    def test_score_event_spoofing(self):
        """Event with alt divergence and NIC anomalies -> high spoofing_score."""
        from app.signal.rule_based import score_event

        event = make_integrity_event(
            version=2,
            nacp_zero=False,
            nic_zero=False,
            nic_low_7=True,       # nic_low_7 AND NOT nacp_zero -> +2 spoof
            mean_alt_divergence_ft=2500.0,  # >1000 -> +2, >2000 -> +1 more = +3 spoof
            has_gps_ok_before=False,
            median_rssi=-5.0,
        )
        baseline = empty_baseline()
        scored = score_event(event, baseline)

        assert scored["spoofing_score"] >= 4
        assert "alt_div" in scored["evidence"]

    def test_score_event_transponder_off_passthrough(self):
        """Transponder-off events (source=gap_detection) get scored normally by score_event.

        Classification, not scoring, handles the passthrough.
        """
        from app.signal.rule_based import score_event

        event = make_integrity_event(
            source="gap_detection",
            nacp_zero=False,
            nic_zero=False,
            has_gps_ok_before=False,
            mean_alt_divergence_ft=0,
        )
        baseline = empty_baseline()
        scored = score_event(event, baseline)

        # score_event processes it like any event
        assert "jamming_score" in scored
        assert "spoofing_score" in scored

    def test_score_event_normal(self):
        """Normal event with healthy indicators -> low scores."""
        from app.signal.rule_based import score_event

        event = make_integrity_event(
            version=2,
            nacp_zero=False,
            nic_zero=False,
            nic_low_7=False,
            gva_zero=False,
            nacv_high=False,
            has_gps_ok_before=False,
            median_rssi=-5.0,       # good RSSI -> +1 jam only
            mean_seen_pos=10.0,     # 5-15 range, no points
            msg_rate=0,             # 0 -> no points
            mean_alt_divergence_ft=100.0,  # below threshold
        )
        baseline = empty_baseline()
        scored = score_event(event, baseline)

        assert scored["jamming_score"] <= 2
        assert scored["spoofing_score"] == 0

    def test_score_event_coverage_hole(self):
        """Event in a coverage hole -> coverage_score increases."""
        from app.signal.rule_based import score_event

        event = make_integrity_event(
            version=2,
            nacp_zero=False,
            nic_zero=False,
            has_gps_ok_before=False,
            median_rssi=-25.0,      # below -20 -> +2 cov (not jam)
            mean_seen_pos=20.0,     # >15 -> +1 cov
            entry_lat=32.0,
            entry_lon=34.0,
        )
        baseline = baseline_with_hole(32.0, 34.0)
        scored = score_event(event, baseline)

        assert scored["in_coverage_hole"] is True
        assert scored["coverage_score"] >= 3  # low RSSI(2) + hole(1)


# ============================================================
# classify_event — pure function tests
# ============================================================


class TestClassifyEvent:

    def test_classify_event_jamming(self):
        """High jamming_score >= 6 -> gps_jamming."""
        from app.signal.rule_based import classify_event

        event = {"source": "integrity_drop", "jamming_score": 8, "spoofing_score": 1, "coverage_score": 0}
        assert classify_event(event) == "gps_jamming"

    def test_classify_event_jamming_moderate(self):
        """jam >= 4 and jam > cov -> gps_jamming."""
        from app.signal.rule_based import classify_event

        event = {"source": "integrity_drop", "jamming_score": 5, "spoofing_score": 0, "coverage_score": 2}
        assert classify_event(event) == "gps_jamming"

    def test_classify_event_spoofing(self):
        """spoofing_score >= 4 -> gps_spoofing."""
        from app.signal.rule_based import classify_event

        event = {"source": "integrity_drop", "jamming_score": 3, "spoofing_score": 5, "coverage_score": 0}
        assert classify_event(event) == "gps_spoofing"

    def test_classify_event_coverage_hole(self):
        """cov >= 2 and cov > jam -> coverage_hole."""
        from app.signal.rule_based import classify_event

        event = {"source": "integrity_drop", "jamming_score": 1, "spoofing_score": 0, "coverage_score": 3}
        assert classify_event(event) == "coverage_hole"

    def test_classify_event_probable_jamming(self):
        """jam >= 2 but below full jamming threshold -> probable_jamming."""
        from app.signal.rule_based import classify_event

        event = {"source": "integrity_drop", "jamming_score": 3, "spoofing_score": 0, "coverage_score": 3}
        # jam >= 2, but cov is not > jam, so coverage_hole doesn't apply; jam < 4 so not full jamming
        # Actually: jam=3, cov=3 -> cov >= 2 and cov > jam? No, cov == jam.
        # So neither gps_jamming nor coverage_hole. jam >= 2 -> probable_jamming.
        assert classify_event(event) == "probable_jamming"

    def test_classify_event_ambiguous(self):
        """Low scores -> ambiguous."""
        from app.signal.rule_based import classify_event

        event = {"source": "integrity_drop", "jamming_score": 1, "spoofing_score": 0, "coverage_score": 0}
        assert classify_event(event) == "ambiguous"

    def test_classify_event_transponder_off(self):
        """source=gap_detection -> transponder_off regardless of scores."""
        from app.signal.rule_based import classify_event

        event = {"source": "gap_detection", "jamming_score": 10, "spoofing_score": 10, "coverage_score": 10}
        assert classify_event(event) == "transponder_off"


# ============================================================
# Async function tests — mocked engine
# ============================================================


class TestDetectIntegrityEventsAsync:

    @pytest.mark.asyncio
    async def test_detect_integrity_events_async(self):
        """Mock DB returning integrity rows -> events detected with correct structure."""
        from app.signal.rule_based import detect_integrity_events_async

        ts1 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 1, 1, 12, 5, 0, tzinfo=timezone.utc)

        # Build a fake row matching the SELECT columns in detect_integrity_events_async
        fake_row = (
            "abc123",      # hex
            1,             # event_id
            ts1,           # start_ts
            ts2,           # end_ts
            300.0,         # duration_s
            50,            # n_reports
            32.0,          # entry_lat
            34.0,          # entry_lon
            32.1,          # exit_lat
            34.1,          # exit_lon
            2,             # version
            True,          # nacp_zero
            False,         # nic_zero
            True,          # nic_low_7
            False,         # gva_zero
            False,         # nacv_high
            "IL",          # region
            -5.0,          # median_rssi
            True,          # has_gps_ok_before
            8.0,           # mean_seen_pos
            1.5,           # msg_rate
            500.0,         # mean_alt_divergence_ft
            800.0,         # max_alt_divergence_ft
            32.05,         # gps_ok_lat
            34.05,         # gps_ok_lon
        )

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [fake_row]

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.signal.rule_based.engine", mock_engine):
            events = await detect_integrity_events_async(
                "abc123",
                datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            )

        assert len(events) == 1
        ev = events[0]
        assert ev["hex"] == "abc123"
        assert ev["source"] == "integrity_drop"
        assert ev["nacp_zero"] is True
        assert ev["n_reports"] == 50
        assert ev["duration_s"] == 300.0
        assert ev["median_rssi"] == -5.0

    @pytest.mark.asyncio
    async def test_detect_integrity_events_empty(self):
        """Empty DB result -> no events."""
        from app.signal.rule_based import detect_integrity_events_async

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.signal.rule_based.engine", mock_engine):
            events = await detect_integrity_events_async(
                "abc123",
                datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            )

        assert events == []


class TestDetectTransponderShutdownsAsync:

    @pytest.mark.asyncio
    async def test_detect_transponder_shutdowns_async(self):
        """Mock DB with transponder gap row -> shutdown event detected."""
        from app.signal.rule_based import detect_transponder_shutdowns_async

        ts_last = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ts_reappear = datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc)

        # Row columns: last_seen_ts, reappear_ts, gap_duration_s,
        #   last_lat, last_lon, last_alt_baro, reappear_lat, reappear_lon,
        #   last_nac_p, last_rssi, region
        fake_row = (
            ts_last,       # last_seen_ts
            ts_reappear,   # reappear_ts
            1800.0,        # gap_duration_s (30 min)
            32.0,          # last_lat
            34.0,          # last_lon
            35000,         # last_alt_baro
            32.5,          # reappear_lat
            34.5,          # reappear_lon
            11,            # last_nac_p
            -3.0,          # last_rssi
            "IL",          # region
        )

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [fake_row]

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.signal.rule_based.engine", mock_engine):
            events = await detect_transponder_shutdowns_async(
                "abc123",
                datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            )

        assert len(events) == 1
        ev = events[0]
        assert ev["hex"] == "abc123"
        assert ev["category"] == "transponder_off"
        assert ev["source"] == "gap_detection"
        assert ev["duration_s"] == 1800.0
        assert ev["jamming_score"] == 0
        assert ev["spoofing_score"] == 0


class TestGetCoverageBaseline:

    @pytest.mark.asyncio
    async def test_get_coverage_baseline(self):
        """Mock DB returning coverage stats -> baseline dict with correct structure."""
        from app.signal.rule_based import (
            build_coverage_baseline_async,
        )

        # Row: lat_cell, lon_cell, median_rssi, total_reports,
        #      reports_per_hour, temporal_coverage
        fake_row = (32.0, 34.0, -8.0, 500, 45.0, 0.85)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [fake_row]

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.signal.rule_based.engine", mock_engine):
            baseline = await build_coverage_baseline_async(lookback_days=7)

        assert (32.0, 34.0) in baseline
        cell = baseline[(32.0, 34.0)]
        assert cell["median_rssi"] == -8.0
        assert cell["reports_per_hour"] == 45.0
        assert cell["temporal_coverage"] == 0.85
        assert cell["is_coverage_hole"] is False
