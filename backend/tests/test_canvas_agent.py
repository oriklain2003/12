"""Tests for Canvas Agent tools (CANVAS-03, CANVAS-05, CANVAS-07)."""

import pytest
from app.agents.context import ToolContext
from app.agents.tools.canvas_tools import (
    read_workflow_graph,
    read_execution_errors,
    read_execution_results,
    propose_graph_diff,
)


def make_tool_context(**overrides) -> ToolContext:
    defaults = dict(db_session=None, cube_registry=None)
    defaults.update(overrides)
    return ToolContext(**defaults)


def make_workflow_graph():
    return {
        "nodes": [
            {"id": "n1", "type": "cube", "position": {"x": 0, "y": 0}, "data": {"cube_id": "all_flights", "params": {"limit": 100}}},
        ],
        "edges": [],
    }


def make_execution_errors():
    return {"n1": {"status": "error", "error": "Connection timeout"}}


def make_execution_results():
    return {
        "n1": {
            "rows": [
                {"icao24": "abc123", "callsign": "TEST01", "lat": 32.0},
                {"icao24": "def456", "callsign": "TEST02", "lat": 33.0},
                {"icao24": "ghi789", "callsign": "TEST03", "lat": 34.0},
                {"icao24": "jkl012", "callsign": "TEST04", "lat": 35.0},
            ],
            "truncated": True,
        }
    }


class TestCanvasTools:
    @pytest.mark.asyncio
    async def test_read_workflow_graph_returns_graph(self):
        ctx = make_tool_context(workflow_graph=make_workflow_graph())
        result = await read_workflow_graph(ctx)
        assert "workflow_graph" in result
        assert result["workflow_graph"]["nodes"][0]["data"]["cube_id"] == "all_flights"

    @pytest.mark.asyncio
    async def test_read_workflow_graph_returns_error_when_none(self):
        ctx = make_tool_context()
        result = await read_workflow_graph(ctx)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_read_execution_errors_returns_errors(self):
        ctx = make_tool_context(execution_errors=make_execution_errors())
        result = await read_execution_errors(ctx)
        assert "execution_errors" in result
        assert result["execution_errors"]["n1"]["error"] == "Connection timeout"

    @pytest.mark.asyncio
    async def test_read_execution_errors_returns_error_when_none(self):
        ctx = make_tool_context()
        result = await read_execution_errors(ctx)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_read_execution_results_summarizes(self):
        ctx = make_tool_context(execution_results=make_execution_results())
        result = await read_execution_results(ctx)
        assert "execution_results" in result
        n1 = result["execution_results"]["n1"]
        assert n1["row_count"] == 4
        assert len(n1["sample_rows"]) == 3  # capped at 3
        assert "icao24" in n1["columns"]
        assert n1["truncated"] is True

    @pytest.mark.asyncio
    async def test_read_execution_results_returns_error_when_none(self):
        ctx = make_tool_context()
        result = await read_execution_results(ctx)
        assert "error" in result


class TestCanvasDiff:
    @pytest.mark.asyncio
    async def test_propose_graph_diff_returns_diff(self):
        ctx = make_tool_context()
        result = await propose_graph_diff(
            ctx,
            summary="Add a filter cube",
            add_nodes=[{"cube_id": "squawk_filter", "position_x": 200, "position_y": 100}],
        )
        assert "proposed_diff" in result
        assert result["proposed_diff"]["summary"] == "Add a filter cube"
        # position_x/y should be restructured to position.x/y
        added = result["proposed_diff"]["add_nodes"][0]
        assert added["position"]["x"] == 200
        assert added["position"]["y"] == 100

    @pytest.mark.asyncio
    async def test_propose_graph_diff_schema_is_flat(self):
        from app.agents.registry import get_all_tools
        tools = get_all_tools()
        assert "propose_graph_diff" in tools
        schema = tools["propose_graph_diff"].parameters_schema
        schema_str = str(schema)
        assert "$defs" not in schema_str
        assert "$ref" not in schema_str
