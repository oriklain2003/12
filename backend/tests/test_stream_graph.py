"""Tests for stream_graph async generator.

Tests cover:
- All nodes emit "pending" events before any "running" event
- Single successful cube: running then done with outputs
- Failing cube: running then error with message
- Downstream of failed cube: skipped
- Events in topological order
- Done events include row-limited outputs and truncated flag
- execute_graph backward compatibility (same dict format)
"""

import pytest
from typing import Any
from unittest.mock import patch, MagicMock

from app.schemas.workflow import (
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeData,
    Position,
)
from app.schemas.execution import CubeStatusEvent


# ============================================================
# Helpers (duplicated from test_executor.py to avoid cross-test imports)
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


class MockEchoCube:
    """A minimal mock cube for testing stream_graph."""

    cube_id = "mock_echo"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        return {"result": inputs.get("value", "")}


class MockFailingCube:
    """A mock cube that always raises an exception."""

    cube_id = "mock_fail"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        raise RuntimeError("Intentional failure")


# ============================================================
# Test 1: All pending events emitted before any running event
# ============================================================


@pytest.mark.asyncio
async def test_stream_graph_all_pending_before_running():
    """Test 1: stream_graph yields 'pending' events for ALL nodes before any 'running' event."""
    from app.engine.executor import stream_graph

    mock_registry = MagicMock()
    mock_registry.get.side_effect = lambda cube_id: MockEchoCube()

    graph = WorkflowGraph(
        nodes=[
            make_node("n1", "mock_echo", params={"value": "a"}),
            make_node("n2", "mock_echo"),
            make_node("n3", "mock_echo"),
        ],
        edges=[
            make_edge("e1", "n1", "n2", source_handle="result", target_handle="value"),
            make_edge("e2", "n2", "n3", source_handle="result", target_handle="value"),
        ],
    )

    with patch("app.engine.executor.registry", mock_registry):
        events = [event async for event in stream_graph(graph)]

    # First 3 events must all be "pending"
    statuses = [e.status for e in events]
    first_running_idx = next(i for i, s in enumerate(statuses) if s == "running")
    pending_indices = [i for i, s in enumerate(statuses) if s == "pending"]

    # All pending events must come before the first running event
    assert all(i < first_running_idx for i in pending_indices), (
        f"Expected all pending before running. Statuses: {statuses}"
    )
    # There should be exactly 3 pending events (one per node)
    assert len(pending_indices) == 3


# ============================================================
# Test 2: Single successful node emits running then done
# ============================================================


@pytest.mark.asyncio
async def test_stream_graph_single_success():
    """Test 2: stream_graph yields 'running' then 'done' with outputs for a successful single-node graph."""
    from app.engine.executor import stream_graph

    mock_registry = MagicMock()
    mock_registry.get.side_effect = lambda cube_id: MockEchoCube()

    graph = WorkflowGraph(
        nodes=[make_node("n1", "mock_echo", params={"value": "hello"})],
        edges=[],
    )

    with patch("app.engine.executor.registry", mock_registry):
        events = [event async for event in stream_graph(graph)]

    statuses = [e.status for e in events]
    assert statuses == ["pending", "running", "done"]

    done_event = events[2]
    assert done_event.node_id == "n1"
    assert done_event.outputs == {"result": "hello"}
    assert done_event.truncated is False


# ============================================================
# Test 3: Failing cube emits running then error
# ============================================================


@pytest.mark.asyncio
async def test_stream_graph_failure():
    """Test 3: stream_graph yields 'running' then 'error' with message for a cube that raises."""
    from app.engine.executor import stream_graph

    mock_registry = MagicMock()
    mock_registry.get.return_value = MockFailingCube()

    graph = WorkflowGraph(
        nodes=[make_node("n1", "mock_fail")],
        edges=[],
    )

    with patch("app.engine.executor.registry", mock_registry):
        events = [event async for event in stream_graph(graph)]

    statuses = [e.status for e in events]
    assert statuses == ["pending", "running", "error"]

    error_event = events[2]
    assert error_event.node_id == "n1"
    assert "Intentional failure" in error_event.error


# ============================================================
# Test 4: Downstream of failed cube emits skipped
# ============================================================


