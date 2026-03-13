"""Rule-based GPS anomaly detection — async module for SignalHealthAnalyzerCube.

Ported from scripts/detect_rule_based.py (sync psycopg CLI tool) to
async SQLAlchemy for use in the backend workflow engine.

Public API (used by Plan 03):
  get_coverage_baseline() -> dict                       (startup-loaded, no TTL)
  start_coverage_baseline_build() -> None               (called from lifespan hook)
  detect_integrity_events_batch_async(hex_list, start_ts, end_ts) -> dict[str, list[dict]]
  detect_shutdowns_batch_async(hex_list, start_ts, end_ts) -> dict[str, list[dict]]
  detect_integrity_events_async(hex_code, start_ts, end_ts) -> list[dict]
  detect_transponder_shutdowns_async(hex_code, start_ts, end_ts) -> list[dict]
  score_event(event, coverage_baseline) -> dict
  classify_event(scored_event) -> str
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from app.database import engine

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds (from notebook research / detect_anomalies.py)
# ---------------------------------------------------------------------------

RSSI_COVERAGE_THRESHOLD = -20.0   # dBFS; below = likely coverage issue
COVERAGE_GRID_SIZE = 0.5          # degrees (~55 km at mid-latitudes)
GAP_MINUTES_SHUTDOWN = 5          # minutes silence = potential transponder off
MIN_REPORTS_PER_HOUR = 6          # below = coverage hole
ALT_DIVERGENCE_FT = 1000          # |alt_baro - alt_geom| anomaly threshold
ALT_DIVERGENCE_SPOOF_FT = 2000    # strong spoofing signal
POSITION_JUMP_NM = 30             # >30 NM between consecutive reports
POSITION_JUMP_KM = 55.56          # 30 NM in km

# ---------------------------------------------------------------------------
# Coverage Baseline — startup-loaded, no TTL
# ---------------------------------------------------------------------------

_baseline_cache: dict[tuple[float, float], dict[str, Any]] | None = None


async def get_coverage_baseline() -> dict[tuple[float, float], dict[str, Any]]:
    """Return the coverage baseline loaded at startup.

    Returns an empty dict if start_coverage_baseline_build() has not completed yet.
    No TTL — loaded once at startup, never invalidated.
    """
    return _baseline_cache if _baseline_cache is not None else {}


async def start_coverage_baseline_build() -> None:
    """Build the coverage baseline and cache it in memory.

    Called from the lifespan hook in main.py via asyncio.create_task().
    Uses a 48-hour lookback window (2 days).
    """
    global _baseline_cache
    log.info("Building coverage baseline...")
    t0 = time.monotonic()
    try:
        _baseline_cache = await build_coverage_baseline_async(lookback_days=2)
        elapsed = time.monotonic() - t0
        log.info("Coverage baseline ready: %d cells in %.1fs", len(_baseline_cache), elapsed)
    except Exception as exc:
        log.warning("Coverage baseline build failed: %s", exc)


# ---------------------------------------------------------------------------
# Coverage Baseline Builder
# ---------------------------------------------------------------------------

async def build_coverage_baseline_async(
    lookback_days: int = 2,
) -> dict[tuple[float, float], dict[str, Any]]:
    """Build a 0.5-degree grid with median RSSI, reports/hour, temporal
    coverage from the positions table over the last *lookback_days*.

    Returns dict of (lat_cell, lon_cell) -> {median_rssi, reports_per_hour,
    temporal_coverage, is_coverage_hole}.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    grid = COVERAGE_GRID_SIZE

    t0 = time.monotonic()

    async with engine.connect() as conn:
        result = await conn.execute(text(f"""
            WITH raw AS (
                SELECT
                    floor(lat / {grid}) * {grid}  AS lat_cell,
                    floor(lon / {grid}) * {grid}  AS lon_cell,
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY rssi) AS median_rssi,
                    count(*)                                AS total_reports,
                    count(DISTINCT hex)                     AS unique_aircraft,
                    count(*) FILTER (WHERE nac_p = 0)       AS nacp_zero_count,
                    min(ts)                                 AS first_seen,
                    max(ts)                                 AS last_seen,
                    count(DISTINCT floor(extract(epoch FROM ts) / 600)) AS bins_with_data,
                    floor(
                        (extract(epoch FROM max(ts)) - extract(epoch FROM min(ts))) / 600
                    ) + 1 AS total_bins
                FROM positions
                WHERE source_type = 'adsb_icao'
                  AND on_ground = false
                  AND lat IS NOT NULL
                  AND rssi IS NOT NULL
                  AND ts >= :start AND ts <= :end
                GROUP BY 1, 2
                HAVING count(*) >= 10
            )
            SELECT lat_cell, lon_cell, median_rssi, total_reports,
                   total_reports / GREATEST(
                       extract(epoch FROM last_seen - first_seen) / 3600.0, 1
                   ) AS reports_per_hour,
                   LEAST(bins_with_data::float / GREATEST(total_bins, 1), 1.0) AS temporal_coverage
            FROM raw
        """), {"start": start, "end": end})
        rows = result.fetchall()

    baseline: dict[tuple[float, float], dict[str, Any]] = {}
    holes = 0
    for row in rows:
        lat_cell, lon_cell, median_rssi, total_reports, reports_per_hour, temporal_coverage = row

        median_rssi = float(median_rssi) if median_rssi is not None else None
        reports_per_hour = float(reports_per_hour) if reports_per_hour is not None else None
        temporal_coverage = float(temporal_coverage) if temporal_coverage is not None else None

        is_coverage_hole = (
            (median_rssi is not None and median_rssi < RSSI_COVERAGE_THRESHOLD)
            or (reports_per_hour is not None and reports_per_hour < MIN_REPORTS_PER_HOUR)
            or (temporal_coverage is not None and temporal_coverage < 0.3)
        )

        if is_coverage_hole:
            holes += 1

        baseline[(lat_cell, lon_cell)] = {
            "median_rssi": median_rssi,
            "reports_per_hour": reports_per_hour,
            "temporal_coverage": temporal_coverage,
            "is_coverage_hole": is_coverage_hole,
        }

    elapsed = time.monotonic() - t0
    log.info("Coverage baseline: %d cells (%d holes) in %.1fs", len(baseline), holes, elapsed)
    return baseline


