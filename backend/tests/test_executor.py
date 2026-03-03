"""Tests for the WorkflowExecutor engine.

Tests cover:
- topological_sort: linear, cycle, parallel branches
- resolve_inputs: manual params, connection override, full result
- apply_row_limit: list capping, unchanged for non-lists
- execute_graph: chained execution, cycle 400, skip on failure, independent branch isolation
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock
from typing import Any

from app.schemas.workflow import (
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeData,
    Position,
)


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
# Test topological_sort
# ============================================================


def test_topological_sort_linear():
    """Test 1: topological_sort returns correct order for linear graph A->B->C."""
    from app.engine.executor import topological_sort

    nodes = [make_node("A", "echo"), make_node("B", "echo"), make_node("C", "echo")]
    edges = [
        make_edge("e1", "A", "B"),
        make_edge("e2", "B", "C"),
    ]
    order = topological_sort(nodes, edges)
    assert order == ["A", "B", "C"]


def test_topological_sort_cycle():
    """Test 2: topological_sort raises ValueError for graph with cycle A->B->A."""
    from app.engine.executor import topological_sort

    nodes = [make_node("A", "echo"), make_node("B", "echo")]
    edges = [
        make_edge("e1", "A", "B"),
        make_edge("e2", "B", "A"),
    ]
    with pytest.raises(ValueError, match="cycle"):
        topological_sort(nodes, edges)


def test_topological_sort_parallel_branches():
    """Test 3: topological_sort handles parallel branches (A->C, B->C returns A,B,C or B,A,C)."""
    from app.engine.executor import topological_sort

    nodes = [make_node("A", "echo"), make_node("B", "echo"), make_node("C", "echo")]
    edges = [
        make_edge("e1", "A", "C"),
        make_edge("e2", "B", "C"),
    ]
    order = topological_sort(nodes, edges)
    # A and B can be in any order, but C must be last
    assert set(order) == {"A", "B", "C"}
    assert order.index("C") > order.index("A")
    assert order.index("C") > order.index("B")


# ============================================================
# Test resolve_inputs
# ============================================================


def test_resolve_inputs_merges_manual_and_connections():
    """Test 4: resolve_inputs merges manual params with connection values; connections override manual."""
    from app.engine.executor import resolve_inputs

    node = make_node("B", "echo", params={"value": "manual_value"})
    edges = [
        make_edge("e1", "A", "B", source_handle="result", target_handle="value"),
    ]
    results = {
        "A": {"status": "done", "outputs": {"result": "connected_value"}},
    }
    inputs = resolve_inputs(node, edges, results)
    # Connection should override manual value
    assert inputs["value"] == "connected_value"


def test_resolve_inputs_full_result():
    """Test 5: resolve_inputs handles __full_result__ sourceHandle by bundling all source outputs."""
    from app.engine.executor import resolve_inputs

    node = make_node("B", "some_cube", params={})
    edges = [
        make_edge("e1", "A", "B", source_handle="__full_result__", target_handle="data"),
    ]
    results = {
        "A": {"status": "done", "outputs": {"x": 1, "y": 2, "z": "hello"}},
    }
    inputs = resolve_inputs(node, edges, results)
    # Full result bundles all outputs into a dict
    assert inputs["data"] == {"x": 1, "y": 2, "z": "hello"}


# ============================================================
# Test apply_row_limit
# ============================================================


def test_apply_row_limit_caps_list():
    """Test 6: apply_row_limit caps list outputs at limit and sets truncated=True."""
    from app.engine.executor import apply_row_limit

    outputs = {"rows": list(range(200)), "name": "test"}
    capped, truncated = apply_row_limit(outputs, limit=100)
    assert len(capped["rows"]) == 100
    assert capped["rows"] == list(range(100))
    assert capped["name"] == "test"
    assert truncated is True


def test_apply_row_limit_unchanged():
    """Test 7: apply_row_limit leaves non-list and short-list outputs unchanged, truncated=False."""
    from app.engine.executor import apply_row_limit

    outputs = {"count": 42, "items": [1, 2, 3], "label": "hello"}
    capped, truncated = apply_row_limit(outputs, limit=100)
    assert capped["count"] == 42
    assert capped["items"] == [1, 2, 3]
    assert capped["label"] == "hello"
    assert truncated is False


# ============================================================
# Test execute_graph
# ============================================================


class MockEchoCube:
    """A minimal mock cube for testing execute_graph."""

    cube_id = "mock_echo"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        return {"result": inputs.get("value", "")}


class MockFailingCube:
    """A mock cube that always raises an exception."""

    cube_id = "mock_fail"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        raise RuntimeError("Intentional failure")


@pytest.mark.asyncio
async def test_execute_graph_echo_chain():
    """Test 8: execute_graph runs a simple echo->echo chain and returns correct chained results."""
    from app.engine.executor import execute_graph

    mock_registry = MagicMock()
    mock_registry.get.side_effect = lambda cube_id: (
        MockEchoCube() if cube_id == "mock_echo" else None
    )

    graph = WorkflowGraph(
        nodes=[
            make_node("n1", "mock_echo", params={"value": "hello"}),
            make_node("n2", "mock_echo", params={}),
        ],
        edges=[
            make_edge("e1", "n1", "n2", source_handle="result", target_handle="value"),
        ],
    )

    with patch("app.engine.executor.registry", mock_registry):
        results = await execute_graph(graph)

    assert results["n1"]["status"] == "done"
    assert results["n1"]["outputs"]["result"] == "hello"
    assert results["n2"]["status"] == "done"
    assert results["n2"]["outputs"]["result"] == "hello"


@pytest.mark.asyncio
async def test_execute_graph_cycle_returns_400():
    """Test 9: execute_graph returns 400-style error on cycle."""
    from app.engine.executor import execute_graph
    from fastapi import HTTPException

    graph = WorkflowGraph(
        nodes=[
            make_node("a", "mock_echo"),
            make_node("b", "mock_echo"),
        ],
        edges=[
            make_edge("e1", "a", "b"),
            make_edge("e2", "b", "a"),
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        await execute_graph(graph)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_execute_graph_skips_dependents_on_failure():
    """Test 10: execute_graph marks dependents as 'skipped' when upstream cube fails."""
    from app.engine.executor import execute_graph

    mock_registry = MagicMock()

    def get_cube(cube_id: str):
        if cube_id == "mock_fail":
            return MockFailingCube()
        if cube_id == "mock_echo":
            return MockEchoCube()
        return None

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
        results = await execute_graph(graph)

    assert results["n1"]["status"] == "error"
    assert results["n2"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_execute_graph_independent_branch_continues():
    """Test 11: execute_graph continues independent branches when one branch fails."""
    from app.engine.executor import execute_graph

    mock_registry = MagicMock()

    def get_cube(cube_id: str):
        if cube_id == "mock_fail":
            return MockFailingCube()
        if cube_id == "mock_echo":
            return MockEchoCube()
        return None

    mock_registry.get.side_effect = get_cube

    graph = WorkflowGraph(
        nodes=[
            make_node("fail_node", "mock_fail"),
            make_node("dependent", "mock_echo"),       # depends on fail_node
            make_node("independent", "mock_echo", params={"value": "ok"}),  # independent
        ],
        edges=[
            make_edge("e1", "fail_node", "dependent"),
        ],
    )

    with patch("app.engine.executor.registry", mock_registry):
        results = await execute_graph(graph)

    assert results["fail_node"]["status"] == "error"
    assert results["dependent"]["status"] == "skipped"
    assert results["independent"]["status"] == "done"
    assert results["independent"]["outputs"]["result"] == "ok"