@pytest.mark.asyncio
async def test_stream_graph_skip_downstream():
    """Test 4: stream_graph yields 'skipped' for nodes downstream of a failed cube."""
    from app.engine.executor import stream_graph

    def get_cube(cube_id: str):
        if cube_id == "mock_fail":
            return MockFailingCube()
        return MockEchoCube()

    mock_registry = MagicMock()
    mock_registry.get.side_effect = get_cube

    graph = WorkflowGraph(
        nodes=[
            make_node("n1", "mock_fail"),
            make_node("n2", "mock_echo"),  # depends on n1
        ],
        edges=[
            make_edge("e1", "n1", "n2"),
        ],
    )

    with patch("app.engine.executor.registry", mock_registry):
        events = [event async for event in stream_graph(graph)]

    by_node: dict[str, list[CubeStatusEvent]] = {}
    for e in events:
        by_node.setdefault(e.node_id, []).append(e)

    n1_statuses = [e.status for e in by_node["n1"]]
    n2_statuses = [e.status for e in by_node["n2"]]

    assert "error" in n1_statuses
    assert "skipped" in n2_statuses


# ============================================================
# Test 5: Events in topological order (A before B in A->B chain)
# ============================================================


@pytest.mark.asyncio
async def test_stream_graph_topological_order():
    """Test 5: stream_graph yields events in topological order (A before B when A->B)."""
    from app.engine.executor import stream_graph

    mock_registry = MagicMock()
    mock_registry.get.side_effect = lambda cube_id: MockEchoCube()

    graph = WorkflowGraph(
        nodes=[
            make_node("n1", "mock_echo", params={"value": "first"}),
            make_node("n2", "mock_echo"),
        ],
        edges=[
            make_edge("e1", "n1", "n2", source_handle="result", target_handle="value"),
        ],
    )

    with patch("app.engine.executor.registry", mock_registry):
        events = [event async for event in stream_graph(graph)]

    # Find the "done" events to check ordering
    done_events = [e for e in events if e.status == "done"]
    node_ids_in_order = [e.node_id for e in done_events]

    # n1 must come before n2 in done events
    assert node_ids_in_order.index("n1") < node_ids_in_order.index("n2")

    # n2 should get the chained value from n1
    n2_done = next(e for e in done_events if e.node_id == "n2")
    assert n2_done.outputs == {"result": "first"}


# ============================================================
# Test 6: Done events include row-limited outputs and truncated flag
# ============================================================


class MockLargeOutputCube:
    """A mock cube that returns a large list."""

    cube_id = "mock_large"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        return {"rows": list(range(200)), "name": "big"}


@pytest.mark.asyncio
async def test_stream_graph_row_limiting():
    """Test 6: 'done' events include row-limited outputs and truncated=True flag."""
    from app.engine.executor import stream_graph

    mock_registry = MagicMock()
    mock_registry.get.return_value = MockLargeOutputCube()

    graph = WorkflowGraph(
        nodes=[make_node("n1", "mock_large")],
        edges=[],
    )

    with patch("app.engine.executor.registry", mock_registry):
        events = [event async for event in stream_graph(graph)]

    done_event = next(e for e in events if e.status == "done")
    assert done_event.truncated is True
    assert len(done_event.outputs["rows"]) == 100  # default limit


# ============================================================
# Test 7: execute_graph backward compatibility
# ============================================================


@pytest.mark.asyncio
async def test_execute_graph_backward_compat():
    """Test 7: execute_graph still returns the same dict[str, Any] result format."""
    from app.engine.executor import execute_graph

    mock_registry = MagicMock()

    def get_cube(cube_id: str):
        if cube_id == "mock_fail":
            return MockFailingCube()
        return MockEchoCube()

    mock_registry.get.side_effect = get_cube

    graph = WorkflowGraph(
        nodes=[
            make_node("n1", "mock_echo", params={"value": "hello"}),
            make_node("n2", "mock_fail"),
            make_node("n3", "mock_echo"),  # depends on n2 (will be skipped)
        ],
        edges=[
            make_edge("e1", "n1", "n2", source_handle="result", target_handle="value"),
            make_edge("e2", "n2", "n3"),
        ],
    )

    with patch("app.engine.executor.registry", mock_registry):
        results = await execute_graph(graph)

    # n1 done
    assert results["n1"]["status"] == "done"
    assert results["n1"]["outputs"]["result"] == "hello"
    # n2 error
    assert results["n2"]["status"] == "error"
    assert "message" in results["n2"]
    # n3 skipped
    assert results["n3"]["status"] == "skipped"
    assert "reason" in results["n3"]
