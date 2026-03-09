"""Tests for GetAnomaliesCube — data-source cube querying research.anomaly_reports.

Tests cover:
- Cube metadata (cube_id, category, inputs, outputs)
- Basic query with mocked DB returning anomaly rows
- Empty result handling
- Flight IDs filter
- Severity filter
- Anomaly status filter
- Empty flight_ids guard (returns empty without querying)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Helpers
# ============================================================

ANOMALY_COLUMNS = [
    "id", "flight_id", "timestamp", "is_anomaly",
    "severity_cnn", "severity_dense",
    "callsign", "airline", "origin_airport", "destination_airport",
    "aircraft_type", "geographic_region", "is_military",
    "matched_rule_ids", "matched_rule_names",
]


def make_anomaly_row(row_id: int, flight_id: str, severity: float = 0.8,
                     is_anomaly: bool = True) -> tuple:
    """Build a raw DB row tuple matching ANOMALY_COLUMNS."""
    return (
        row_id, flight_id, 1_700_000_000, is_anomaly,
        severity, severity * 0.9,
        "TEST01", "TestAir", "LLBG", "EGLL",
        "B738", "Middle East", False,
        [1, 2], ["rule_a", "rule_b"],
    )


def make_mock_conn(rows: list[tuple], columns: list[str] = None):
    """Create an async context manager mock for engine.connect()."""
    if columns is None:
        columns = ANOMALY_COLUMNS
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.keys.return_value = columns
    mock_result.fetchall.return_value = rows
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)
    return mock_conn


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """GetAnomaliesCube has correct cube_id and category."""
    from app.cubes.get_anomalies import GetAnomaliesCube
    from app.schemas.cube import CubeCategory

    cube = GetAnomaliesCube()
    assert cube.cube_id == "get_anomalies"
    assert cube.category == CubeCategory.DATA_SOURCE
    assert cube.name == "Get Anomalies"


def test_cube_inputs():
    """GetAnomaliesCube has expected input parameters."""
    from app.cubes.get_anomalies import GetAnomaliesCube

    cube = GetAnomaliesCube()
    input_names = {p.name for p in cube.inputs}
    expected = {"flight_ids", "min_severity", "is_anomaly", "matched_rule_name"}
    assert expected <= input_names


def test_cube_outputs():
    """GetAnomaliesCube has anomalies and flight_ids outputs."""
    from app.cubes.get_anomalies import GetAnomaliesCube

    cube = GetAnomaliesCube()
    output_names = {p.name for p in cube.outputs}
    assert "anomalies" in output_names
    assert "flight_ids" in output_names


# ============================================================
# Basic query
# ============================================================


@pytest.mark.asyncio
async def test_basic_query():
    """Basic query returns anomaly rows as dicts with correct structure."""
    from app.cubes.get_anomalies import GetAnomaliesCube

    rows = [
        make_anomaly_row(1, "F001", 0.9),
        make_anomaly_row(2, "F002", 0.7),
    ]
    mock_conn = make_mock_conn(rows)

    cube = GetAnomaliesCube()
    with patch("app.cubes.get_anomalies.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute()

    assert len(result["anomalies"]) == 2
    assert result["anomalies"][0]["flight_id"] == "F001"
    assert result["anomalies"][0]["severity_cnn"] == 0.9
    assert set(result["flight_ids"]) == {"F001", "F002"}


@pytest.mark.asyncio
async def test_empty_result():
    """Empty DB result returns empty anomalies list and empty flight_ids."""
    from app.cubes.get_anomalies import GetAnomaliesCube

    mock_conn = make_mock_conn([])

    cube = GetAnomaliesCube()
    with patch("app.cubes.get_anomalies.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute()

    assert result["anomalies"] == []
    assert result["flight_ids"] == []


# ============================================================
# Filters
# ============================================================


@pytest.mark.asyncio
async def test_flight_ids_filter():
    """Passing flight_ids adds ANY filter to query params."""
    from app.cubes.get_anomalies import GetAnomaliesCube

    rows = [make_anomaly_row(1, "F001")]
    mock_conn = make_mock_conn(rows)

    cube = GetAnomaliesCube()
    with patch("app.cubes.get_anomalies.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(flight_ids=["F001", "F002"])

    assert len(result["anomalies"]) == 1
    call_args = mock_conn.execute.call_args
    sql_params = call_args[0][1] if len(call_args[0]) > 1 else {}
    assert sql_params.get("flight_ids") == ["F001", "F002"]


@pytest.mark.asyncio
async def test_severity_filter():
    """Passing min_severity adds severity_cnn >= filter."""
    from app.cubes.get_anomalies import GetAnomaliesCube

    rows = [make_anomaly_row(1, "F001", 0.9)]
    mock_conn = make_mock_conn(rows)

    cube = GetAnomaliesCube()
    with patch("app.cubes.get_anomalies.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(min_severity=0.5)

    call_args = mock_conn.execute.call_args
    sql_params = call_args[0][1] if len(call_args[0]) > 1 else {}
    assert sql_params.get("min_severity") == 0.5


@pytest.mark.asyncio
async def test_is_anomaly_filter():
    """Passing is_anomaly adds boolean filter."""
    from app.cubes.get_anomalies import GetAnomaliesCube

    rows = [make_anomaly_row(1, "F001", is_anomaly=True)]
    mock_conn = make_mock_conn(rows)

    cube = GetAnomaliesCube()
    with patch("app.cubes.get_anomalies.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(is_anomaly=True)

    call_args = mock_conn.execute.call_args
    sql_params = call_args[0][1] if len(call_args[0]) > 1 else {}
    assert sql_params.get("is_anomaly") is True


@pytest.mark.asyncio
async def test_empty_flight_ids_guard():
    """Empty flight_ids list does not add flight_ids filter (queries all)."""
    from app.cubes.get_anomalies import GetAnomaliesCube

    rows = [make_anomaly_row(1, "F001")]
    mock_conn = make_mock_conn(rows)

    cube = GetAnomaliesCube()
    with patch("app.cubes.get_anomalies.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(flight_ids=[])

    # Empty list treated as falsy, so no flight_ids param in SQL
    call_args = mock_conn.execute.call_args
    sql_params = call_args[0][1] if len(call_args[0]) > 1 else {}
    assert "flight_ids" not in sql_params


@pytest.mark.asyncio
async def test_unique_flight_ids_deduplication():
    """Multiple anomaly rows for same flight_id yield single entry in flight_ids output."""
    from app.cubes.get_anomalies import GetAnomaliesCube

    rows = [
        make_anomaly_row(1, "F001", 0.9),
        make_anomaly_row(2, "F001", 0.7),
        make_anomaly_row(3, "F002", 0.8),
    ]
    mock_conn = make_mock_conn(rows)

    cube = GetAnomaliesCube()
    with patch("app.cubes.get_anomalies.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute()

    assert len(result["anomalies"]) == 3
    assert set(result["flight_ids"]) == {"F001", "F002"}
