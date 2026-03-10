#!/usr/bin/env python3
"""Batch GPS anomaly detection — processes all aircraft in a time window.

Imports proven detection logic from detect_rule_based.py and detect_kalman.py,
runs batch SQL queries (all hexes at once), and writes results to dedicated
tables: rule_based_events and kalman_events.

Usage:
    uv run python detect_batch.py --hours-back 48
    uv run python detect_batch.py --start "2026-03-04" --end "2026-03-06"
    uv run python detect_batch.py --hours-back 48 --skip-kalman
    uv run python detect_batch.py --hours-back 48 --dry-run
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from dotenv import load_dotenv

from detect_rule_based import (
    build_coverage_baseline,
    score_event,
    classify_event,
    RSSI_COVERAGE_THRESHOLD,
    COVERAGE_GRID_SIZE,
    GAP_MINUTES_SHUTDOWN,
)
from detect_kalman import (
    kalman_filter,
    detect_position_jumps,
    detect_altitude_divergence,
    physics_cross_validation,
    classify_flight,
)

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

log = logging.getLogger("detect_batch")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

KALMAN_CHUNK_SIZE = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _copy_value(v) -> str:
    """Format a single value for PostgreSQL COPY (tab-delimited, \\N for null)."""
    if v is None:
        return "\\N"
    if isinstance(v, bool):
        return "t" if v else "f"
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


# ---------------------------------------------------------------------------
# DB Connection & Schema
# ---------------------------------------------------------------------------

def connect_db() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def ensure_schema(conn: psycopg.Connection) -> None:
    """Create rule_based_events and kalman_events tables if they don't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rule_based_events (
                id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                run_ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
                hex             TEXT NOT NULL,
                category        TEXT NOT NULL,
                source          TEXT NOT NULL,
                start_ts        TIMESTAMPTZ NOT NULL,
                end_ts          TIMESTAMPTZ,
                duration_s      DOUBLE PRECISION,
                entry_lat       DOUBLE PRECISION,
                entry_lon       DOUBLE PRECISION,
                exit_lat        DOUBLE PRECISION,
                exit_lon        DOUBLE PRECISION,
                region          TEXT,
                version         SMALLINT,
                n_reports       INTEGER,
                jamming_score   INTEGER,
                spoofing_score  INTEGER,
                coverage_score  INTEGER,
                evidence        TEXT,
                metadata        JSONB
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rbe_hex_start
            ON rule_based_events (hex, start_ts)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rbe_category
            ON rule_based_events (category, start_ts)
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS kalman_events (
                id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                run_ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
                hex                 TEXT NOT NULL,
                classification      TEXT NOT NULL,
                start_ts            TIMESTAMPTZ NOT NULL,
                end_ts              TIMESTAMPTZ,
                n_positions         INTEGER,
                n_flagged           INTEGER,
                flag_pct            DOUBLE PRECISION,
                n_jumps             INTEGER,
                n_alt_divergence    INTEGER,
                n_severe_alt_div    INTEGER,
                physics_confidence  DOUBLE PRECISION,
                physics_details     JSONB,
                entry_lat           DOUBLE PRECISION,
                entry_lon           DOUBLE PRECISION,
                exit_lat            DOUBLE PRECISION,
                exit_lon            DOUBLE PRECISION,
                metadata            JSONB
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ke_hex_start
            ON kalman_events (hex, start_ts)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ke_classification
            ON kalman_events (classification, start_ts)
        """)
    conn.commit()
    log.info("Schema ensured: rule_based_events, kalman_events")


# ---------------------------------------------------------------------------
# Batch Rule-Based: Integrity Events
# ---------------------------------------------------------------------------

def detect_integrity_batch(
    conn: psycopg.Connection,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Detect integrity degradation events for ALL hexes in one query.

    Same logic as detect_rule_based.detect_integrity_events but without
    the hex filter — processes every aircraft in the time window.
    """
    t0 = time.monotonic()
    with conn.cursor() as cur:
        cur.execute("""
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
                  AND ts >= %(start)s AND ts <= %(end)s
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
        """, {"start": start, "end": end})
        rows = cur.fetchall()

    events: list[dict[str, Any]] = []
    for row in rows:
        (hex_val, _event_id, ev_start_ts, ev_end_ts, duration_s, n_reports,
         entry_lat, entry_lon, exit_lat, exit_lon, version,
         nacp_zero, nic_zero, nic_low_7, gva_zero, nacv_high,
         region, median_rssi, has_gps_ok_before, mean_seen_pos, msg_rate,
         mean_alt_div, max_alt_div, gps_ok_lat, gps_ok_lon) = row

        median_rssi = float(median_rssi) if median_rssi is not None else None
        mean_seen_pos = float(mean_seen_pos) if mean_seen_pos is not None else None
        msg_rate = float(msg_rate) if msg_rate is not None else None
        mean_alt_div = float(mean_alt_div) if mean_alt_div is not None else None
        max_alt_div = float(max_alt_div) if max_alt_div is not None else None
        duration_s = float(duration_s) if duration_s is not None else 0.0

        events.append({
            "hex": hex_val,
            "source": "integrity_drop",
            "start_ts": ev_start_ts,
            "end_ts": ev_end_ts,
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

    elapsed = time.monotonic() - t0
    hexes = len({e["hex"] for e in events})
    log.info("Integrity batch: %d events from %d hexes in %.1fs", len(events), hexes, elapsed)
    return events


# ---------------------------------------------------------------------------
# Batch Rule-Based: Transponder Shutdowns
# ---------------------------------------------------------------------------

def detect_shutdowns_batch(
    conn: psycopg.Connection,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Detect transponder shutdowns for ALL hexes in one query.

    Same logic as detect_rule_based.detect_transponder_shutdowns but
    without the hex filter.
    """
    min_gap_s = GAP_MINUTES_SHUTDOWN * 60
    t0 = time.monotonic()
    with conn.cursor() as cur:
        cur.execute("""
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
                  AND ts >= %(start)s AND ts <= %(end)s
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
              AND extract(epoch FROM ts - prev_ts) > %(min_gap_s)s
              AND prev_on_ground = false
              AND (prev_alt IS NULL OR prev_alt > 2000)
              AND (prev_nac_p IS NULL OR prev_nac_p >= 8)
              AND (prev_rssi IS NULL OR prev_rssi > %(rssi_thresh)s)
            ORDER BY gap_duration_s DESC
            LIMIT 50000
        """, {
            "start": start,
            "end": end,
            "min_gap_s": min_gap_s,
            "rssi_thresh": RSSI_COVERAGE_THRESHOLD,
        })
        rows = cur.fetchall()

    events: list[dict[str, Any]] = []
    for row in rows:
        (hex_val, last_seen_ts, reappear_ts, gap_duration_s,
         last_lat, last_lon, last_alt_baro,
         reappear_lat, reappear_lon,
         last_nac_p, last_rssi, region) = row

        events.append({
            "hex": hex_val,
            "category": "transponder_off",
            "source": "gap_detection",
            "start_ts": last_seen_ts,
            "end_ts": reappear_ts,
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
            "evidence": "",
        })

    elapsed = time.monotonic() - t0
    hexes = len({e["hex"] for e in events})
    log.info("Shutdown batch: %d events from %d hexes in %.1fs", len(events), hexes, elapsed)
    return events


# ---------------------------------------------------------------------------
# Score & Classify Integrity Events
# ---------------------------------------------------------------------------

def score_and_classify(
    events: list[dict[str, Any]],
    coverage: dict[tuple[float, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Score and classify integrity events using imported rule-based logic.

    Adds category, scores, and evidence string to each event in-place.
    """
    for event in events:
        jam, cov_sc, spf = score_event(event, coverage)
        category = classify_event(jam, cov_sc, spf)
        event["jamming_score"] = jam
        event["coverage_score"] = cov_sc
        event["spoofing_score"] = spf
        event["category"] = category

        # Build evidence string (same logic as detect_rule_based.analyze_flight)
        parts: list[str] = []
        if event.get("has_gps_ok_before"):
            parts.append("gps_ok_before")
        v = event.get("version")
        v_label = f"V{v}" if v is not None else "V?"
        if event.get("nacp_zero"):
            parts.append(f"NACp=0({v_label})")
        if event.get("nic_zero"):
            parts.append(f"NIC=0({v_label})")
        if event.get("nic_low_7") and not event.get("nacp_zero"):
            parts.append(f"NIC<7({v_label})")
        if v == 2 and event.get("gva_zero"):
            parts.append("GVA=0")
        if v in (1, 2) and event.get("nacv_high"):
            parts.append("NACv>0")
        if event.get("median_rssi") is not None:
            if event["median_rssi"] > RSSI_COVERAGE_THRESHOLD:
                parts.append(f"RSSI={event['median_rssi']:.1f}")
            else:
                parts.append(f"low_RSSI={event['median_rssi']:.1f}")
        if event.get("mean_alt_divergence_ft") is not None and event["mean_alt_divergence_ft"] > 1000:
            parts.append(f"alt_div={event['mean_alt_divergence_ft']:.0f}ft")
        if event.get("msg_rate") is not None and event["msg_rate"] > 0:
            parts.append(f"msg_rate={event['msg_rate']:.1f}/s")
        if event.get("mean_seen_pos") is not None:
            parts.append(f"seen_pos={event['mean_seen_pos']:.1f}s")
        event["evidence"] = ", ".join(parts)

    return events


# ---------------------------------------------------------------------------
# Bulk Write: Rule-Based Events
# ---------------------------------------------------------------------------

def write_rule_events(conn: psycopg.Connection, events: list[dict[str, Any]]) -> int:
    """Bulk-insert rule-based events via COPY."""
    if not events:
        return 0

    cols = (
        "hex, category, source, start_ts, end_ts, duration_s, "
        "entry_lat, entry_lon, exit_lat, exit_lon, region, version, "
        "n_reports, jamming_score, spoofing_score, coverage_score, evidence, metadata"
    )
    buf = io.StringIO()
    for ev in events:
        meta = {}
        for k in ("nacp_zero", "nic_zero", "nic_low_7", "gva_zero", "nacv_high",
                   "has_gps_ok_before", "median_rssi", "mean_seen_pos", "msg_rate",
                   "mean_alt_divergence_ft", "max_alt_divergence_ft",
                   "gps_ok_lat", "gps_ok_lon"):
            val = ev.get(k)
            if val is not None:
                meta[k] = val
        vals = [
            ev["hex"], ev["category"], ev["source"],
            ev["start_ts"], ev.get("end_ts"),
            ev.get("duration_s"),
            ev.get("entry_lat"), ev.get("entry_lon"),
            ev.get("exit_lat"), ev.get("exit_lon"),
            ev.get("region"), ev.get("version"),
            ev.get("n_reports", 0),
            ev.get("jamming_score", 0), ev.get("spoofing_score", 0), ev.get("coverage_score", 0),
            ev.get("evidence", ""),
            json.dumps(meta) if meta else None,
        ]
        buf.write("\t".join(_copy_value(v) for v in vals) + "\n")

    buf.seek(0)
    with conn.cursor() as cur:
        with cur.copy(f"COPY rule_based_events ({cols}) FROM STDIN") as copy:
            for line in buf:
                copy.write(line)
    conn.commit()
    log.info("Wrote %d rule_based_events", len(events))
    return len(events)


# ---------------------------------------------------------------------------
# Bulk Write: Kalman Events
# ---------------------------------------------------------------------------

def write_kalman_events(conn: psycopg.Connection, events: list[dict[str, Any]]) -> int:
    """Bulk-insert Kalman events via COPY."""
    if not events:
        return 0

    cols = (
        "hex, classification, start_ts, end_ts, n_positions, n_flagged, "
        "flag_pct, n_jumps, n_alt_divergence, n_severe_alt_div, "
        "physics_confidence, physics_details, "
        "entry_lat, entry_lon, exit_lat, exit_lon, metadata"
    )
    buf = io.StringIO()
    for ev in events:
        vals = [
            ev["hex"], ev["classification"],
            ev["start_ts"], ev.get("end_ts"),
            ev.get("n_positions", 0), ev.get("n_flagged", 0),
            ev.get("flag_pct", 0.0),
            ev.get("n_jumps", 0), ev.get("n_alt_divergence", 0),
            ev.get("n_severe_alt_div", 0),
            ev.get("physics_confidence", 0.0),
            json.dumps(ev["physics_details"]) if ev.get("physics_details") else None,
            ev.get("entry_lat"), ev.get("entry_lon"),
            ev.get("exit_lat"), ev.get("exit_lon"),
            json.dumps(ev["metadata"]) if ev.get("metadata") else None,
        ]
        buf.write("\t".join(_copy_value(v) for v in vals) + "\n")

    buf.seek(0)
    with conn.cursor() as cur:
        with cur.copy(f"COPY kalman_events ({cols}) FROM STDIN") as copy:
            for line in buf:
                copy.write(line)
    conn.commit()
    log.info("Wrote %d kalman_events", len(events))
    return len(events)


# ---------------------------------------------------------------------------
# Kalman Batch Processing
# ---------------------------------------------------------------------------

def get_kalman_candidates(
    conn: psycopg.Connection,
    rule_events: list[dict[str, Any]],
    start: datetime,
    end: datetime,
) -> set[str]:
    """Build candidate hex set for Kalman analysis.

    Candidates = hexes from rule-based results + all hexes with NACp=0
    in the time window.
    """
    candidates = {ev["hex"] for ev in rule_events}
    rule_count = len(candidates)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT hex
            FROM positions
            WHERE source_type = 'adsb_icao'
              AND nac_p = 0
              AND on_ground = false
              AND lat IS NOT NULL
              AND ts >= %(start)s AND ts <= %(end)s
        """, {"start": start, "end": end})
        for row in cur.fetchall():
            candidates.add(row[0])

    log.info("Kalman candidates: %d total (%d from rule-based, %d from NACp=0)",
             len(candidates), rule_count, len(candidates) - rule_count)
    return candidates


def fetch_positions_batch(
    conn: psycopg.Connection,
    hexes: list[str],
    start: datetime,
    end: datetime,
) -> dict[str, list[dict]]:
    """Fetch positions for a batch of hexes, partitioned by hex."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT ts, hex, lat, lon, alt_baro, alt_geom, gs, tas, track,
                   true_heading, nac_p, nic, baro_rate, geom_rate, on_ground
            FROM positions
            WHERE hex = ANY(%(hexes)s)
              AND source_type = 'adsb_icao'
              AND on_ground = false
              AND lat IS NOT NULL
              AND ts >= %(start)s AND ts <= %(end)s
            ORDER BY hex, ts
        """, {"hexes": hexes, "start": start, "end": end})

        cols = [d[0] for d in cur.description]
        by_hex: dict[str, list[dict]] = {}
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            by_hex.setdefault(d["hex"], []).append(d)

    return by_hex


def run_kalman_batch(
    conn: psycopg.Connection,
    candidates: set[str],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Run Kalman analysis on candidate hexes in chunks, return non-normal events."""
    hex_list = sorted(candidates)
    total = len(hex_list)
    all_events: list[dict[str, Any]] = []
    t0 = time.monotonic()

    for i in range(0, total, KALMAN_CHUNK_SIZE):
        chunk = hex_list[i:i + KALMAN_CHUNK_SIZE]
        chunk_num = i // KALMAN_CHUNK_SIZE + 1
        n_chunks = (total + KALMAN_CHUNK_SIZE - 1) // KALMAN_CHUNK_SIZE
        log.info("Kalman chunk %d/%d: %d hexes", chunk_num, n_chunks, len(chunk))

        by_hex = fetch_positions_batch(conn, chunk, start, end)

        for hex_code, positions in by_hex.items():
            if len(positions) < 3:
                continue

            kalman_results = kalman_filter(positions)
            jumps = detect_position_jumps(positions)
            alt_div = detect_altitude_divergence(positions)
            physics = physics_cross_validation(positions)
            classification = classify_flight(kalman_results, jumps, alt_div, physics)

            if classification == "normal":
                continue

            n_flagged = sum(1 for r in kalman_results if r["flagged"])
            n_kalman = len(kalman_results)
            flag_pct = (n_flagged / n_kalman * 100) if n_kalman > 0 else 0.0
            n_severe = sum(1 for a in alt_div if a["severe"])

            all_events.append({
                "hex": hex_code,
                "classification": classification,
                "start_ts": positions[0]["ts"],
                "end_ts": positions[-1]["ts"],
                "n_positions": len(positions),
                "n_flagged": n_flagged,
                "flag_pct": round(flag_pct, 2),
                "n_jumps": len(jumps),
                "n_alt_divergence": len(alt_div),
                "n_severe_alt_div": n_severe,
                "physics_confidence": physics.get("confidence", 0.0),
                "physics_details": {
                    k: v for k, v in physics.items()
                    if k not in ("confidence",)
                },
                "entry_lat": positions[0]["lat"],
                "entry_lon": positions[0]["lon"],
                "exit_lat": positions[-1]["lat"],
                "exit_lon": positions[-1]["lon"],
                "metadata": {
                    "max_chi2": round(max((r["chi2"] for r in kalman_results), default=0), 2),
                    "max_jump_km": round(max((j["dist_km"] for j in jumps), default=0), 2),
                },
            })

    elapsed = time.monotonic() - t0
    log.info("Kalman batch: %d non-normal events from %d candidates in %.1fs",
             len(all_events), total, elapsed)
    return all_events


# ---------------------------------------------------------------------------
# CLI & Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch GPS anomaly detection — processes all aircraft in a time window."
    )
    parser.add_argument("--hours-back", type=int, default=None,
                        help="Hours of data to process (from now)")
    parser.add_argument("--start", type=str, default=None,
                        help="Window start (ISO 8601)")
    parser.add_argument("--end", type=str, default=None,
                        help="Window end (ISO 8601)")
    parser.add_argument("--skip-kalman", action="store_true",
                        help="Run rule-based detection only, skip Kalman")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run detection but don't write to DB")
    parser.add_argument("--lookback-days", type=int, default=30,
                        help="Days for coverage baseline (default: 30)")
    args = parser.parse_args()

    # Determine time window
    if args.hours_back is not None:
        end_ts = datetime.now(timezone.utc)
        start_ts = end_ts - timedelta(hours=args.hours_back)
    elif args.start is not None:
        start_ts = datetime.fromisoformat(args.start)
        if start_ts.tzinfo is None:
            start_ts = start_ts.replace(tzinfo=timezone.utc)
        if args.end is not None:
            end_ts = datetime.fromisoformat(args.end)
            if end_ts.tzinfo is None:
                end_ts = end_ts.replace(tzinfo=timezone.utc)
        else:
            end_ts = datetime.now(timezone.utc)
    else:
        parser.error("Either --hours-back or --start is required")
        return  # unreachable, for type checker

    log.info("=== Batch detection: %s -> %s ===", start_ts.isoformat(), end_ts.isoformat())
    if args.dry_run:
        log.info("DRY RUN — no DB writes")

    conn = connect_db()
    try:
        if not args.dry_run:
            ensure_schema(conn)

        # 1. Coverage baseline
        log.info("Step 1: Building coverage baseline...")
        coverage = build_coverage_baseline(conn, lookback_days=args.lookback_days)

        # 2. Integrity events (all hexes)
        log.info("Step 2: Detecting integrity events (batch)...")
        integrity_events = detect_integrity_batch(conn, start_ts, end_ts)

        # 3. Score & classify
        log.info("Step 3: Scoring and classifying...")
        score_and_classify(integrity_events, coverage)

        # 4. Transponder shutdowns (all hexes)
        log.info("Step 4: Detecting transponder shutdowns (batch)...")
        shutdown_events = detect_shutdowns_batch(conn, start_ts, end_ts)

        # Combine all rule-based events
        all_rule_events = integrity_events + shutdown_events

        # Print rule-based summary
        from collections import Counter
        rule_cats = Counter(ev["category"] for ev in all_rule_events)
        log.info("Rule-based results: %d events", len(all_rule_events))
        for cat, count in rule_cats.most_common():
            log.info("  %s: %d", cat, count)

        # 5. Write rule-based events
        if not args.dry_run:
            log.info("Step 5: Writing rule_based_events...")
            write_rule_events(conn, all_rule_events)
        else:
            log.info("Step 5: (dry run) Would write %d rule_based_events", len(all_rule_events))

        # 6-9. Kalman processing
        if args.skip_kalman:
            log.info("Skipping Kalman processing (--skip-kalman)")
        else:
            log.info("Step 6: Identifying Kalman candidates...")
            candidates = get_kalman_candidates(conn, all_rule_events, start_ts, end_ts)

            if candidates:
                log.info("Step 7-8: Running Kalman batch analysis...")
                kalman_events = run_kalman_batch(conn, candidates, start_ts, end_ts)

                # Print Kalman summary
                kalman_cats = Counter(ev["classification"] for ev in kalman_events)
                log.info("Kalman results: %d non-normal events", len(kalman_events))
                for cat, count in kalman_cats.most_common():
                    log.info("  %s: %d", cat, count)

                if not args.dry_run:
                    log.info("Step 9: Writing kalman_events...")
                    write_kalman_events(conn, kalman_events)
                else:
                    log.info("Step 9: (dry run) Would write %d kalman_events", len(kalman_events))
            else:
                log.info("No Kalman candidates found")

        log.info("=== Batch detection complete ===")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