# ---------------------------------------------------------------------------
# Detection: Batch Transponder Shutdowns
# ---------------------------------------------------------------------------

async def detect_shutdowns_batch_async(
    hex_list: list[str],
    start_ts: datetime,
    end_ts: datetime,
) -> dict[str, list[dict]]:
    """Find mid-flight transponder shutdown gaps for a batch of hex codes.

    Runs a single query with ANY(:hex_list) instead of per-hex queries.
    Returns dict keyed by hex -> list of shutdown event dicts.
    """
    min_gap_s = GAP_MINUTES_SHUTDOWN * 60

    async with engine.connect() as conn:
        result = await conn.execute(text("""
            WITH gaps AS (
                SELECT
                    hex, ts, lat, lon, alt_baro, on_ground, nac_p, messages, rssi, region,
                    LAG(ts)        OVER w AS prev_ts,
                    LAG(lat)       OVER w AS prev_lat,
                    LAG(lon)       OVER w AS prev_lon,
                    LAG(alt_baro)  OVER w AS prev_alt,
                    LAG(on_ground) OVER w AS prev_on_ground,
                    LAG(nac_p)     OVER w AS prev_nac_p,
                    LAG(rssi)      OVER w AS prev_rssi
                FROM positions
                WHERE source_type = 'adsb_icao'
                  AND lat IS NOT NULL
                  AND hex = ANY(:hex_list)
                  AND ts >= :start AND ts <= :end
                WINDOW w AS (PARTITION BY hex ORDER BY ts)
            )
            SELECT
                hex,
                prev_ts           AS last_seen_ts,
                ts                AS reappear_ts,
                extract(epoch FROM ts - prev_ts) AS gap_duration_s,
                prev_lat          AS last_lat,
                prev_lon          AS last_lon,
                prev_alt          AS last_alt_baro,
                lat               AS reappear_lat,
                lon               AS reappear_lon,
                prev_nac_p        AS last_nac_p,
                prev_rssi         AS last_rssi,
                region
            FROM gaps
            WHERE prev_ts IS NOT NULL
              AND extract(epoch FROM ts - prev_ts) > :min_gap_s
              AND prev_on_ground = false
              AND (prev_alt IS NULL OR prev_alt > 2000)
              AND (prev_nac_p IS NULL OR prev_nac_p >= 8)
              AND (prev_rssi IS NULL OR prev_rssi > :rssi_thresh)
            ORDER BY hex, gap_duration_s DESC
        """), {
            "hex_list": hex_list,
            "start": start_ts,
            "end": end_ts,
            "min_gap_s": min_gap_s,
            "rssi_thresh": RSSI_COVERAGE_THRESHOLD,
        })
        rows = result.fetchall()

    by_hex: dict[str, list[dict]] = {}
    for row in rows:
        (hex_code, last_seen_ts, reappear_ts, gap_duration_s,
         last_lat, last_lon, last_alt_baro,
         reappear_lat, reappear_lon,
         last_nac_p, last_rssi, region) = row

        last_seen_str = last_seen_ts.isoformat() if isinstance(last_seen_ts, datetime) else last_seen_ts
        reappear_str = reappear_ts.isoformat() if isinstance(reappear_ts, datetime) else reappear_ts

        event = {
            "hex": hex_code,
            "category": "transponder_off",
            "source": "gap_detection",
            "start_ts": last_seen_str,
            "end_ts": reappear_str,
            "duration_s": float(gap_duration_s) if gap_duration_s is not None else 0,
            "entry_lat": last_lat,
            "entry_lon": last_lon,
            "exit_lat": reappear_lat,
            "exit_lon": reappear_lon,
            "region": region,
            "version": None,
            "n_reports": 0,
            "jamming_score": 0,
            "spoofing_score": 0,
            "coverage_score": 0,
            "nacp_zero": False,
            "nic_zero": False,
            "nic_low_7": False,
            "gva_zero": False,
            "nacv_high": False,
            "has_gps_ok_before": False,
            "median_rssi": last_rssi,
            "mean_seen_pos": None,
            "msg_rate": None,
            "mean_alt_divergence_ft": None,
            "max_alt_divergence_ft": None,
            "in_coverage_hole": False,
            "last_alt_baro": last_alt_baro,
            "last_nac_p": last_nac_p,
        }
        by_hex.setdefault(hex_code, []).append(event)

    return by_hex


