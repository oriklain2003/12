"""Tests for find_cubes_for_task tool and CubeExpert sub-agent.

Phase 19 Plan 02 — Cube Expert implementation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.context import ToolContext


# ---------------------------------------------------------------------------
# Helpers — mock registry with known cubes
# ---------------------------------------------------------------------------

def _make_cube_def(cube_id: str, name: str, description: str, category: str = "filter"):
    """Create a minimal mock CubeDefinition with the fields used by find_cubes_for_task."""
    defn = MagicMock()
    defn.cube_id = cube_id
    defn.name = name
    defn.description = description
    # Simulate enum .value
    cat_mock = MagicMock()
    cat_mock.value = category
    defn.category = cat_mock
    return defn


MOCK_CUBES = [
    _make_cube_def(
        "area_spatial_filter",
        "Area Spatial Filter",
        "Filter flights by geographic area using polygon or bounding box",
        "filter",
    ),
    _make_cube_def(
        "all_flights",
        "All Flights",
        "Load all flights from the database with optional time range",
        "data_source",
    ),
    _make_cube_def(
        "squawk_filter",
        "Squawk Filter",
        "Filter flights by transponder squawk code",
        "filter",
    ),
    _make_cube_def(
        "count_by_field",
        "Count By Field",
        "Aggregate and count flights grouped by a field",
        "aggregation",
    ),
]


def _make_mock_registry(cubes=None):
    """Build a mock CubeRegistry returning the given cube definitions."""
    reg = MagicMock()
    reg.catalog.return_value = cubes if cubes is not None else MOCK_CUBES
    return reg


def _make_ctx(registry=None):
    """Build a ToolContext with optional mock registry."""
    return ToolContext(
        db_session=None,
        cube_registry=registry if registry is not None else _make_mock_registry(),
    )


# ---------------------------------------------------------------------------
# TestFindCubes
# ---------------------------------------------------------------------------

class TestFindCubes:
    """Tests for find_cubes_for_task tool."""

    @pytest.mark.asyncio
    async def test_find_cubes_keyword_match(self):
        """Query matching area_spatial_filter returns it in results with score > 0."""
        from app.agents.tools.catalog_tools import find_cubes_for_task

        ctx = _make_ctx()
        result = await find_cubes_for_task(ctx, query="filter flights geographic area")

        assert "results" in result
        cube_ids = [r["cube_id"] for r in result["results"]]
        assert "area_spatial_filter" in cube_ids
        # Score must be > 0 for matched cube
        matched = next(r for r in result["results"] if r["cube_id"] == "area_spatial_filter")
        assert matched["score"] > 0

    @pytest.mark.asyncio
    async def test_find_cubes_no_match(self):
        """Query with no matching keywords returns empty results list."""
        from app.agents.tools.catalog_tools import find_cubes_for_task

        ctx = _make_ctx()
        result = await find_cubes_for_task(ctx, query="xyznonexistent")

        assert "results" in result
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_find_cubes_limit(self):
        """Limit parameter caps the returned results."""
        from app.agents.tools.catalog_tools import find_cubes_for_task

        # Use a query that matches multiple cubes (e.g. "filter" matches area_spatial_filter and squawk_filter)
        ctx = _make_ctx()
        result = await find_cubes_for_task(ctx, query="filter flights", limit=1)

        assert "results" in result
        assert len(result["results"]) <= 1

    @pytest.mark.asyncio
    async def test_find_cubes_ranked(self):
        """Results are sorted by score descending."""
        from app.agents.tools.catalog_tools import find_cubes_for_task

        ctx = _make_ctx()
        result = await find_cubes_for_task(ctx, query="filter flights geographic area squawk")

        assert "results" in result
        scores = [r["score"] for r in result["results"]]
        assert scores == sorted(scores, reverse=True), "Results should be sorted by score desc"

    @pytest.mark.asyncio
    async def test_find_cubes_no_registry(self):
        """Returns error dict when cube_registry is None."""
        from app.agents.tools.catalog_tools import find_cubes_for_task

        ctx = ToolContext(db_session=None, cube_registry=None)
        result = await find_cubes_for_task(ctx, query="filter flights")

        assert "error" in result
        assert result["error"] == "Cube registry not available"


# ---------------------------------------------------------------------------
# TestCubeExpert
# ---------------------------------------------------------------------------

class TestCubeExpert:
    """Tests for CubeExpert sub-agent (mocked Gemini calls)."""

    def _make_text_response(self, text: str):
        """Build a mock Gemini response with text only (no function calls)."""
        response = MagicMock()
        response.text = text
        part = MagicMock()
        part.function_call = None
        candidate = MagicMock()
        candidate.content.parts = [part]
        response.candidates = [candidate]
        return response

    def _make_tool_call_response(self, fn_name: str, fn_args: dict):
        """Build a mock Gemini response with a function call."""
        response = MagicMock()
        response.text = None
        fc = MagicMock()
        fc.name = fn_name
        fc.args = fn_args
        part = MagicMock()
        part.function_call = fc
        candidate = MagicMock()
        candidate.content.parts = [part]
        response.candidates = [candidate]
        return response

    @pytest.mark.asyncio
    async def test_ask_text_response(self):
        """Gemini returns text only -> CubeExpert.ask() returns that text."""
        from app.agents.cube_expert import CubeExpert

        mock_response = self._make_text_response("Use area_spatial_filter")
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with (
            patch("app.agents.cube_expert.get_gemini_client", return_value=mock_client),
            patch("app.agents.cube_expert.get_system_prompt", return_value="You are expert"),
            patch("app.agents.cube_expert.get_gemini_tool_declarations", return_value=[]),
        ):
            expert = CubeExpert()
            result = await expert.ask("filter flights by area", _make_ctx())

        assert result == "Use area_spatial_filter"

    @pytest.mark.asyncio
    async def test_ask_with_tool_call(self):
        """Gemini first returns function_call, then text -> dispatches tool and returns final text."""
        from app.agents.cube_expert import CubeExpert

        tool_call_response = self._make_tool_call_response(
            "list_cubes_summary", {}
        )
        text_response = self._make_text_response("Use all_flights cube")

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[tool_call_response, text_response]
        )

        with (
            patch("app.agents.cube_expert.get_gemini_client", return_value=mock_client),
            patch("app.agents.cube_expert.get_system_prompt", return_value="You are expert"),
            patch("app.agents.cube_expert.get_gemini_tool_declarations", return_value=[]),
            patch(
                "app.agents.cube_expert.dispatch_tool",
                new_callable=AsyncMock,
                return_value={"categories": {}},
            ) as mock_dispatch,
        ):
            expert = CubeExpert()
            result = await expert.ask("load all flight data", _make_ctx())

        mock_dispatch.assert_called_once_with("list_cubes_summary", {}, pytest.ANY)
        assert result == "Use all_flights cube"

    @pytest.mark.asyncio
    async def test_ask_empty_response(self):
        """Gemini returns empty response -> CubeExpert.ask() returns empty string."""
        from app.agents.cube_expert import CubeExpert

        mock_response = MagicMock()
        mock_response.text = None
        mock_response.candidates = []

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with (
            patch("app.agents.cube_expert.get_gemini_client", return_value=mock_client),
            patch("app.agents.cube_expert.get_system_prompt", return_value=""),
            patch("app.agents.cube_expert.get_gemini_tool_declarations", return_value=[]),
        ):
            expert = CubeExpert()
            result = await expert.ask("anything", _make_ctx())

        assert result == ""

    @pytest.mark.asyncio
    async def test_ask_uses_flash_model(self):
        """Gemini call uses settings.gemini_flash_model."""
        from app.agents.cube_expert import CubeExpert

        mock_response = self._make_text_response("ok")
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with (
            patch("app.agents.cube_expert.get_gemini_client", return_value=mock_client),
            patch("app.agents.cube_expert.get_system_prompt", return_value=""),
            patch("app.agents.cube_expert.get_gemini_tool_declarations", return_value=[]),
            patch("app.agents.cube_expert.settings") as mock_settings,
        ):
            mock_settings.gemini_flash_model = "gemini-2.5-flash"
            expert = CubeExpert()
            await expert.ask("task", _make_ctx())

        call_kwargs = mock_client.aio.models.generate_content.call_args
        assert call_kwargs.kwargs.get("model") == "gemini-2.5-flash" or \
               call_kwargs.args[0] if call_kwargs.args else False or \
               "gemini-2.5-flash" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_ask_uses_cube_expert_persona(self):
        """get_system_prompt is called with 'cube_expert'."""
        from app.agents.cube_expert import CubeExpert

        mock_response = self._make_text_response("ok")
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with (
            patch("app.agents.cube_expert.get_gemini_client", return_value=mock_client),
            patch("app.agents.cube_expert.get_system_prompt", return_value="persona_text") as mock_prompt,
            patch("app.agents.cube_expert.get_gemini_tool_declarations", return_value=[]),
        ):
            expert = CubeExpert()
            await expert.ask("task", _make_ctx())

        mock_prompt.assert_called_once_with("cube_expert")

    @pytest.mark.asyncio
    async def test_ask_receives_task_only(self):
        """History passed to Gemini contains only the task string as a single user message (per D-13)."""
        from app.agents.cube_expert import CubeExpert

        mock_response = self._make_text_response("ok")
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        captured_contents = []

        async def capture_generate_content(**kwargs):
            captured_contents.append(kwargs.get("contents", []))
            return mock_response

        mock_client.aio.models.generate_content = capture_generate_content

        task_text = "filter flights by squawk 7700"

        with (
            patch("app.agents.cube_expert.get_gemini_client", return_value=mock_client),
            patch("app.agents.cube_expert.get_system_prompt", return_value=""),
            patch("app.agents.cube_expert.get_gemini_tool_declarations", return_value=[]),
        ):
            expert = CubeExpert()
            await expert.ask(task_text, _make_ctx())

        # Should have been called once with exactly one Content entry
        assert len(captured_contents) == 1
        contents = captured_contents[0]
        assert len(contents) == 1
        first_content = contents[0]
        assert first_content.role == "user"
        # The part's text should be the task string
        assert any(
            hasattr(p, "text") and p.text == task_text
            for p in first_content.parts
        )
