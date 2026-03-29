"""Unit tests for app.cubes.utils.historical_query.

Tests cover:
- Empty input → empty dict
- Single callsign query returns keyed dict with correct row shape
- Deduplication of callsigns uses asyncio.gather with correct call count
- epoch_cutoff integration (lookback_seconds respected)
- Empty route input → empty dict
- Single route query returns keyed dict with tuple key
- Route deduplication uses asyncio.gather with correct call count
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.cubes.utils.historical_query import get_callsign_history, get_route_history


# ============================================================
# Helpers
# ============================================================

HISTORY_COLUMNS = [
    "flight_id", "callsign", "first_seen_ts", "last_seen_ts",
    "start_lat", "start_lon", "end_lat", "end_lon",
    "origin_airport", "destination_airport",
]


def make_history_row(
    flight_id: str = "FL001",
    callsign: str = "AAL123",
    origin: str = "LLBG",
    destination: str = "EGLL",
) -> tuple:
    """Build a raw DB row tuple matching HISTORY_COLUMNS."""
    return (
        flight_id, callsign,
        1_700_000_000, 1_700_003_600,
        32.0, 34.8, 51.5, -0.1,
        origin, destination,
    )


def make_conn_for_rows(rows: list[tuple]):
    """Create an async context manager mock for a single engine.connect() call."""
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.keys.return_value = HISTORY_COLUMNS
    mock_result.fetchall.return_value = rows
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)
    return mock_conn


def make_mock_engine(rows_per_call: list[list[tuple]] | None = None):
    """Mock engine where connect() returns fresh conn per call."""
    mock_engine = MagicMock()
    call_index = [0]

    def make_conn():
        idx = call_index[0]
        call_index[0] += 1
        rows = []
        if rows_per_call and idx < len(rows_per_call):
            rows = rows_per_call[idx]
        return make_conn_for_rows(rows)

    mock_engine.connect = MagicMock(side_effect=lambda: make_conn())
    return mock_engine


# ============================================================
# get_callsign_history tests
# ============================================================

@pytest.mark.asyncio
async def test_callsign_history_empty_input():
    """get_callsign_history([]) returns empty dict without querying DB."""
    result = await get_callsign_history([])
    assert result == {}


@pytest.mark.asyncio
@patch("app.cubes.utils.historical_query.engine")
async def test_callsign_history_single_callsign(mock_engine):
    """get_callsign_history(['AAL123']) returns {'AAL123': [row_dict]}."""
    row = make_history_row(callsign="AAL123")
    mock_engine.connect = MagicMock(side_effect=lambda: make_conn_for_rows([row]))

    result = await get_callsign_history(["AAL123"])

    assert "AAL123" in result
    assert len(result["AAL123"]) == 1
    assert result["AAL123"][0]["callsign"] == "AAL123"
    assert result["AAL123"][0]["flight_id"] == "FL001"


@pytest.mark.asyncio
@patch("app.cubes.utils.historical_query.engine")
async def test_callsign_history_row_keys(mock_engine):
    """Returned row dicts contain all expected flight_metadata columns."""
    row = make_history_row()
    mock_engine.connect = MagicMock(side_effect=lambda: make_conn_for_rows([row]))

    result = await get_callsign_history(["AAL123"])
    row_dict = result["AAL123"][0]

    for col in HISTORY_COLUMNS:
        assert col in row_dict, f"Missing column: {col}"


@pytest.mark.asyncio
@patch("app.cubes.utils.historical_query.engine")
async def test_callsign_history_deduplication(mock_engine):
    """Duplicate callsigns are deduplicated — engine.connect() called once per unique callsign."""
    row_aal = make_history_row(flight_id="FL001", callsign="AAL123")
    row_baw = make_history_row(flight_id="FL002", callsign="BAW456")

    connect_calls = [0]
    conn_aal = make_conn_for_rows([row_aal])
    conn_baw = make_conn_for_rows([row_baw])
    connections = [conn_aal, conn_baw]

    def side_effect():
        i = connect_calls[0]
        connect_calls[0] += 1
        return connections[i % len(connections)]

    mock_engine.connect = MagicMock(side_effect=side_effect)

    # 3 callsigns but only 2 unique
    result = await get_callsign_history(["AAL123", "AAL123", "BAW456"])

    # connect() called exactly twice (one per unique callsign)
    assert mock_engine.connect.call_count == 2
    # Both unique callsigns present in result
    assert len(result) == 2


@pytest.mark.asyncio
@patch("app.cubes.utils.historical_query.engine")
async def test_callsign_history_empty_db_result(mock_engine):
    """get_callsign_history returns callsign key with empty list when no DB rows."""
    mock_engine.connect = MagicMock(side_effect=lambda: make_conn_for_rows([]))

    result = await get_callsign_history(["AAL123"])
    assert "AAL123" in result
    assert result["AAL123"] == []


@pytest.mark.asyncio
@patch("app.cubes.utils.historical_query.engine")
@patch("app.cubes.utils.historical_query.epoch_cutoff")
async def test_callsign_history_uses_epoch_cutoff(mock_epoch_cutoff, mock_engine):
    """get_callsign_history calls epoch_cutoff with the provided lookback_seconds."""
    mock_epoch_cutoff.return_value = 1_700_000_000
    mock_engine.connect = MagicMock(side_effect=lambda: make_conn_for_rows([]))

    await get_callsign_history(["AAL123"], lookback_seconds=86400)

    mock_epoch_cutoff.assert_called_once_with(86400)


@pytest.mark.asyncio
@patch("app.cubes.utils.historical_query.engine")
@patch("app.cubes.utils.historical_query.epoch_cutoff")
async def test_callsign_history_custom_lookback(mock_epoch_cutoff, mock_engine):
    """Custom lookback_seconds is passed through to epoch_cutoff."""
    mock_epoch_cutoff.return_value = 1_699_000_000
    mock_engine.connect = MagicMock(side_effect=lambda: make_conn_for_rows([]))

    await get_callsign_history(["AAL123"], lookback_seconds=172800)

    mock_epoch_cutoff.assert_called_once_with(172800)


# ============================================================
# get_route_history tests
# ============================================================

@pytest.mark.asyncio
async def test_route_history_empty_input():
    """get_route_history([]) returns empty dict without querying DB."""
    result = await get_route_history([])
    assert result == {}


@pytest.mark.asyncio
@patch("app.cubes.utils.historical_query.engine")
async def test_route_history_single_route(mock_engine):
    """get_route_history([('LLBG', 'EGLL')]) returns {('LLBG', 'EGLL'): [row_dict]}."""
    row = make_history_row(origin="LLBG", destination="EGLL")
    mock_engine.connect = MagicMock(side_effect=lambda: make_conn_for_rows([row]))

    result = await get_route_history([("LLBG", "EGLL")])

    assert ("LLBG", "EGLL") in result
    assert len(result[("LLBG", "EGLL")]) == 1
    assert result[("LLBG", "EGLL")][0]["origin_airport"] == "LLBG"
    assert result[("LLBG", "EGLL")][0]["destination_airport"] == "EGLL"


@pytest.mark.asyncio
@patch("app.cubes.utils.historical_query.engine")
async def test_route_history_row_keys(mock_engine):
    """Returned row dicts contain all expected flight_metadata columns."""
    row = make_history_row()
    mock_engine.connect = MagicMock(side_effect=lambda: make_conn_for_rows([row]))

    result = await get_route_history([("LLBG", "EGLL")])
    row_dict = result[("LLBG", "EGLL")][0]

    for col in HISTORY_COLUMNS:
        assert col in row_dict, f"Missing column: {col}"


@pytest.mark.asyncio
@patch("app.cubes.utils.historical_query.engine")
async def test_route_history_deduplication(mock_engine):
    """Duplicate routes are deduplicated — connect() called once per unique route."""
    row_r1 = make_history_row(flight_id="FL001", origin="LLBG", destination="EGLL")
    row_r2 = make_history_row(flight_id="FL002", origin="EGLL", destination="LLBG")

    connect_calls = [0]
    connections = [make_conn_for_rows([row_r1]), make_conn_for_rows([row_r2])]

    def side_effect():
        i = connect_calls[0]
        connect_calls[0] += 1
        return connections[i % len(connections)]

    mock_engine.connect = MagicMock(side_effect=side_effect)

    # 3 routes but only 2 unique
    result = await get_route_history([
        ("LLBG", "EGLL"),
        ("LLBG", "EGLL"),
        ("EGLL", "LLBG"),
    ])

    assert mock_engine.connect.call_count == 2
    assert len(result) == 2


@pytest.mark.asyncio
@patch("app.cubes.utils.historical_query.engine")
async def test_route_history_tuple_keys(mock_engine):
    """get_route_history result keys are tuples (origin, destination)."""
    row = make_history_row(origin="KJFK", destination="KLAX")
    mock_engine.connect = MagicMock(side_effect=lambda: make_conn_for_rows([row]))

    result = await get_route_history([("KJFK", "KLAX")])

    key = list(result.keys())[0]
    assert isinstance(key, tuple)
    assert key == ("KJFK", "KLAX")