# ---------------------------------------------------------------------------
# Detection: Batch Integrity Events
# ---------------------------------------------------------------------------

async def detect_integrity_events_batch_async(
    hex_list: list[str],
    start_ts: datetime,
    end_ts: datetime,
) -> dict[str, list[dict]]:
    """Version-aware integrity degradation detection for a batch of hex codes.

    Runs a single query with ANY(:hex_list) instead of per-hex queries.
    Returns dict keyed by hex -> list of integrity event dicts.
    """
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            WITH degraded AS (
                SELECT ts, hex, lat, lon, nac_p, nic, version, sil, gva, nac_v,
                       alt_baro, alt_geom, gs, region,
                       rssi, seen_pos, messages,
                       gps_ok_before, gps_ok_lat, gps_ok_lon,
                       CASE WHEN LAG(ts) OVER (PARTITION BY hex ORDER BY ts) IS NULL THEN 1
                            WHEN EXTRACT(EPOCH FROM ts - LAG(ts) OVER (PARTITION BY hex ORDER BY ts)) > 30 THEN 1
                            ELSE 0 END AS event_start
                FROM positions
                WHERE source_type = 'adsb_icao'
                  AND on_ground = false
                  AND lat IS NOT NULL
                  AND hex = ANY(:hex_list)
                  AND ts >= :start AND ts <= :end
                  AND (
                      (version = 2 AND (nac_p = 0 OR nic < 7))
                      OR (version = 1 AND nac_p = 0 AND (nic = 0 OR gps_ok_before IS NOT NULL))
                      OR ((version = 0 OR version IS NULL) AND gps_ok_before IS NOT NULL)
                  )
            ),
            events AS (
                SELECT *, SUM(event_start) OVER (PARTITION BY hex ORDER BY ts) AS event_id
                FROM degraded
            )
            SELECT
                hex, event_id,
                min(ts) AS start_ts,
                max(ts) AS end_ts,
                EXTRACT(EPOCH FROM max(ts) - min(ts)) AS duration_s,
                count(*) AS n_reports,
                (array_agg(lat ORDER BY ts))[1] AS entry_lat,
                (array_agg(lon ORDER BY ts))[1] AS entry_lon,
                (array_agg(lat ORDER BY ts DESC))[1] AS exit_lat,
                (array_agg(lon ORDER BY ts DESC))[1] AS exit_lon,
                mode() WITHIN GROUP (ORDER BY version) AS version,
                bool_or(nac_p = 0) AS nacp_zero,
                bool_and(nic = 0) AS nic_zero,
                bool_or(nic < 7) AS nic_low_7,
                bool_or(gva = 0) AS gva_zero,
                bool_or(nac_v > 0) AS nacv_high,
                mode() WITHIN GROUP (ORDER BY region) AS region,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY rssi) AS median_rssi,
                bool_or(gps_ok_before IS NOT NULL) AS has_gps_ok_before,
                avg(seen_pos) AS mean_seen_pos,
                CASE WHEN count(*) FILTER (WHERE messages IS NOT NULL) >= 2
                     THEN (max(messages) - min(messages))::float
                          / GREATEST(EXTRACT(EPOCH FROM max(ts) - min(ts)), 1)
                     ELSE NULL END AS msg_rate,
                avg(abs(alt_baro - alt_geom)) FILTER (WHERE alt_baro IS NOT NULL AND alt_geom IS NOT NULL) AS mean_alt_divergence_ft,
                max(abs(alt_baro - alt_geom)) FILTER (WHERE alt_baro IS NOT NULL AND alt_geom IS NOT NULL) AS max_alt_divergence_ft,
                avg(gps_ok_lat) AS gps_ok_lat_mean,
                avg(gps_ok_lon) AS gps_ok_lon_mean
            FROM events
            GROUP BY hex, event_id
            HAVING max(ts) - min(ts) >= INTERVAL '30 seconds'
            ORDER BY hex, min(ts)
        """), {"hex_list": hex_list, "start": start_ts, "end": end_ts})
        rows = result.fetchall()

    by_hex: dict[str, list[dict]] = {}
    for row in rows:
        (hex_val, _event_id, ev_start_ts, ev_end_ts, duration_s, n_reports,
         entry_lat, entry_lon, exit_lat, exit_lon, version,
         nacp_zero, nic_zero, nic_low_7, gva_zero, nacv_high,
         region, median_rssi, has_gps_ok_before, mean_seen_pos, msg_rate,
         mean_alt_div, max_alt_div, gps_ok_lat, gps_ok_lon) = row

        # Cast Decimal types to float
        median_rssi = float(median_rssi) if median_rssi is not None else None
        mean_seen_pos = float(mean_seen_pos) if mean_seen_pos is not None else None
        msg_rate = float(msg_rate) if msg_rate is not None else None
        mean_alt_div = float(mean_alt_div) if mean_alt_div is not None else None
        max_alt_div = float(max_alt_div) if max_alt_div is not None else None
        duration_s = float(duration_s) if duration_s is not None else 0.0

        # Serialize datetime objects to ISO 8601 strings
        start_str = ev_start_ts.isoformat() if isinstance(ev_start_ts, datetime) else ev_start_ts
        end_str = ev_end_ts.isoformat() if isinstance(ev_end_ts, datetime) else ev_end_ts

        event = {
            "hex": hex_val,
            "source": "integrity_drop",
            "start_ts": start_str,
            "end_ts": end_str,
            "duration_s": duration_s,
            "n_reports": n_reports,
            "entry_lat": entry_lat,
            "entry_lon": entry_lon,
            "exit_lat": exit_lat,
            "exit_lon": exit_lon,
            "version": version,
            "nacp_zero": nacp_zero,
            "nic_zero": nic_zero,
            "nic_low_7": nic_low_7,
            "gva_zero": gva_zero,
            "nacv_high": nacv_high,
            "region": region,
            "median_rssi": median_rssi,
            "has_gps_ok_before": has_gps_ok_before,
            "mean_seen_pos": mean_seen_pos,
            "msg_rate": msg_rate,
            "mean_alt_divergence_ft": mean_alt_div,
            "max_alt_divergence_ft": max_alt_div,
            "gps_ok_lat": gps_ok_lat,
            "gps_ok_lon": gps_ok_lon,
        }
        by_hex.setdefault(hex_val, []).append(event)

    return by_hex


# ---------------------------------------------------------------------------
# Detection: Transponder Shutdowns (Legacy per-hex — kept for script compatibility)
# ---------------------------------------------------------------------------

async def detect_transponder_shutdowns_async(
    hex_code: str,
    start_ts: datetime,
    end_ts: datetime,
) -> list[dict[str, Any]]:
    """Find mid-flight gaps >5 min where the transponder likely shut down.

    Uses SQL window function LAG to find gaps while airborne with good NACp
    before the gap.
    """
    min_gap_s = GAP_MINUTES_SHUTDOWN * 60

    async with engine.connect() as conn:
        result = await conn.execute(text("""
            WITH gaps AS (
                SELECT
                    hex, ts, lat, lon, alt_baro, on_ground, nac_p, messages, rssi, region,
                    LAG(ts)        OVER w AS prev_ts,
                    LAG(lat)       OVER w AS prev_lat,
                    LAG(lon)       OVER w AS prev_lon,
                    LAG(alt_baro)  OVER w AS prev_alt,
                    LAG(on_ground) OVER w AS prev_on_ground,
                    LAG(nac_p)     OVER w AS prev_nac_p,
                    LAG(rssi)      OVER w AS prev_rssi
                FROM positions
                WHERE source_type = 'adsb_icao'
                  AND lat IS NOT NULL
                  AND hex = :hex
                  AND ts >= :start AND ts <= :end
                WINDOW w AS (PARTITION BY hex ORDER BY ts)
            )
            SELECT
                prev_ts           AS last_seen_ts,
                ts                AS reappear_ts,
                extract(epoch FROM ts - prev_ts) AS gap_duration_s,
                prev_lat          AS last_lat,
                prev_lon          AS last_lon,
                prev_alt          AS last_alt_baro,
                lat               AS reappear_lat,
                lon               AS reappear_lon,
                prev_nac_p        AS last_nac_p,
                prev_rssi         AS last_rssi,
                region
            FROM gaps
            WHERE prev_ts IS NOT NULL
              AND extract(epoch FROM ts - prev_ts) > :min_gap_s
              AND prev_on_ground = false
              AND (prev_alt IS NULL OR prev_alt > 2000)
              AND (prev_nac_p IS NULL OR prev_nac_p >= 8)
              AND (prev_rssi IS NULL OR prev_rssi > :rssi_thresh)
            ORDER BY gap_duration_s DESC
        """), {
            "hex": hex_code,
            "start": start_ts,
            "end": end_ts,
            "min_gap_s": min_gap_s,
            "rssi_thresh": RSSI_COVERAGE_THRESHOLD,
        })
        rows = result.fetchall()

    events: list[dict[str, Any]] = []
    for row in rows:
        (last_seen_ts, reappear_ts, gap_duration_s,
         last_lat, last_lon, last_alt_baro,
         reappear_lat, reappear_lon,
         last_nac_p, last_rssi, region) = row

        # Serialize datetime objects to ISO 8601 strings
        last_seen_str = last_seen_ts.isoformat() if isinstance(last_seen_ts, datetime) else last_seen_ts
        reappear_str = reappear_ts.isoformat() if isinstance(reappear_ts, datetime) else reappear_ts

        events.append({
            "hex": hex_code,
            "category": "transponder_off",
            "source": "gap_detection",
            "start_ts": last_seen_str,
            "end_ts": reappear_str,
            "duration_s": float(gap_duration_s) if gap_duration_s is not None else 0,
            "entry_lat": last_lat,
            "entry_lon": last_lon,
            "exit_lat": reappear_lat,
            "exit_lon": reappear_lon,
            "region": region,
            "version": None,
            "n_reports": 0,
            "jamming_score": 0,
            "spoofing_score": 0,
            "coverage_score": 0,
            "nacp_zero": False,
            "nic_zero": False,
            "nic_low_7": False,
            "gva_zero": False,
            "nacv_high": False,
            "has_gps_ok_before": False,
            "median_rssi": last_rssi,
            "mean_seen_pos": None,
            "msg_rate": None,
            "mean_alt_divergence_ft": None,
            "max_alt_divergence_ft": None,
            "in_coverage_hole": False,
            "last_alt_baro": last_alt_baro,
            "last_nac_p": last_nac_p,
        })

    return events


# ---------------------------------------------------------------------------
# Detection: Integrity Events — Version-Aware NACp/NIC (Legacy per-hex — kept for script compatibility)
# ---------------------------------------------------------------------------

async def detect_integrity_events_async(
    hex_code: str,
    start_ts: datetime,
    end_ts: datetime,
) -> list[dict[str, Any]]:
    """Version-aware integrity degradation detection with event segmentation.

    Uses a 30-second gap threshold to segment contiguous degradation into
    discrete events. Returns per-event aggregations.
    """
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            WITH degraded AS (
                SELECT ts, hex, lat, lon, nac_p, nic, version, sil, gva, nac_v,
                       alt_baro, alt_geom, gs, region,
                       rssi, seen_pos, messages,
                       gps_ok_before, gps_ok_lat, gps_ok_lon,
                       CASE WHEN LAG(ts) OVER (PARTITION BY hex ORDER BY ts) IS NULL THEN 1
                            WHEN EXTRACT(EPOCH FROM ts - LAG(ts) OVER (PARTITION BY hex ORDER BY ts)) > 30 THEN 1
                            ELSE 0 END AS event_start
                FROM positions
                WHERE source_type = 'adsb_icao'
                  AND on_ground = false
                  AND lat IS NOT NULL
                  AND hex = :hex
                  AND ts >= :start AND ts <= :end
                  AND (
                      (version = 2 AND (nac_p = 0 OR nic < 7))
                      OR (version = 1 AND nac_p = 0 AND (nic = 0 OR gps_ok_before IS NOT NULL))
                      OR ((version = 0 OR version IS NULL) AND gps_ok_before IS NOT NULL)
                  )
            ),
            events AS (
                SELECT *, SUM(event_start) OVER (PARTITION BY hex ORDER BY ts) AS event_id
                FROM degraded
            )
            SELECT
                hex, event_id,
                min(ts) AS start_ts,
                max(ts) AS end_ts,
                EXTRACT(EPOCH FROM max(ts) - min(ts)) AS duration_s,
                count(*) AS n_reports,
                (array_agg(lat ORDER BY ts))[1] AS entry_lat,
                (array_agg(lon ORDER BY ts))[1] AS entry_lon,
                (array_agg(lat ORDER BY ts DESC))[1] AS exit_lat,
                (array_agg(lon ORDER BY ts DESC))[1] AS exit_lon,
                mode() WITHIN GROUP (ORDER BY version) AS version,
                bool_or(nac_p = 0) AS nacp_zero,
                bool_and(nic = 0) AS nic_zero,
                bool_or(nic < 7) AS nic_low_7,
                bool_or(gva = 0) AS gva_zero,
                bool_or(nac_v > 0) AS nacv_high,
                mode() WITHIN GROUP (ORDER BY region) AS region,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY rssi) AS median_rssi,
                bool_or(gps_ok_before IS NOT NULL) AS has_gps_ok_before,
                avg(seen_pos) AS mean_seen_pos,
                CASE WHEN count(*) FILTER (WHERE messages IS NOT NULL) >= 2
                     THEN (max(messages) - min(messages))::float
                          / GREATEST(EXTRACT(EPOCH FROM max(ts) - min(ts)), 1)
                     ELSE NULL END AS msg_rate,
                avg(abs(alt_baro - alt_geom)) FILTER (WHERE alt_baro IS NOT NULL AND alt_geom IS NOT NULL) AS mean_alt_divergence_ft,
                max(abs(alt_baro - alt_geom)) FILTER (WHERE alt_baro IS NOT NULL AND alt_geom IS NOT NULL) AS max_alt_divergence_ft,
                avg(gps_ok_lat) AS gps_ok_lat_mean,
                avg(gps_ok_lon) AS gps_ok_lon_mean
            FROM events
            GROUP BY hex, event_id
            HAVING max(ts) - min(ts) >= INTERVAL '30 seconds'
            ORDER BY min(ts)
        """), {"hex": hex_code, "start": start_ts, "end": end_ts})
        rows = result.fetchall()

    events: list[dict[str, Any]] = []
    for row in rows:
        (hex_val, _event_id, ev_start_ts, ev_end_ts, duration_s, n_reports,
         entry_lat, entry_lon, exit_lat, exit_lon, version,
         nacp_zero, nic_zero, nic_low_7, gva_zero, nacv_high,
         region, median_rssi, has_gps_ok_before, mean_seen_pos, msg_rate,
         mean_alt_div, max_alt_div, gps_ok_lat, gps_ok_lon) = row

        # Cast Decimal types to float
        median_rssi = float(median_rssi) if median_rssi is not None else None
        mean_seen_pos = float(mean_seen_pos) if mean_seen_pos is not None else None
        msg_rate = float(msg_rate) if msg_rate is not None else None
        mean_alt_div = float(mean_alt_div) if mean_alt_div is not None else None
        max_alt_div = float(max_alt_div) if max_alt_div is not None else None
        duration_s = float(duration_s) if duration_s is not None else 0.0

        # Serialize datetime objects to ISO 8601 strings
        start_str = ev_start_ts.isoformat() if isinstance(ev_start_ts, datetime) else ev_start_ts
        end_str = ev_end_ts.isoformat() if isinstance(ev_end_ts, datetime) else ev_end_ts

        events.append({
            "hex": hex_val,
            "source": "integrity_drop",
            "start_ts": start_str,
            "end_ts": end_str,
            "duration_s": duration_s,
            "n_reports": n_reports,
            "entry_lat": entry_lat,
            "entry_lon": entry_lon,
            "exit_lat": exit_lat,
            "exit_lon": exit_lon,
            "version": version,
            "nacp_zero": nacp_zero,
            "nic_zero": nic_zero,
            "nic_low_7": nic_low_7,
            "gva_zero": gva_zero,
            "nacv_high": nacv_high,
            "region": region,
            "median_rssi": median_rssi,
            "has_gps_ok_before": has_gps_ok_before,
            "mean_seen_pos": mean_seen_pos,
            "msg_rate": msg_rate,
            "mean_alt_divergence_ft": mean_alt_div,
            "max_alt_divergence_ft": max_alt_div,
            "gps_ok_lat": gps_ok_lat,
            "gps_ok_lon": gps_ok_lon,
        })

    return events


