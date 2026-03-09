"""Tests for kalman.py — Kalman filter GPS anomaly detection.

Tests cover:
- haversine_km: known distance calculations
- latlon_to_enu: coordinate conversion
- kalman_filter: normal trajectory (no flags) and jump trajectory (flags)
- detect_position_jumps: jump detection and normal trajectory
- detect_altitude_divergence: divergent and consistent altitudes
- physics_cross_validation: impossible speed and normal scenarios
- classify_flight: aggregated classification
- classify_flight_async: mocked DB async orchestration
- fetch_positions_async: mocked DB position fetching
"""

import math
import pytest
import numpy as np
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Helpers
# ============================================================

def make_position(ts, lat, lon, alt_baro=35000, alt_geom=35000,
                  gs=450, tas=440, track=90, true_heading=88,
                  nac_p=11, nic=8, baro_rate=0, geom_rate=0,
                  on_ground=False):
    """Build a position dict matching DB row structure for kalman tests."""
    return {
        "ts": ts,
        "lat": lat,
        "lon": lon,
        "alt_baro": alt_baro,
        "alt_geom": alt_geom,
        "gs": gs,
        "tas": tas,
        "track": track,
        "true_heading": true_heading,
        "nac_p": nac_p,
        "nic": nic,
        "baro_rate": baro_rate,
        "geom_rate": geom_rate,
        "on_ground": on_ground,
    }


def smooth_trajectory(n=20, start_lat=32.0, start_lon=34.0, dt_s=10):
    """Generate a smooth straight-line trajectory (heading east)."""
    base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    positions = []
    for i in range(n):
        ts = base_ts + timedelta(seconds=i * dt_s)
        lat = start_lat
        lon = start_lon + i * 0.01  # ~1.1 km per step at lat 32
        positions.append(make_position(ts=ts, lat=lat, lon=lon))
    return positions


# ============================================================
# haversine_km — pure function
# ============================================================


class TestHaversineKm:

    def test_haversine_km_known_distance(self):
        """TLV (32.01, 34.77) to Jerusalem (31.77, 35.21) ~ 50-60 km."""
        from app.signal.kalman import haversine_km

        dist = haversine_km(32.01, 34.77, 31.77, 35.21)
        assert 40 < dist < 70  # approximately 50 km

    def test_haversine_km_same_point(self):
        """Same point -> 0 km."""
        from app.signal.kalman import haversine_km

        dist = haversine_km(32.0, 34.0, 32.0, 34.0)
        assert dist == 0.0

    def test_haversine_km_antipodal(self):
        """Opposite points on Earth -> ~20000 km."""
        from app.signal.kalman import haversine_km

        dist = haversine_km(0, 0, 0, 180)
        assert 19900 < dist < 20100


# ============================================================
# latlon_to_enu — pure function
# ============================================================


class TestLatlonToEnu:

    def test_latlon_to_enu_same_point(self):
        """Same point as reference -> (0, 0)."""
        from app.signal.kalman import latlon_to_enu

        e, n = latlon_to_enu(32.0, 34.0, 32.0, 34.0)
        assert abs(e) < 1.0  # sub-meter
        assert abs(n) < 1.0

    def test_latlon_to_enu_east_offset(self):
        """Point 1 degree east at equator -> ~111 km east."""
        from app.signal.kalman import latlon_to_enu

        e, n = latlon_to_enu(0.0, 1.0, 0.0, 0.0)
        assert 110000 < e < 112000  # ~111 km in meters
        assert abs(n) < 1.0

    def test_latlon_to_enu_north_offset(self):
        """Point 1 degree north -> ~111 km north."""
        from app.signal.kalman import latlon_to_enu

        e, n = latlon_to_enu(1.0, 0.0, 0.0, 0.0)
        assert abs(e) < 1.0
        assert 110000 < n < 112000


# ============================================================
# kalman_filter — pure function
# ============================================================


class TestKalmanFilter:

    def test_kalman_filter_normal(self):
        """Smooth trajectory -> no flagged points."""
        from app.signal.kalman import kalman_filter

        positions = smooth_trajectory(n=20, dt_s=10)
        results = kalman_filter(positions)

        assert len(results) > 0
        flagged = [r for r in results if r["flagged"]]
        assert len(flagged) == 0

    def test_kalman_filter_jump(self):
        """Trajectory with a sudden 100km jump -> at least one flagged point."""
        from app.signal.kalman import kalman_filter

        positions = smooth_trajectory(n=10, dt_s=10)
        # Insert a 100km jump at position 7
        jump_pos = make_position(
            ts=positions[6]["ts"] + timedelta(seconds=10),
            lat=positions[6]["lat"] + 1.0,  # ~111 km north
            lon=positions[6]["lon"],
        )
        positions[7] = jump_pos
        # Fix timestamps to be sequential
        for i in range(8, len(positions)):
            positions[i] = make_position(
                ts=positions[7]["ts"] + timedelta(seconds=(i - 7) * 10),
                lat=positions[i]["lat"],
                lon=positions[i]["lon"],
            )

        results = kalman_filter(positions)
        flagged = [r for r in results if r["flagged"]]
        assert len(flagged) >= 1

    def test_kalman_filter_too_few_positions(self):
        """Less than 3 positions -> empty results."""
        from app.signal.kalman import kalman_filter

        positions = smooth_trajectory(n=2)
        results = kalman_filter(positions)
        assert results == []


