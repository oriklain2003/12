"""Shared time utilities for behavioral cubes (Phases 24-26).

Provides epoch helpers, datetime pair validation, and reusable ParamDefinition
list for consistent time mode toggles across all behavioral cubes.

Per D-01: explicit time_mode param.
Per D-02: default 7-day lookback.
Per D-03: epoch seconds throughout.
"""

import time

from app.schemas.cube import ParamDefinition, ParamType


def epoch_cutoff(lookback_seconds: int) -> int:
    """Return the epoch second cutoff for a rolling lookback window.

    Args:
        lookback_seconds: How many seconds to look back from now.

    Returns:
        Current epoch time minus lookback_seconds as int.
    """
    return int(time.time()) - int(lookback_seconds)


def validate_datetime_pair(
    start_time: str | None,
    end_time: str | None,
) -> dict | None:
    """Validate that datetime params are provided as a complete pair.

    Returns error dict if only one provided, None if valid (both or neither).

    Args:
        start_time: Start time as epoch seconds string, or None.
        end_time: End time as epoch seconds string, or None.

    Returns:
        None if valid (both or neither provided).
        Dict with 'error' key if partial input.
    """
    has_start = start_time is not None
    has_end = end_time is not None
    if has_start and not has_end:
        return {
            "error": (
                "Partial datetime input: start_time provided but end_time is missing. "
                "Provide both or neither."
            )
        }
    if has_end and not has_start:
        return {
            "error": (
                "Partial datetime input: end_time provided but start_time is missing. "
                "Provide both or neither."
            )
        }
    return None


# Reusable ParamDefinition list for behavioral cubes (Phases 24-26).
# Cubes copy these into their `inputs` list to get consistent time mode toggle.
# Per D-01: explicit time_mode param. Per D-02: default 7 days. Per D-03: epoch seconds.
TIME_MODE_PARAMS: list[ParamDefinition] = [
    ParamDefinition(
        name="time_mode",
        type=ParamType.STRING,
        description="Time selection mode: 'lookback' (rolling window) or 'datetime' (fixed range).",
        required=False,
        default="lookback",
        widget_hint="toggle",
        options=["lookback", "datetime"],
    ),
    ParamDefinition(
        name="lookback_days",
        type=ParamType.NUMBER,
        description="Days of history to query (used when time_mode='lookback'). Default: 7.",
        required=False,
        default=7,
    ),
    ParamDefinition(
        name="start_time",
        type=ParamType.STRING,
        description="Absolute start time as epoch seconds string (used when time_mode='datetime').",
        required=False,
        widget_hint="datetime",
    ),
    ParamDefinition(
        name="end_time",
        type=ParamType.STRING,
        description="Absolute end time as epoch seconds string (used when time_mode='datetime').",
        required=False,
        widget_hint="datetime",
    ),
]
