"""Shared time utility functions for cube datetime validation."""


def validate_datetime_pair(
    start_time: str | None,
    end_time: str | None,
) -> dict | None:
    """Returns error dict if only one of start_time/end_time is provided, None if valid (both or neither).

    Per D-08: validation must apply consistently across all cubes with datetime params.
    Per D-09: errors surface as output dict keys, not exceptions.
    """
    has_start = start_time is not None
    has_end = end_time is not None
    if has_start and not has_end:
        return {"error": "Partial datetime input: start_time provided but end_time is missing. Provide both or neither."}
    if has_end and not has_start:
        return {"error": "Partial datetime input: end_time provided but start_time is missing. Provide both or neither."}
    return None