# ============================================================
# detect_position_jumps — pure function
# ============================================================


class TestDetectPositionJumps:

    def test_detect_position_jumps_detected(self):
        """Positions with gap > POSITION_JUMP_KM (55.56 km) within 30s -> detected."""
        from app.signal.kalman import detect_position_jumps

        base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        positions = [
            make_position(ts=base_ts, lat=32.0, lon=34.0),
            make_position(ts=base_ts + timedelta(seconds=10), lat=32.0, lon=35.0),
            # ~85 km east, within 10s
        ]
        jumps = detect_position_jumps(positions)
        assert len(jumps) == 1
        assert jumps[0]["dist_km"] > 55.56

    def test_detect_position_jumps_normal(self):
        """Smooth positions -> no jumps."""
        from app.signal.kalman import detect_position_jumps

        positions = smooth_trajectory(n=10, dt_s=10)
        jumps = detect_position_jumps(positions)
        assert len(jumps) == 0

    def test_detect_position_jumps_large_dt_ignored(self):
        """Gap > 30s between reports is ignored (not a jump)."""
        from app.signal.kalman import detect_position_jumps

        base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        positions = [
            make_position(ts=base_ts, lat=32.0, lon=34.0),
            make_position(ts=base_ts + timedelta(seconds=60), lat=32.0, lon=35.0),
            # >30s gap, even though distance is large, it's ignored
        ]
        jumps = detect_position_jumps(positions)
        assert len(jumps) == 0


# ============================================================
# detect_altitude_divergence — pure function
# ============================================================


class TestDetectAltitudeDivergence:

    def test_detect_altitude_divergence_detected(self):
        """Baro vs geometric altitude diff > 1000ft -> detected."""
        from app.signal.kalman import detect_altitude_divergence

        base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        positions = [
            make_position(ts=base_ts, lat=32.0, lon=34.0, alt_baro=35000, alt_geom=33500),
            make_position(ts=base_ts + timedelta(seconds=10), lat=32.0, lon=34.01, alt_baro=35000, alt_geom=32000),
        ]
        divs = detect_altitude_divergence(positions)
        assert len(divs) == 2
        assert divs[0]["divergence_ft"] == 1500
        assert divs[1]["divergence_ft"] == 3000
        assert divs[1]["severe"] is True  # >2000ft

    def test_detect_altitude_divergence_normal(self):
        """Consistent altitudes -> no divergence."""
        from app.signal.kalman import detect_altitude_divergence

        positions = smooth_trajectory(n=5)  # alt_baro == alt_geom == 35000
        divs = detect_altitude_divergence(positions)
        assert len(divs) == 0

    def test_detect_altitude_divergence_missing_data(self):
        """Missing alt_geom -> skipped, not flagged."""
        from app.signal.kalman import detect_altitude_divergence

        base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        positions = [
            make_position(ts=base_ts, lat=32.0, lon=34.0, alt_baro=35000, alt_geom=None),
        ]
        divs = detect_altitude_divergence(positions)
        assert len(divs) == 0


# ============================================================
# physics_cross_validation — pure function
# ============================================================


class TestPhysicsCrossValidation:

    def test_physics_cross_validation_normal(self):
        """Normal consistent sensor readings -> low confidence (no anomaly)."""
        from app.signal.kalman import physics_cross_validation

        positions = smooth_trajectory(n=5)
        result = physics_cross_validation(positions)
        assert result["confidence"] < 0.5
        assert "n_checks_total" in result

    def test_physics_cross_validation_anomalous(self):
        """Large GS-TAS divergence and alt divergence -> high confidence."""
        from app.signal.kalman import physics_cross_validation

        base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        positions = [
            make_position(ts=base_ts + timedelta(seconds=i * 10),
                          lat=32.0, lon=34.0 + i * 0.01,
                          alt_baro=35000, alt_geom=33000,  # 2000ft divergence
                          gs=500, tas=200,  # 300kt GS-TAS diff
                          track=90, true_heading=180,  # 90 deg heading diff
                          baro_rate=0, geom_rate=1500)  # 1500 fpm vrate diff
            for i in range(5)
        ]
        result = physics_cross_validation(positions)
        assert result["confidence"] >= 0.5
        assert result["n_checks_passed"] >= 2


# ============================================================
# classify_flight — pure function
# ============================================================


