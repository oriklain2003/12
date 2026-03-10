"""Kalman filter + physics cross-validation GPS anomaly detection.

Applies a constant-velocity Kalman filter to ADS-B position reports and
flags statistical outliers via chi-squared innovation testing.  Additional
physics checks (altitude divergence, speed/heading consistency, vertical
rate agreement) provide cross-validation evidence.

Async port of scripts/detect_kalman.py — DB access uses async SQLAlchemy;
pure computation functions remain synchronous.

Public API (used by SignalHealthAnalyzerCube in Plan 03):
    classify_flight_async(hex_code, start_ts=None, end_ts=None) -> dict
    fetch_positions_async(hex_code, start_ts, end_ts) -> list[dict]
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

import numpy as np
from scipy.linalg import inv
from sqlalchemy import text

from app.database import engine

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (from notebook research — DO NOT MODIFY)
# ---------------------------------------------------------------------------

R_EARTH = 6_371_000  # meters
CHI2_THRESHOLD = 13.82  # chi2.ppf(0.999, df=2), 2 DOF, P_fa=0.001
MAX_VELOCITY = 650.0  # m/s (~Mach 2)
MEASUREMENT_SIGMA = 300.0  # meters — accounts for ADS-B timestamp jitter / batching
PROCESS_NOISE_Q = 100.0  # aircraft acceleration process noise (m/s^2)^2
TIME_GAP_RESET = 300  # seconds (5 min)
POSITION_JUMP_KM = 55.56  # 30 NM
ALT_DIVERGENCE_FT = 1000
ALT_DIVERGENCE_SPOOF_FT = 2000


# ---------------------------------------------------------------------------
# 1. Coordinate conversion (pure computation, sync)
# ---------------------------------------------------------------------------

def latlon_to_enu(lat, lon, ref_lat, ref_lon):
    """Convert lat/lon to local East-North-Up (meters) relative to a reference."""
    lat_r, lon_r = np.radians(lat), np.radians(lon)
    ref_lat_r, ref_lon_r = np.radians(ref_lat), np.radians(ref_lon)
    east = R_EARTH * np.cos(ref_lat_r) * (lon_r - ref_lon_r)
    north = R_EARTH * (lat_r - ref_lat_r)
    return east, north


# ---------------------------------------------------------------------------
# 2. Database access (async)
# ---------------------------------------------------------------------------

async def fetch_positions_async(hex_code: str,
                                 start_ts: datetime,
                                 end_ts: datetime) -> list[dict]:
    """Fetch airborne ADS-B position reports for a given hex and time window."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT ts, lat, lon, alt_baro, alt_geom, gs, tas, track, true_heading,
                       nac_p, nic, baro_rate, geom_rate, on_ground
                FROM positions
                WHERE hex = :hex
                  AND source_type = 'adsb_icao'
                  AND on_ground = false
                  AND lat IS NOT NULL
                  AND ts >= :start AND ts <= :end
                ORDER BY ts
            """),
            {"hex": hex_code, "start": start_ts, "end": end_ts},
        )
        cols = list(result.keys())
        rows = []
        for row in result.fetchall():
            rows.append(dict(zip(cols, row)))
        return rows


async def fetch_time_range_async(
    hex_code: str,
    lookback_hours: float = 168,
) -> tuple[datetime, datetime] | None:
    """Fetch the min and max timestamps for a given hex within a lookback window.

    Args:
        hex_code: ICAO24 hex address.
        lookback_hours: Only consider positions from the last N hours (default 168 = 7 days).
            Prevents full table scans on the 46M-row positions table.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT min(ts), max(ts) FROM positions"
                " WHERE hex = :hex AND ts >= :cutoff"
            ),
            {"hex": hex_code, "cutoff": cutoff},
        )
        row = result.fetchone()
        if row is None or row[0] is None:
            return None
        return row[0], row[1]


# ---------------------------------------------------------------------------
# 3. Kalman filter (pure computation, sync)
# ---------------------------------------------------------------------------

