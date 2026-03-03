"""Integration tests for the GET /api/workflows/{id}/run/stream SSE endpoint.

Tests cover:
- SSE events have event type "cube_status" and JSON data with node_id + status
- Stream starts with "pending" events for all nodes, then running/done
- Cycle graph returns HTTP 400 (not SSE 200 with error)
- Nonexistent workflow returns HTTP 404
- SSE response includes correct Content-Type (text/event-stream)
"""

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.database import get_db
from app.main import app
from app.schemas.workflow import (
    Position,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeData,
)


# ============================================================
# Helpers
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
    """A minimal mock cube for testing the SSE endpoint."""

    cube_id = "mock_echo"

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        return {"result": inputs.get("value", "")}


def make_mock_db(workflow_obj):
    """Create a mock DB dependency that returns the given workflow object."""

    async def mock_get_db():
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = workflow_obj
        session.execute = AsyncMock(return_value=result)
        yield session

    return mock_get_db


def make_workflow_obj(graph: WorkflowGraph):
    """Create a mock Workflow ORM object with a given graph."""
    wf = MagicMock()
    wf.id = uuid.uuid4()
    wf.name = "Test Workflow"
    wf.graph_json = graph.model_dump()
    return wf


def parse_sse_events(content: bytes) -> list[dict]:
    """Parse SSE response bytes into a list of dicts with 'event' and 'data' keys."""
    events = []
    current_event: dict[str, str] = {}

    for line in content.decode().splitlines():
        if line.startswith("event:"):
            current_event["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current_event["data"] = line[len("data:"):].strip()
        elif line == "" and current_event:
            events.append(current_event.copy())
            current_event = {}

    return events


# ============================================================
# Test 1: SSE events have event type "cube_status" and JSON data
# ============================================================


@pytest.mark.asyncio
async def test_sse_events_have_cube_status_type():
    """Test 1: SSE events have event type 'cube_status' and JSON data with node_id + status."""
    graph = WorkflowGraph(
        nodes=[make_node("n1", "mock_echo", params={"value": "hello"})],
        edges=[],
    )
    wf = make_workflow_obj(graph)

    mock_registry = MagicMock()
    mock_registry.get.return_value = MockEchoCube()

    app.dependency_overrides[get_db] = make_mock_db(wf)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("app.engine.executor.registry", mock_registry):
                response = await client.get(
                    f"/api/workflows/{wf.id}/run/stream",
                    headers={"Accept": "text/event-stream"},
                )

        assert response.status_code == 200
        events = parse_sse_events(response.content)
        assert len(events) > 0

        for event in events:
            assert event.get("event") == "cube_status", (
                f"Expected event type 'cube_status', got '{event.get('event')}'"
            )
            data = json.loads(event["data"])
            assert "node_id" in data
            assert "status" in data
    finally:
        app.dependency_overrides.pop(get_db, None)


# ============================================================
# Test 2: Stream starts with pending events, then running/done
# ============================================================


@pytest.mark.asyncio
async def test_sse_stream_pending_before_running():
    """Test 2: SSE stream starts with 'pending' events for all nodes, then running/done."""
    graph = WorkflowGraph(
        nodes=[
            make_node("n1", "mock_echo", params={"value": "a"}),
            make_node("n2", "mock_echo"),
        ],
        edges=[
            make_edge("e1", "n1", "n2", source_handle="result", target_handle="value"),
        ],
    )
    wf = make_workflow_obj(graph)

    mock_registry = MagicMock()
    mock_registry.get.return_value = MockEchoCube()

    app.dependency_overrides[get_db] = make_mock_db(wf)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("app.engine.executor.registry", mock_registry):
                response = await client.get(
                    f"/api/workflows/{wf.id}/run/stream",
                    headers={"Accept": "text/event-stream"},
                )

        events = parse_sse_events(response.content)
        statuses = [json.loads(e["data"])["status"] for e in events]

        # Find first non-pending event
        first_running_idx = next(
            (i for i, s in enumerate(statuses) if s != "pending"), None
        )
        assert first_running_idx is not None, "Expected non-pending events"

        # All events before first_running_idx must be pending
        pending_statuses = statuses[:first_running_idx]
        assert all(s == "pending" for s in pending_statuses), (
            f"Expected all pending before running. Statuses: {statuses}"
        )
        # Two nodes → two pending events
        assert len(pending_statuses) == 2

        # There should be running and done events after the pending events
        non_pending = statuses[first_running_idx:]
        assert "running" in non_pending
        assert "done" in non_pending
    finally:
        app.dependency_overrides.pop(get_db, None)


# ============================================================
# Test 3: Cycle graph returns HTTP 400 (not SSE)
# ============================================================


@pytest.mark.asyncio
async def test_sse_cycle_returns_400():
    """Test 3: Cycle graph returns HTTP 400 before SSE stream starts."""
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
    wf = make_workflow_obj(graph)

    app.dependency_overrides[get_db] = make_mock_db(wf)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/workflows/{wf.id}/run/stream",
                headers={"Accept": "text/event-stream"},
            )

        assert response.status_code == 400
    finally:
        app.dependency_overrides.pop(get_db, None)


# ============================================================
# Test 4: Nonexistent workflow returns HTTP 404
# ============================================================


@pytest.mark.asyncio
async def test_sse_nonexistent_workflow_returns_404():
    """Test 4: Nonexistent workflow returns HTTP 404."""

    async def mock_get_db_none():
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)
        yield session

    app.dependency_overrides[get_db] = mock_get_db_none
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/workflows/{uuid.uuid4()}/run/stream",
                headers={"Accept": "text/event-stream"},
            )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


# ============================================================
# Test 5: SSE response Content-Type is text/event-stream
# ============================================================


@pytest.mark.asyncio
async def test_sse_content_type():
    """Test 5: SSE response includes correct Content-Type (text/event-stream)."""
    graph = WorkflowGraph(
        nodes=[make_node("n1", "mock_echo", params={"value": "hi"})],
        edges=[],
    )
    wf = make_workflow_obj(graph)

    mock_registry = MagicMock()
    mock_registry.get.return_value = MockEchoCube()

    app.dependency_overrides[get_db] = make_mock_db(wf)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("app.engine.executor.registry", mock_registry):
                response = await client.get(
                    f"/api/workflows/{wf.id}/run/stream",
                    headers={"Accept": "text/event-stream"},
                )

        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "text/event-stream" in content_type, (
            f"Expected text/event-stream, got: {content_type}"
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