class TestClassifyFlight:

    def test_classify_flight_normal(self):
        """No flags, no jumps, no divergence -> normal."""
        from app.signal.kalman import classify_flight

        kalman_results = [{"flagged": False} for _ in range(20)]
        assert classify_flight(kalman_results, [], [], {"confidence": 0.0}) == "normal"

    def test_classify_flight_spoofing(self):
        """Multiple corroborating signals -> gps_spoofing."""
        from app.signal.kalman import classify_flight

        # >5% flagged + systematic jumps + alt divergence = 3 signals >= 2
        kalman_results = [{"flagged": i < 5} for i in range(20)]  # 25% flagged
        jumps = [{"ts": None}, {"ts": None}]  # 2 jumps = systematic
        alt_div = [{"severe": True}]  # significant alt divergence
        physics = {"confidence": 0.6}

        result = classify_flight(kalman_results, jumps, alt_div, physics)
        assert result == "gps_spoofing"

    def test_classify_flight_anomalous(self):
        """Single strong indicator -> anomalous."""
        from app.signal.kalman import classify_flight

        kalman_results = [{"flagged": False} for _ in range(20)]
        jumps = [{"ts": None}, {"ts": None}]  # systematic jumps
        result = classify_flight(kalman_results, jumps, [], {"confidence": 0.0})
        assert result == "anomalous"

    def test_classify_flight_empty_kalman(self):
        """Empty kalman results -> normal (no evidence)."""
        from app.signal.kalman import classify_flight

        assert classify_flight([], [], [], {"confidence": 0.0}) == "normal"


# ============================================================
# Async function tests — mocked engine
# ============================================================


class TestClassifyFlightAsync:

    @pytest.mark.asyncio
    async def test_classify_flight_async(self):
        """Mock DB returning positions -> classification result with correct structure."""
        from app.signal.kalman import classify_flight_async

        base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        # Generate smooth trajectory rows as DB would return them
        cols = ["ts", "lat", "lon", "alt_baro", "alt_geom", "gs", "tas",
                "track", "true_heading", "nac_p", "nic", "baro_rate",
                "geom_rate", "on_ground"]

        db_rows = []
        for i in range(10):
            db_rows.append((
                base_ts + timedelta(seconds=i * 10),  # ts
                32.0,                                  # lat
                34.0 + i * 0.01,                       # lon
                35000,                                 # alt_baro
                35000,                                 # alt_geom
                450,                                   # gs
                440,                                   # tas
                90,                                    # track
                88,                                    # true_heading
                11,                                    # nac_p
                8,                                     # nic
                0,                                     # baro_rate
                0,                                     # geom_rate
                False,                                 # on_ground
            ))

        mock_result = MagicMock()
        mock_result.keys.return_value = cols
        mock_result.fetchall.return_value = db_rows

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.signal.kalman.engine", mock_engine):
            result = await classify_flight_async(
                "abc123",
                start_ts=base_ts,
                end_ts=base_ts + timedelta(hours=1),
            )

        assert result["hex"] == "abc123"
        assert result["n_positions"] == 10
        assert result["classification"] == "normal"
        assert "kalman_results" in result
        assert "jumps" in result
        assert "physics" in result

    @pytest.mark.asyncio
    async def test_classify_flight_async_empty(self):
        """No positions for hex -> safe classification with n_positions=0."""
        from app.signal.kalman import classify_flight_async

        base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        cols = ["ts", "lat", "lon", "alt_baro", "alt_geom", "gs", "tas",
                "track", "true_heading", "nac_p", "nic", "baro_rate",
                "geom_rate", "on_ground"]

        mock_result = MagicMock()
        mock_result.keys.return_value = cols
        mock_result.fetchall.return_value = []

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.signal.kalman.engine", mock_engine):
            result = await classify_flight_async(
                "abc123",
                start_ts=base_ts,
                end_ts=base_ts + timedelta(hours=1),
            )

        assert result["n_positions"] == 0
        assert result["classification"] == "normal"


class TestFetchPositionsAsync:

    @pytest.mark.asyncio
    async def test_fetch_positions_async(self):
        """Mock DB -> position list returned with correct keys."""
        from app.signal.kalman import fetch_positions_async

        base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        cols = ["ts", "lat", "lon", "alt_baro", "alt_geom", "gs", "tas",
                "track", "true_heading", "nac_p", "nic", "baro_rate",
                "geom_rate", "on_ground"]

        db_rows = [
            (base_ts, 32.0, 34.0, 35000, 35000, 450, 440, 90, 88, 11, 8, 0, 0, False),
        ]

        mock_result = MagicMock()
        mock_result.keys.return_value = cols
        mock_result.fetchall.return_value = db_rows

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.signal.kalman.engine", mock_engine):
            positions = await fetch_positions_async(
                "abc123",
                base_ts,
                base_ts + timedelta(hours=1),
            )

        assert len(positions) == 1
        assert positions[0]["lat"] == 32.0
        assert positions[0]["ts"] == base_ts