def kalman_filter(positions: list[dict]) -> list[dict]:
    """Run a constant-velocity Kalman filter and flag chi2 / velocity outliers.

    State vector: [x, y, vx, vy] in ENU metres relative to first position.
    Returns a list of per-point result dicts starting from index 2.
    """
    if len(positions) < 3:
        return []

    # Use first position as reference
    ref_lat, ref_lon = positions[0]["lat"], positions[0]["lon"]

    # Convert all positions to ENU
    lats = np.array([p["lat"] for p in positions])
    lons = np.array([p["lon"] for p in positions])
    ex, ny = latlon_to_enu(lats, lons, ref_lat, ref_lon)

    # Initialize from first two positions
    dt0 = (positions[1]["ts"] - positions[0]["ts"]).total_seconds()
    if dt0 <= 0:
        dt0 = 1.0
    vx0 = (ex[1] - ex[0]) / dt0
    vy0 = (ny[1] - ny[0]) / dt0
    state = np.array([ex[1], ny[1], vx0, vy0])

    P = np.diag([100.0, 100.0, 50.0, 50.0])
    H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=float)
    R = np.diag([MEASUREMENT_SIGMA**2, MEASUREMENT_SIGMA**2])

    results: list[dict] = []
    I4 = np.eye(4)

    for i in range(2, len(positions)):
        dt = (positions[i]["ts"] - positions[i - 1]["ts"]).total_seconds()
        if dt <= 0:
            continue

        # Reset on large gaps
        if dt > TIME_GAP_RESET:
            state = np.array([ex[i], ny[i], 0.0, 0.0])
            P = np.diag([100.0, 100.0, 50.0, 50.0])
            results.append({
                "ts": positions[i]["ts"],
                "lat": positions[i]["lat"],
                "lon": positions[i]["lon"],
                "chi2": 0.0,
                "implied_velocity_ms": 0.0,
                "innovation_east_m": 0.0,
                "innovation_north_m": 0.0,
                "flagged": False,
                "reset": True,
            })
            continue

        # State transition (constant velocity)
        F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=float)

        # Process noise (continuous white noise acceleration)
        q = PROCESS_NOISE_Q
        Q = np.array([
            [dt**3 / 3, 0, dt**2 / 2, 0],
            [0, dt**3 / 3, 0, dt**2 / 2],
            [dt**2 / 2, 0, dt, 0],
            [0, dt**2 / 2, 0, dt],
        ]) * q

        # Predict
        s_pred = F @ state
        P_pred = F @ P @ F.T + Q

        # Innovation
        z = np.array([ex[i], ny[i]])
        y = z - H @ s_pred
        S = H @ P_pred @ H.T + R

        # Chi-squared test
        S_inv = inv(S)
        w = float(y.T @ S_inv @ y)

        implied_v = np.sqrt(y[0]**2 + y[1]**2) / dt
        flagged = w > CHI2_THRESHOLD or implied_v > MAX_VELOCITY

        results.append({
            "ts": positions[i]["ts"],
            "lat": positions[i]["lat"],
            "lon": positions[i]["lon"],
            "chi2": w,
            "implied_velocity_ms": implied_v,
            "innovation_east_m": float(y[0]),
            "innovation_north_m": float(y[1]),
            "flagged": flagged,
            "reset": False,
        })

        # Update
        K = P_pred @ H.T @ S_inv
        state = s_pred + K @ y
        P = (I4 - K @ H) @ P_pred

    return results


# ---------------------------------------------------------------------------
# 4. Position jump detection (pure computation, sync)
# ---------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in kilometres."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def detect_position_jumps(positions: list[dict]) -> list[dict]:
    """Flag consecutive position reports >30 NM apart in <30 s."""
    jumps: list[dict] = []
    for i in range(1, len(positions)):
        dt = (positions[i]["ts"] - positions[i - 1]["ts"]).total_seconds()
        if dt <= 0 or dt > 30:
            continue
        dist = haversine_km(
            positions[i - 1]["lat"], positions[i - 1]["lon"],
            positions[i]["lat"], positions[i]["lon"],
        )
        if dist > POSITION_JUMP_KM:
            implied_speed_kts = (dist / 1.852) / (dt / 3600)
            jumps.append({
                "ts": positions[i]["ts"],
                "lat": positions[i]["lat"],
                "lon": positions[i]["lon"],
                "prev_lat": positions[i - 1]["lat"],
                "prev_lon": positions[i - 1]["lon"],
                "dist_km": dist,
                "dt_s": dt,
                "implied_speed_kts": implied_speed_kts,
            })
    return jumps


# ---------------------------------------------------------------------------
# 5. Altitude divergence detection (pure computation, sync)
# ---------------------------------------------------------------------------

def detect_altitude_divergence(positions: list[dict]) -> list[dict]:
    """|alt_baro - alt_geom| check for each position."""
    divergences: list[dict] = []
    for p in positions:
        ab = p.get("alt_baro")
        ag = p.get("alt_geom")
        if ab is None or ag is None:
            continue
        div = abs(ab - ag)
        if div > ALT_DIVERGENCE_FT:
            divergences.append({
                "ts": p["ts"],
                "alt_baro": ab,
                "alt_geom": ag,
                "divergence_ft": div,
                "severe": div > ALT_DIVERGENCE_SPOOF_FT,
            })
    return divergences


