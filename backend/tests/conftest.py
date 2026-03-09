"""Shared test fixtures and helpers for cube unit tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest


def make_mock_db_conn(results=None):
    """Create a mock async DB connection context manager.

    Args:
        results: Single MagicMock result or list for side_effect.
            - None: returns empty result (fetchall=[], keys=[])
            - MagicMock: returned by execute()
            - list: used as side_effect for execute() (multiple calls)
    """
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    if results is None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.keys.return_value = []
        mock_conn.execute = AsyncMock(return_value=mock_result)
    elif isinstance(results, list):
        mock_conn.execute = AsyncMock(side_effect=results)
    else:
        mock_conn.execute = AsyncMock(return_value=results)

    return mock_conn
