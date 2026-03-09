"""Integration pipeline tests for multi-cube workflows through WorkflowExecutor.

Tests verify data flows correctly through realistic multi-cube chains:
1. AllFlights -> FilterFlights -> GetAnomalies (FR analysis pipeline)
2. AlisonFlights -> SquawkFilter -> DarkFlightDetector (Alison filter chain)
3. AlisonFlights -> SignalHealthAnalyzer (signal analysis pipeline)

All cubes are mocked -- tests verify the executor's wiring, not cube logic.
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Any

from app.schemas.workflow import (
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeData,
    Position,
)


# ============================================================
# Helpers (duplicated from test_executor.py per project convention)
# ============================================================


def make_node(node_id: str, cube_id: str, params: dict | None = None) -> WorkflowNode:
    """Helper to build a WorkflowNode."""
    return WorkflowNode(
        id=node_id,
        type="cube",
        position=Position(x=0, y=0),
        data=WorkflowNodeData(cube_id=cube_id, params=params or {}),
    )


def make_edge(
    edge_id: str,
    source: str,
    target: str,
    source_handle: str = "result",
    target_handle: str = "value",
) -> WorkflowEdge:
    """Helper to build a WorkflowEdge."""
    return WorkflowEdge(
        id=edge_id,
        source=source,
        target=target,
        sourceHandle=source_handle,
        targetHandle=target_handle,
    )


# ============================================================
# Mock cube classes
# ============================================================


class MockAllFlightsCube:
    """Mock AllFlightsCube returning flight data."""
    cube_id = "all_flights"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        return {
            "flight_ids": ["FL001", "FL002", "FL003"],
            "count": 3,
            "flights": [
                {"flight": "FL001", "hex": "aaa111", "callsign": "TST001"},
                {"flight": "FL002", "hex": "bbb222", "callsign": "TST002"},
                {"flight": "FL003", "hex": "ccc333", "callsign": "TST003"},
            ],
        }


class MockFilterFlightsCube:
    """Mock filter cube that passes through full_result and adds filter metadata."""
    cube_id = "filter_flights"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        full_result = inputs.get("full_result", {})
        flight_ids = full_result.get("flight_ids", [])
        # Simulate filtering: keep first 2
        filtered = flight_ids[:2]
        return {
            "flight_ids": filtered,
            "count": len(filtered),
            "flights": [f for f in full_result.get("flights", []) if f.get("flight") in filtered],
        }


class MockGetAnomaliesCube:
    """Mock GetAnomaliesCube that processes full_result from upstream."""
    cube_id = "get_anomalies"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        full_result = inputs.get("full_result", {})
        flight_ids = full_result.get("flight_ids", [])
        return {
            "flight_ids": flight_ids,
            "count": len(flight_ids),
            "anomalies": [{"flight": fid, "type": "altitude_deviation"} for fid in flight_ids],
        }


class MockAlisonFlightsCube:
    """Mock AlisonFlightsCube returning hex_list."""
    cube_id = "alison_flights"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        return {
            "hex_list": ["abc123", "def456", "789ghi"],
            "count": 3,
            "flights": [
                {"hex": "abc123", "flight": "AL001"},
                {"hex": "def456", "flight": "AL002"},
                {"hex": "789ghi", "flight": "AL003"},
            ],
        }


class MockSquawkFilterCube:
    """Mock SquawkFilterCube that filters by squawk code."""
    cube_id = "squawk_filter"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        full_result = inputs.get("full_result", {})
        hex_list = full_result.get("hex_list", inputs.get("hex_list", []))
        # Simulate: first 2 pass filter
        filtered = hex_list[:2]
        return {
            "hex_list": filtered,
            "count": len(filtered),
            "flights": [{"hex": h, "squawk": "7700"} for h in filtered],
        }


class MockDarkFlightDetectorCube:
    """Mock DarkFlightDetectorCube that detects dark flights."""
    cube_id = "dark_flight_detector"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        full_result = inputs.get("full_result", {})
        hex_list = full_result.get("hex_list", inputs.get("hex_list", []))
        return {
            "hex_list": hex_list,
            "count": len(hex_list),
            "dark_flights": [{"hex": h, "dark_duration_s": 3600} for h in hex_list],
        }


class MockSignalHealthAnalyzerCube:
    """Mock SignalHealthAnalyzerCube that analyzes signal health."""
    cube_id = "signal_health_analyzer"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        full_result = inputs.get("full_result", {})
        hex_list = inputs.get("hex_list") or []
        if not hex_list and full_result and isinstance(full_result, dict):
            hex_list = full_result.get("hex_list") or full_result.get("flight_ids") or []
        return {
            "flight_ids": hex_list,
            "count": len(hex_list),
            "events": [{"hex": h, "category": "gps_jamming"} for h in hex_list],
            "stats_summary": {"gps_jamming": len(hex_list)},
        }


# ============================================================
# Registry helper
# ============================================================


CUBE_MAP = {
    "all_flights": MockAllFlightsCube,
    "filter_flights": MockFilterFlightsCube,
    "get_anomalies": MockGetAnomaliesCube,
    "alison_flights": MockAlisonFlightsCube,
    "squawk_filter": MockSquawkFilterCube,
    "dark_flight_detector": MockDarkFlightDetectorCube,
    "signal_health_analyzer": MockSignalHealthAnalyzerCube,
}


def make_mock_registry():
    """Create a mock registry that returns mock cube instances."""
    mock_reg = MagicMock()
    mock_reg.get.side_effect = lambda cube_id: CUBE_MAP.get(cube_id, lambda: None)()
    return mock_reg


# ============================================================
# Pipeline 1: AllFlights -> FilterFlights -> GetAnomalies
# ============================================================


@pytest.mark.asyncio
async def test_fr_analysis_pipeline():
    """AllFlights -> FilterFlights -> GetAnomalies: data flows through full_result wiring."""
    from app.engine.executor import execute_graph

    graph = WorkflowGraph(
        nodes=[
            make_node("n1", "all_flights", params={"time_range": "1h"}),
            make_node("n2", "filter_flights"),
            make_node("n3", "get_anomalies"),
        ],
        edges=[
            make_edge("e1", "n1", "n2", source_handle="__full_result__", target_handle="full_result"),
            make_edge("e2", "n2", "n3", source_handle="__full_result__", target_handle="full_result"),
        ],
    )

    with patch("app.engine.executor.registry", make_mock_registry()):
        results = await execute_graph(graph)

    # All nodes should complete successfully
    assert results["n1"]["status"] == "done"
    assert results["n2"]["status"] == "done"
    assert results["n3"]["status"] == "done"

    # AllFlights returns 3 flights
    assert results["n1"]["outputs"]["count"] == 3
    assert len(results["n1"]["outputs"]["flight_ids"]) == 3

    # FilterFlights keeps first 2
    assert results["n2"]["outputs"]["count"] == 2
    assert len(results["n2"]["outputs"]["flight_ids"]) == 2

    # GetAnomalies processes the filtered 2
    assert results["n3"]["outputs"]["count"] == 2
    assert len(results["n3"]["outputs"]["anomalies"]) == 2


@pytest.mark.asyncio
async def test_fr_pipeline_data_integrity():
    """Verify specific flight IDs propagate correctly through the FR pipeline."""
    from app.engine.executor import execute_graph

    graph = WorkflowGraph(
        nodes=[
            make_node("src", "all_flights"),
            make_node("filter", "filter_flights"),
            make_node("anomaly", "get_anomalies"),
        ],
        edges=[
            make_edge("e1", "src", "filter", source_handle="__full_result__", target_handle="full_result"),
            make_edge("e2", "filter", "anomaly", source_handle="__full_result__", target_handle="full_result"),
        ],
    )

    with patch("app.engine.executor.registry", make_mock_registry()):
        results = await execute_graph(graph)

    # The filter keeps FL001 and FL002
    filtered_ids = results["filter"]["outputs"]["flight_ids"]
    assert filtered_ids == ["FL001", "FL002"]

    # Anomalies should reference the same filtered IDs
    anomaly_ids = results["anomaly"]["outputs"]["flight_ids"]
    assert anomaly_ids == ["FL001", "FL002"]


# ============================================================
# Pipeline 2: AlisonFlights -> SquawkFilter -> DarkFlightDetector
# ============================================================


@pytest.mark.asyncio
async def test_alison_filter_chain():
    """AlisonFlights -> SquawkFilter -> DarkFlightDetector: hex_list propagates through chain."""
    from app.engine.executor import execute_graph

    graph = WorkflowGraph(
        nodes=[
            make_node("alison", "alison_flights", params={"time_range": "1h"}),
            make_node("squawk", "squawk_filter"),
            make_node("dark", "dark_flight_detector"),
        ],
        edges=[
            make_edge("e1", "alison", "squawk", source_handle="__full_result__", target_handle="full_result"),
            make_edge("e2", "squawk", "dark", source_handle="__full_result__", target_handle="full_result"),
        ],
    )

    with patch("app.engine.executor.registry", make_mock_registry()):
        results = await execute_graph(graph)

    # All nodes complete
    assert results["alison"]["status"] == "done"
    assert results["squawk"]["status"] == "done"
    assert results["dark"]["status"] == "done"

    # Alison returns 3 hexes
    assert results["alison"]["outputs"]["count"] == 3
    assert len(results["alison"]["outputs"]["hex_list"]) == 3

    # Squawk filters to 2
    assert results["squawk"]["outputs"]["count"] == 2
    squawk_hexes = results["squawk"]["outputs"]["hex_list"]
    assert squawk_hexes == ["abc123", "def456"]

    # Dark detector processes the 2 filtered hexes
    assert results["dark"]["outputs"]["count"] == 2
    dark_hexes = results["dark"]["outputs"]["hex_list"]
    assert dark_hexes == ["abc123", "def456"]

    # Dark flight details present
    assert len(results["dark"]["outputs"]["dark_flights"]) == 2


@pytest.mark.asyncio
async def test_alison_chain_hex_integrity():
    """Verify hex codes propagate unchanged through Alison filter chain."""
    from app.engine.executor import execute_graph

    graph = WorkflowGraph(
        nodes=[
            make_node("src", "alison_flights"),
            make_node("flt", "squawk_filter"),
        ],
        edges=[
            make_edge("e1", "src", "flt", source_handle="__full_result__", target_handle="full_result"),
        ],
    )

    with patch("app.engine.executor.registry", make_mock_registry()):
        results = await execute_graph(graph)

    src_hexes = results["src"]["outputs"]["hex_list"]
    flt_hexes = results["flt"]["outputs"]["hex_list"]

    # Filtered hexes must be a subset of source hexes
    assert set(flt_hexes).issubset(set(src_hexes))


# ============================================================
# Pipeline 3: AlisonFlights -> SignalHealthAnalyzer
# ============================================================


@pytest.mark.asyncio
async def test_signal_analysis_pipeline():
    """AlisonFlights -> SignalHealthAnalyzer: hex_list flows via full_result."""
    from app.engine.executor import execute_graph

    graph = WorkflowGraph(
        nodes=[
            make_node("alison", "alison_flights", params={"time_range": "2h"}),
            make_node("signal", "signal_health_analyzer"),
        ],
        edges=[
            make_edge("e1", "alison", "signal", source_handle="__full_result__", target_handle="full_result"),
        ],
    )

    with patch("app.engine.executor.registry", make_mock_registry()):
        results = await execute_graph(graph)

    assert results["alison"]["status"] == "done"
    assert results["signal"]["status"] == "done"

    # Signal analyzer should receive all 3 hexes from AlisonFlights
    assert results["signal"]["outputs"]["count"] == 3
    assert sorted(results["signal"]["outputs"]["flight_ids"]) == sorted(["abc123", "def456", "789ghi"])

    # Events generated for each hex
    assert len(results["signal"]["outputs"]["events"]) == 3
    assert results["signal"]["outputs"]["stats_summary"] == {"gps_jamming": 3}


@pytest.mark.asyncio
async def test_signal_pipeline_direct_hex_list():
    """AlisonFlights -> SignalHealthAnalyzer with direct hex_list wiring."""
    from app.engine.executor import execute_graph

    graph = WorkflowGraph(
        nodes=[
            make_node("alison", "alison_flights"),
            make_node("signal", "signal_health_analyzer"),
        ],
        edges=[
            make_edge("e1", "alison", "signal", source_handle="hex_list", target_handle="hex_list"),
        ],
    )

    with patch("app.engine.executor.registry", make_mock_registry()):
        results = await execute_graph(graph)

    assert results["signal"]["status"] == "done"
    # Direct hex_list wiring should also work
    assert results["signal"]["outputs"]["count"] == 3


# ============================================================
# Edge cases
# ============================================================


@pytest.mark.asyncio
async def test_pipeline_with_failing_middle_node():
    """When middle node fails, downstream is skipped but upstream is done."""
    from app.engine.executor import execute_graph

    class MockFailCube:
        cube_id = "fail_cube"
        async def execute(self, **inputs):
            raise RuntimeError("Simulated failure")

    fail_map = {**CUBE_MAP, "fail_cube": MockFailCube}
    mock_reg = MagicMock()
    mock_reg.get.side_effect = lambda cid: fail_map.get(cid, lambda: None)()

    graph = WorkflowGraph(
        nodes=[
            make_node("src", "alison_flights"),
            make_node("mid", "fail_cube"),
            make_node("end", "dark_flight_detector"),
        ],
        edges=[
            make_edge("e1", "src", "mid", source_handle="__full_result__", target_handle="full_result"),
            make_edge("e2", "mid", "end", source_handle="__full_result__", target_handle="full_result"),
        ],
    )

    with patch("app.engine.executor.registry", mock_reg):
        results = await execute_graph(graph)

    assert results["src"]["status"] == "done"
    assert results["mid"]["status"] == "error"
    assert results["end"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_independent_pipelines_run_in_parallel():
    """Two independent pipelines both execute successfully."""
    from app.engine.executor import execute_graph

    graph = WorkflowGraph(
        nodes=[
            # Pipeline A
            make_node("a1", "all_flights"),
            make_node("a2", "get_anomalies"),
            # Pipeline B (independent)
            make_node("b1", "alison_flights"),
            make_node("b2", "signal_health_analyzer"),
        ],
        edges=[
            make_edge("e1", "a1", "a2", source_handle="__full_result__", target_handle="full_result"),
            make_edge("e2", "b1", "b2", source_handle="__full_result__", target_handle="full_result"),
        ],
    )

    with patch("app.engine.executor.registry", make_mock_registry()):
        results = await execute_graph(graph)

    # All 4 nodes complete
    for nid in ["a1", "a2", "b1", "b2"]:
        assert results[nid]["status"] == "done", f"Node {nid} status: {results[nid]['status']}"

    # Pipeline A processed 3 flights
    assert results["a2"]["outputs"]["count"] == 3
    # Pipeline B processed 3 hexes
    assert results["b2"]["outputs"]["count"] == 3