# ---------------------------------------------------------------------------
# 6. Physics cross-validation (pure computation, sync)
# ---------------------------------------------------------------------------

def physics_cross_validation(positions: list[dict]) -> dict:
    """Multi-sensor consistency checks (baro vs GPS alt, GS vs TAS, etc.)."""
    checks: dict = {}
    scores: list[float] = []

    # 1. Baro vs GPS altitude divergence
    both_alt = [p for p in positions
                if p.get("alt_baro") is not None and p.get("alt_geom") is not None]
    if len(both_alt) >= 2:
        alt_diffs = [abs(p["alt_baro"] - p["alt_geom"]) for p in both_alt]
        mean_diff = sum(alt_diffs) / len(alt_diffs)
        checks["alt_divergence_ft"] = mean_diff
        if mean_diff > 1000:
            scores.append(1.0)
        elif mean_diff > 500:
            scores.append(0.6)
        else:
            scores.append(0.1)

    # 2. Ground speed vs true airspeed
    both_spd = [p for p in positions
                if p.get("gs") is not None and p.get("tas") is not None]
    if len(both_spd) >= 2:
        spd_diffs = [abs(p["gs"] - p["tas"]) for p in both_spd]
        mean_spd_diff = sum(spd_diffs) / len(spd_diffs)
        checks["gs_tas_diff_kt"] = mean_spd_diff
        if mean_spd_diff > 150:
            scores.append(1.0)
        elif mean_spd_diff > 100:
            scores.append(0.5)
        else:
            scores.append(0.1)

    # 3. Track vs heading divergence
    both_hdg = [p for p in positions
                if p.get("track") is not None and p.get("true_heading") is not None]
    if len(both_hdg) >= 2:
        hdg_diffs = [
            min(abs(p["track"] - p["true_heading"]),
                360 - abs(p["track"] - p["true_heading"]))
            for p in both_hdg
        ]
        mean_hdg_diff = sum(hdg_diffs) / len(hdg_diffs)
        checks["track_heading_diff_deg"] = mean_hdg_diff
        if mean_hdg_diff > 45:
            scores.append(1.0)
        elif mean_hdg_diff > 20:
            scores.append(0.5)
        else:
            scores.append(0.1)

    # 4. Vertical rate consistency
    both_vr = [p for p in positions
               if p.get("baro_rate") is not None and p.get("geom_rate") is not None]
    if len(both_vr) >= 2:
        vr_diffs = [abs(p["baro_rate"] - p["geom_rate"]) for p in both_vr]
        mean_vr_diff = sum(vr_diffs) / len(vr_diffs)
        checks["vrate_diff_fpm"] = mean_vr_diff
        if mean_vr_diff > 1000:
            scores.append(1.0)
        elif mean_vr_diff > 500:
            scores.append(0.5)
        else:
            scores.append(0.1)

    confidence = sum(scores) / len(scores) if scores else 0.0
    checks["confidence"] = round(confidence, 3)
    checks["n_checks_passed"] = sum(1 for s in scores if s >= 0.5)
    checks["n_checks_total"] = len(scores)
    return checks


# ---------------------------------------------------------------------------
# 7. Classification (pure computation, sync)
# ---------------------------------------------------------------------------