# ---------------------------------------------------------------------------
# Scoring & Classification (16-point system from detect_anomalies.py)
# ---------------------------------------------------------------------------

def score_event(
    event: dict[str, Any],
    coverage_baseline: dict[tuple[float, float], dict[str, Any]],
) -> dict[str, Any]:
    """Score an integrity event on the 16-point evidence scale.

    Returns a copy of the event dict augmented with:
      jamming_score, coverage_score, spoofing_score, in_coverage_hole, evidence.
    """
    # Version weight maps
    nacp_v_weight = {2: 3, 1: 2}
    nic_v_weight = {2: 2, 1: 1}

    jam = 0
    spf = 0
    cov = 0

    version = event.get("version")
    v = version if version is not None else -1

    nacp_zero = event.get("nacp_zero", False)
    nic_zero = event.get("nic_zero", False)
    nic_low_7 = event.get("nic_low_7", False)
    gva_zero = event.get("gva_zero", False)
    nacv_high = event.get("nacv_high", False)
    has_gps_ok_before = event.get("has_gps_ok_before", False)
    median_rssi = event.get("median_rssi")
    mean_seen_pos = event.get("mean_seen_pos")
    msg_rate = event.get("msg_rate")
    mean_alt_div = event.get("mean_alt_divergence_ft")

    # Coverage hole check
    entry_lat = event.get("entry_lat")
    entry_lon = event.get("entry_lon")
    in_hole = False
    if entry_lat is not None and entry_lon is not None:
        lat_cell = math.floor(entry_lat / COVERAGE_GRID_SIZE) * COVERAGE_GRID_SIZE
        lon_cell = math.floor(entry_lon / COVERAGE_GRID_SIZE) * COVERAGE_GRID_SIZE
        cell_info = coverage_baseline.get((lat_cell, lon_cell))
        if cell_info is not None:
            in_hole = cell_info.get("is_coverage_hole", False)
        # If cell not in baseline at all, we only flag cells we know about

    # Jamming signals
    if has_gps_ok_before:
        jam += 3
    if nacp_zero:
        jam += nacp_v_weight.get(v, 0)
    if nic_zero:
        jam += nic_v_weight.get(v, 0)
    if v == 2 and gva_zero:
        jam += 1
    if v in (1, 2) and nacv_high:
        jam += 1
    if median_rssi is not None:
        if median_rssi > RSSI_COVERAGE_THRESHOLD:
            jam += 1
        else:
            cov += 2
    if in_hole:
        cov += 1
    if msg_rate is not None and msg_rate > 0:
        jam += 1
    if mean_seen_pos is not None:
        if mean_seen_pos < 5:
            jam += 1
        elif mean_seen_pos > 15:
            cov += 1

    # Spoofing signals
    alt_div = mean_alt_div if mean_alt_div is not None else 0
    if alt_div > ALT_DIVERGENCE_FT:
        spf += 2
    if alt_div > ALT_DIVERGENCE_SPOOF_FT:
        spf += 1
    if nic_low_7 and not nacp_zero:
        spf += 2

    # Build evidence string
    evidence_parts = []
    if has_gps_ok_before:
        evidence_parts.append("gps_ok_before")
    v_label = f"V{v}" if v is not None and v != -1 else "V?"
    if nacp_zero:
        evidence_parts.append(f"NACp=0({v_label})")
    if nic_zero:
        evidence_parts.append(f"NIC=0({v_label})")
    if nic_low_7 and not nacp_zero:
        evidence_parts.append(f"NIC<7({v_label})")
    if v == 2 and gva_zero:
        evidence_parts.append("GVA=0")
    if v in (1, 2) and nacv_high:
        evidence_parts.append("NACv>0")
    if median_rssi is not None:
        if median_rssi > RSSI_COVERAGE_THRESHOLD:
            evidence_parts.append(f"RSSI={median_rssi:.1f}")
        else:
            evidence_parts.append(f"low_RSSI={median_rssi:.1f}")
    if mean_alt_div is not None and mean_alt_div > ALT_DIVERGENCE_FT:
        evidence_parts.append(f"alt_div={mean_alt_div:.0f}ft")
    if msg_rate is not None and msg_rate > 0:
        evidence_parts.append(f"msg_rate={msg_rate:.1f}/s")
    if mean_seen_pos is not None:
        evidence_parts.append(f"seen_pos={mean_seen_pos:.1f}s")

    scored = dict(event)
    scored["jamming_score"] = jam
    scored["coverage_score"] = cov
    scored["spoofing_score"] = spf
    scored["in_coverage_hole"] = in_hole
    scored["evidence"] = ", ".join(evidence_parts)
    return scored


def classify_event(scored_event: dict[str, Any]) -> str:
    """Classify an event based on its evidence scores.

    Accepts a scored event dict (output of score_event).
    Returns category string: gps_spoofing, gps_jamming, coverage_hole,
    probable_jamming, transponder_off, or ambiguous.
    """
    # Transponder shutdowns don't get re-classified via scoring
    if scored_event.get("source") == "gap_detection":
        return "transponder_off"

    spf_score = scored_event.get("spoofing_score", 0)
    jam_score = scored_event.get("jamming_score", 0)
    cov_score = scored_event.get("coverage_score", 0)

    if spf_score >= 4:
        return "gps_spoofing"
    elif jam_score >= 6 or (jam_score >= 4 and jam_score > cov_score):
        return "gps_jamming"
    elif cov_score >= 2 and cov_score > jam_score:
        return "coverage_hole"
    elif jam_score >= 2:
        return "probable_jamming"
    else:
        return "ambiguous"
