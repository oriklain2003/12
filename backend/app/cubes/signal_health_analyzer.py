"""SignalHealthAnalyzerCube: GPS anomaly detection using rule-based + Kalman filter analysis.

Orchestrates both detection layers from app.signal:
  - Rule-based (app.signal.rule_based): integrity events, transponder shutdowns, scoring
  - Kalman (app.signal.kalman): chi-squared position filtering, jump detection, physics

Inputs: hex_list, full_result, target_phase, classify_mode
Outputs: flight_ids, count, events, stats_summary
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType
from app.signal.kalman import classify_flight_async, fetch_positions_batch_async
from app.signal.rule_based import (
    classify_event,
    detect_integrity_events_batch_async,
    detect_shutdowns_batch_async,
    get_coverage_baseline,
    score_event,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# classify_mode mapping: user-facing labels → internal event categories
# ---------------------------------------------------------------------------

CLASSIFY_MODE_MAP: dict[str, set[str]] = {
    "Stable":         set(),                            # hexes with ZERO non-normal events
    "Jamming":        {"gps_jamming", "probable_jamming"},
    "Spoofing":       {"gps_spoofing"},
    "Dark Target":    {"transponder_off"},
    "Technical Gaps": {"coverage_hole", "ambiguous"},
}

# Which classify_mode labels require which detection layers
_NEEDS_KALMAN = {"Spoofing"}
_NEEDS_RULE_BASED = {"Jamming", "Dark Target", "Technical Gaps", "Stable"}


# ---------------------------------------------------------------------------
# Unified event schema helper
# ---------------------------------------------------------------------------

def kalman_event_from_result(hex_code: str, result: dict) -> dict:
    """Convert classify_flight_async result to unified event schema.

    Fills Kalman-specific fields and nulls out rule-based fields that don't
    apply, giving a consistent structure for all events in the output.
    """
    kr = result.get("kalman_results", [])
    n_flagged = sum(1 for r in kr if r.get("flagged"))
    n_kalman = len(kr)
    flag_pct = (n_flagged / n_kalman * 100) if n_kalman else 0.0
    alt_div = result.get("alt_divergence", [])
    n_severe = sum(1 for a in alt_div if a.get("severe"))

    # start/end are already ISO strings (serialized by classify_flight_async)
    start_str = result.get("start")
    end_str = result.get("end")

    return {
        "hex": hex_code,
        "category": result["classification"],        # gps_spoofing or anomalous
        "classification": result["classification"],  # Kalman-specific field
        "source": "kalman",
        "start_ts": start_str,
        "end_ts": end_str,
        "duration_s": None,                          # not available without datetime objects
        "entry_lat": None,
        "entry_lon": None,
        "exit_lat": None,
        "exit_lon": None,
        "region": None,
        # Kalman-specific metrics
        "n_flagged": n_flagged,
        "flag_pct": round(flag_pct, 2),
        "n_jumps": len(result.get("jumps", [])),
        "n_alt_divergence": len(alt_div),
        "n_severe_alt_div": n_severe,
        "physics_confidence": result.get("physics", {}).get("confidence", 0.0),
        # Rule-based fields (null for Kalman events)
        "jamming_score": None,
        "spoofing_score": None,
        "coverage_score": None,
        "evidence": None,
    }


# ---------------------------------------------------------------------------
# classify_mode filter
# ---------------------------------------------------------------------------

def filter_by_classify_mode(
    events: list[dict],
    classify_mode: list[str],
) -> list[dict]:
    """Filter events by user-facing classify_mode labels.

    If "all" is in classify_mode, return all events unfiltered.
    If only "Stable" is selected, this function returns empty list — the
    caller is responsible for computing the stable-hex set separately.
    """
    if "all" in classify_mode:
        return events

    wanted: set[str] = set()
    for label in classify_mode:
        wanted.update(CLASSIFY_MODE_MAP.get(label, set()))

    return [
        ev for ev in events
        if ev.get("category") in wanted or ev.get("classification") in wanted
    ]


# ---------------------------------------------------------------------------
# Cube
# ---------------------------------------------------------------------------

class SignalHealthAnalyzerCube(BaseCube):
    """Analysis cube: GPS anomaly detection — rule-based + Kalman filter.

    Accepts hex_list from upstream AlisonFlights (or any cube providing hex_list).
    Runs batch detection (3 queries total), then processes per-hex in memory,
    and returns flight_ids + events + stats.
    """

    cube_id = "signal_health_analyzer"
    name = "Signal Health Analyzer"
    description = "GPS anomaly detection — rule-based + Kalman filter analysis for individual flights"
    category = CubeCategory.ANALYSIS

    inputs = [
        ParamDefinition(
            name="hex_list",
            type=ParamType.LIST_OF_STRINGS,
            required=True,
            description="ICAO24 hex identifiers from AlisonFlights or upstream cube",
        ),
        ParamDefinition(
            name="full_result",
            type=ParamType.JSON_OBJECT,
            required=False,
            accepts_full_result=True,
            description="Full Result from upstream cube (extracts hex_list if connected)",
        ),
        ParamDefinition(
            name="target_phase",
            type=ParamType.STRING,
            required=False,
            default="any",
            description="Flight phase to analyze: takeoff / cruise / landing / any",
            widget_hint="select",
            options=["any", "takeoff", "cruise", "landing"],
        ),
        ParamDefinition(
            name="classify_mode",
            type=ParamType.LIST_OF_STRINGS,
            required=False,
            default=["all"],
            description="Filter output by user-facing classification label",
            widget_hint="tags",
            options=["all", "Stable", "Jamming", "Spoofing", "Dark Target", "Technical Gaps"],
        ),
        ParamDefinition(
            name="lookback_hours",
            type=ParamType.NUMBER,
            required=False,
            default=24,
            description="How many hours back to analyze (default 24). Increase for historical analysis.",
        ),
    ]

    outputs = [
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Hex IDs of flights with non-normal events matching classify_mode",
        ),
        ParamDefinition(
            name="count",
            type=ParamType.NUMBER,
            description="Count of matching flights",
        ),
        ParamDefinition(
            name="events",
            type=ParamType.JSON_OBJECT,
            description="Array of all non-normal events with detection fields",
        ),
        ParamDefinition(
            name="stats_summary",
            type=ParamType.JSON_OBJECT,
            description="Count of events per category across all analyzed flights",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Orchestrate rule-based + Kalman detection using batch queries."""
        t0 = time.monotonic()

        # ------------------------------------------------------------------
        # 1. Extract hex_list (from direct input or full_result connection)
        # ------------------------------------------------------------------
        hex_list: list[str] = inputs.get("hex_list") or []
        full_result = inputs.get("full_result")
        if not hex_list and full_result and isinstance(full_result, dict):
            hex_list = full_result.get("hex_list") or full_result.get("flight_ids") or []

        if not hex_list:
            log.info("SignalHealthAnalyzer: no hexes provided, returning empty result")
            return self._empty_result()

        classify_mode: list[str] = inputs.get("classify_mode") or ["all"]
        target_phase: str = (inputs.get("target_phase") or "any").lower().strip()
        lookback_hours: float = float(inputs.get("lookback_hours") or 24)

        log.info(
            "SignalHealthAnalyzer: analyzing %d hexes, classify_mode=%s, target_phase=%s, lookback=%.0fh",
            len(hex_list), classify_mode, target_phase, lookback_hours,
        )

        # ------------------------------------------------------------------
        # 2. Compute time range in Python (no per-hex DB fetch needed)
        # ------------------------------------------------------------------
        end_ts = datetime.now(timezone.utc)
        start_ts = end_ts - timedelta(hours=lookback_hours)

        # ------------------------------------------------------------------
        # 3. Determine which detection layers are needed
        # ------------------------------------------------------------------
        # Normalize hex codes once for consistent lookup
        hex_list_normalized = [str(h).strip().lower() for h in hex_list]

        mode_set = set(classify_mode)
        if "all" in mode_set:
            need_rule_based = True
            need_kalman = True
        else:
            need_rule_based = bool(mode_set & _NEEDS_RULE_BASED)
            need_kalman = bool(mode_set & _NEEDS_KALMAN)

        log.info(
            "SignalHealthAnalyzer: layers rule_based=%s kalman=%s",
            need_rule_based, need_kalman,
        )

        # ------------------------------------------------------------------
        # 4. Batch queries — only fetch what's needed
        # ------------------------------------------------------------------
        coverage_baseline = await get_coverage_baseline() if need_rule_based else {}

        queries: list = []
        query_keys: list[str] = []

        if need_rule_based:
            queries.append(detect_integrity_events_batch_async(hex_list_normalized, start_ts, end_ts))
            query_keys.append("integrity")
            queries.append(detect_shutdowns_batch_async(hex_list_normalized, start_ts, end_ts))
            query_keys.append("shutdown")
        if need_kalman:
            queries.append(fetch_positions_batch_async(hex_list_normalized, start_ts, end_ts))
            query_keys.append("positions")

        results = await asyncio.gather(*queries)
        result_map = dict(zip(query_keys, results))

        integrity_by_hex: dict = result_map.get("integrity", {})
        shutdown_by_hex: dict = result_map.get("shutdown", {})
        positions_by_hex: dict = result_map.get("positions", {})

        # ------------------------------------------------------------------
        # 5. Per-hex processing loop (in-memory, no DB calls)
        # ------------------------------------------------------------------
        hex_events: dict[str, list[dict]] = {}
        stable_hexes: set[str] = set()

        for raw_hex in hex_list:
            hx = str(raw_hex).strip().lower()
            try:
                rule_events: list[dict] = []
                kalman_events: list[dict] = []

                if need_rule_based:
                    # Score + classify integrity events
                    for ev in integrity_by_hex.get(hx, []):
                        scored = score_event(ev, coverage_baseline)
                        scored["category"] = classify_event(scored)
                        rule_events.append(scored)

                    # Score + classify shutdown events
                    for ev in shutdown_by_hex.get(hx, []):
                        scored = score_event(ev, coverage_baseline)
                        scored["category"] = classify_event(scored)
                        rule_events.append(scored)

                if need_kalman:
                    # Run Kalman on pre-fetched positions (skips per-hex DB fetch)
                    hex_positions = positions_by_hex.get(hx)
                    if hex_positions:
                        kalman_result = await classify_flight_async(
                            hx, start_ts, end_ts, positions=hex_positions
                        )
                        if kalman_result.get("classification") not in ("normal", None):
                            kalman_events.append(kalman_event_from_result(hx, kalman_result))

                all_hex_events = rule_events + kalman_events

                # Apply target_phase post-hoc filtering
                if target_phase != "any" and all_hex_events:
                    all_hex_events = self._filter_events_by_phase(all_hex_events, target_phase)

                if all_hex_events:
                    hex_events[hx] = all_hex_events
                else:
                    stable_hexes.add(hx)

            except Exception as exc:
                log.warning(
                    "SignalHealthAnalyzer: error analyzing hex=%s: %s — skipping",
                    hx, exc, exc_info=True,
                )

        # ------------------------------------------------------------------
        # 6. Apply classify_mode filtering
        # ------------------------------------------------------------------
        only_stable = (
            len(classify_mode) == 1
            and classify_mode[0] == "Stable"
        )

        if only_stable:
            # Return hexes that had ZERO non-normal events
            filtered_flight_ids = sorted(stable_hexes)
            filtered_events: list[dict] = []
        else:
            # Flatten all events then filter
            all_events: list[dict] = []
            for evs in hex_events.values():
                all_events.extend(evs)

            filtered_events = filter_by_classify_mode(all_events, classify_mode)

            # flight_ids = unique hexes that have at least one filtered event
            seen_hexes: set[str] = set()
            for ev in filtered_events:
                h = ev.get("hex")
                if h:
                    seen_hexes.add(h)
            filtered_flight_ids = sorted(seen_hexes)

        # ------------------------------------------------------------------
        # 7. Build outputs
        # ------------------------------------------------------------------
        stats_summary = dict(Counter(
            ev.get("category") or ev.get("classification") or "unknown"
            for ev in filtered_events
        ))

        elapsed = time.monotonic() - t0
        log.info(
            "SignalHealthAnalyzer: done in %.1fs — %d/%d hexes matched, %d events",
            elapsed, len(filtered_flight_ids), len(hex_list), len(filtered_events),
        )

        return {
            "flight_ids": filtered_flight_ids,
            "count": len(filtered_flight_ids),
            "events": filtered_events,
            "stats_summary": stats_summary,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _filter_events_by_phase(
        self,
        events: list[dict],
        target_phase: str,
    ) -> list[dict]:
        """Post-hoc filter: keep events whose entry altitude matches the target phase.

        v1 approximation — uses entry_lat/entry_lon altitude info when available.
        Constants:
          TAKEOFF_ALT_CEILING = 5000 ft  (ascending, alt_baro < 5000)
          CRUISE_ALT_FLOOR    = 10000 ft (alt_baro >= 10000)
          LANDING_ALT_CEILING = 5000 ft  (descending, alt_baro < 5000)

        Note: takeoff vs landing cannot be distinguished reliably without baro_rate,
        so both use the <5000 ft criterion in v1. Tunable for v2.
        """
        TAKEOFF_ALT_CEILING = 5000
        CRUISE_ALT_FLOOR = 10000

        filtered = []
        for ev in events:
            # Kalman events don't have per-event altitude — pass through
            if ev.get("source") == "kalman":
                filtered.append(ev)
                continue

            alt = ev.get("last_alt_baro") or ev.get("entry_alt")
            if alt is None:
                # No altitude data — include event (can't determine phase)
                filtered.append(ev)
                continue

            try:
                alt = float(alt)
            except (TypeError, ValueError):
                filtered.append(ev)
                continue

            if target_phase in ("takeoff", "landing"):
                if alt < TAKEOFF_ALT_CEILING:
                    filtered.append(ev)
            elif target_phase == "cruise":
                if alt >= CRUISE_ALT_FLOOR:
                    filtered.append(ev)
            else:
                filtered.append(ev)

        return filtered

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "flight_ids": [],
            "count": 0,
            "events": [],
            "stats_summary": {},
        }