def classify_flight(kalman_results: list[dict],
                    jumps: list[dict],
                    alt_divergence: list[dict],
                    physics: dict) -> str:
    """Aggregate evidence into a single flight classification.

    Returns one of: 'gps_spoofing', 'anomalous', 'normal'.

    Key differentiators:
    - Spoofing: sustained chi2 exceedances + position jumps + alt divergence
    - Jamming: NACp=0 but positions are honest (no chi2 flags), often no data
    - Normal: smooth trajectories, occasional isolated outliers from ADS-B jitter
    - Transponder off: gaps cause filter resets but no anomalies between resets
    """
    n_kalman = len(kalman_results)
    n_flagged = sum(1 for r in kalman_results if r["flagged"])
    flag_pct = (n_flagged / n_kalman * 100) if n_kalman > 0 else 0.0

    # Multiple jumps are a strong signal; a single jump may be ADS-B noise
    n_jumps = len(jumps)
    has_systematic_jumps = n_jumps >= 2

    # Altitude divergence: severe events (>2000ft) are strong spoofing indicators.
    # Many moderate events (>1000ft) also count if sustained.
    n_alt_div = len(alt_divergence)
    n_severe_alt_div = sum(1 for a in alt_divergence if a["severe"])
    has_significant_alt_div = n_severe_alt_div >= 1 or n_alt_div >= 10

    physics_confidence = physics.get("confidence", 0.0)

    # GPS spoofing: require multiple corroborating signals.
    # Chi2 exceedances alone can come from ADS-B jitter — they must be
    # accompanied by physical evidence (alt divergence, jumps, or physics).
    spoofing_signals = 0
    if flag_pct > 5:
        spoofing_signals += 1
    if has_systematic_jumps:
        spoofing_signals += 1
    if has_significant_alt_div:
        spoofing_signals += 1
        # Multiple severe altitude divergence events are very strong evidence
        # of GPS spoofing — counts double when there are many.
        if n_severe_alt_div >= 3:
            spoofing_signals += 1
    if physics_confidence >= 0.5:
        spoofing_signals += 1

    if spoofing_signals >= 2:
        return "gps_spoofing"

    # Anomalous: at least one strong indicator present.
    # Chi2 flags alone at moderate levels are normal ADS-B noise, so require
    # a higher threshold or corroborating evidence.
    if (has_systematic_jumps
            or has_significant_alt_div
            or physics_confidence >= 0.5
            or flag_pct > 15):
        return "anomalous"

    # Normal: isolated chi2 flags from ADS-B jitter, single jump glitches,
    # minor constant-offset alt differences
    return "normal"


# ---------------------------------------------------------------------------
# 8. Async orchestration
# ---------------------------------------------------------------------------

def _serialize_datetimes(obj):
    """Recursively convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize_datetimes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_datetimes(item) for item in obj]
    return obj


async def classify_flight_async(
    hex_code: str,
    start_ts: datetime | None = None,
    end_ts: datetime | None = None,
) -> dict:
    """Run all detection steps for a single flight and return results.

    Main entry point for SignalHealthAnalyzerCube.

    Args:
        hex_code: ICAO24 hex address (e.g. '717ce7')
        start_ts: Start of analysis window (timezone-aware). If None, auto-detect.
        end_ts: End of analysis window (timezone-aware). If None, auto-detect.

    Returns:
        dict with keys:
            hex, start (ISO str), end (ISO str), n_positions,
            classification ('normal'|'anomalous'|'gps_spoofing'),
            kalman_results, jumps, alt_divergence, physics, summary
    """
    # Auto-detect time range if not supplied
    if start_ts is None or end_ts is None:
        time_range = await fetch_time_range_async(hex_code)
        if time_range is None:
            return {"error": f"No positions found for hex={hex_code}"}
        detected_start, detected_end = time_range
        if start_ts is None:
            start_ts = detected_start
        if end_ts is None:
            end_ts = detected_end

    positions = await fetch_positions_async(hex_code, start_ts, end_ts)
    if not positions:
        return {
            "hex": hex_code,
            "start": start_ts.isoformat() if isinstance(start_ts, datetime) else start_ts,
            "end": end_ts.isoformat() if isinstance(end_ts, datetime) else end_ts,
            "n_positions": 0,
            "classification": "normal",
            "kalman_results": [],
            "jumps": [],
            "alt_divergence": [],
            "physics": {},
            "summary": "No qualifying positions found.",
        }

    kalman_results = kalman_filter(positions)
    jumps = detect_position_jumps(positions)
    alt_div = detect_altitude_divergence(positions)
    physics = physics_cross_validation(positions)
    classification = classify_flight(kalman_results, jumps, alt_div, physics)

    n_flagged = sum(1 for r in kalman_results if r["flagged"])
    n_kalman = len(kalman_results)
    flag_pct = (n_flagged / n_kalman * 100) if n_kalman else 0.0

    summary = (
        f"Positions: {len(positions)}, "
        f"Kalman flagged: {n_flagged} ({flag_pct:.1f}%), "
        f"Jumps: {len(jumps)}, "
        f"Alt divergence: {len(alt_div)}"
    )

    result = {
        "hex": hex_code,
        "start": start_ts,
        "end": end_ts,
        "n_positions": len(positions),
        "classification": classification,
        "kalman_results": kalman_results,
        "jumps": jumps,
        "alt_divergence": alt_div,
        "physics": physics,
        "summary": summary,
    }

    # Convert all datetime objects to ISO strings for JSON serializability
    return _serialize_datetimes(result)
