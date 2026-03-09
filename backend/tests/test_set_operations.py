"""Tests for SetOperationsCube — pure Python set math on LIST_OF_STRINGS.

Tests cover:
- Cube metadata (id, category, input/output names)
- Intersection of two sets
- Union of two sets
- Difference (A - B)
- Three-way intersection
- Empty input handling
- Unknown operation raises ValueError
"""

import pytest

from app.cubes.set_operations import SetOperationsCube
from app.schemas.cube import CubeCategory, ParamType


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """SetOperationsCube has correct cube_id, name, and category."""
    cube = SetOperationsCube()
    assert cube.cube_id == "set_operations"
    assert cube.name == "Set Operations"
    assert cube.category == CubeCategory.FILTER


def test_cube_inputs():
    """SetOperationsCube has the required inputs."""
    cube = SetOperationsCube()
    input_map = {p.name: p for p in cube.inputs}
    assert "set_a" in input_map
    assert "set_b" in input_map
    assert "set_c" in input_map
    assert "operation" in input_map

    assert input_map["set_a"].type == ParamType.LIST_OF_STRINGS
    assert input_map["set_a"].required is True
    assert input_map["set_b"].type == ParamType.LIST_OF_STRINGS
    assert input_map["set_b"].required is True
    assert input_map["set_c"].type == ParamType.LIST_OF_STRINGS
    assert input_map["set_c"].required is False
    assert input_map["operation"].type == ParamType.STRING
    assert input_map["operation"].default == "intersection"
    assert input_map["operation"].widget_hint == "select"


def test_cube_outputs():
    """SetOperationsCube has the required outputs."""
    cube = SetOperationsCube()
    output_names = {p.name for p in cube.outputs}
    assert "result" in output_names
    assert "count" in output_names


# ============================================================
# Intersection
# ============================================================


@pytest.mark.asyncio
async def test_intersection_two_sets():
    """Intersection of two sets returns common elements."""
    cube = SetOperationsCube()
    result = await cube.execute(
        set_a=["a", "b", "c", "d"],
        set_b=["b", "c", "e"],
        operation="intersection",
    )
    assert result["result"] == ["b", "c"]
    assert result["count"] == 2


@pytest.mark.asyncio
async def test_intersection_no_overlap():
    """Intersection of disjoint sets returns empty."""
    cube = SetOperationsCube()
    result = await cube.execute(
        set_a=["a", "b"],
        set_b=["c", "d"],
        operation="intersection",
    )
    assert result["result"] == []
    assert result["count"] == 0


# ============================================================
# Union
# ============================================================


@pytest.mark.asyncio
async def test_union_two_sets():
    """Union of two sets returns all unique elements, sorted."""
    cube = SetOperationsCube()
    result = await cube.execute(
        set_a=["a", "b", "c"],
        set_b=["b", "c", "d"],
        operation="union",
    )
    assert result["result"] == ["a", "b", "c", "d"]
    assert result["count"] == 4


# ============================================================
# Difference
# ============================================================


@pytest.mark.asyncio
async def test_difference_a_minus_b():
    """Difference returns elements in A but not in B."""
    cube = SetOperationsCube()
    result = await cube.execute(
        set_a=["a", "b", "c", "d"],
        set_b=["b", "c"],
        operation="difference",
    )
    assert result["result"] == ["a", "d"]
    assert result["count"] == 2


# ============================================================
# Three-way operations
# ============================================================


@pytest.mark.asyncio
async def test_three_way_intersection():
    """Three-way intersection: (A & B) & C."""
    cube = SetOperationsCube()
    result = await cube.execute(
        set_a=["a", "b", "c", "d"],
        set_b=["b", "c", "d", "e"],
        set_c=["c", "d", "e", "f"],
        operation="intersection",
    )
    assert result["result"] == ["c", "d"]
    assert result["count"] == 2


@pytest.mark.asyncio
async def test_three_way_union():
    """Three-way union: (A | B) | C."""
    cube = SetOperationsCube()
    result = await cube.execute(
        set_a=["a", "b"],
        set_b=["c", "d"],
        set_c=["d", "e"],
        operation="union",
    )
    assert result["result"] == ["a", "b", "c", "d", "e"]
    assert result["count"] == 5


@pytest.mark.asyncio
async def test_three_way_difference():
    """Three-way difference: (A - B) - C."""
    cube = SetOperationsCube()
    result = await cube.execute(
        set_a=["a", "b", "c", "d", "e"],
        set_b=["b", "c"],
        set_c=["d"],
        operation="difference",
    )
    assert result["result"] == ["a", "e"]
    assert result["count"] == 2


# ============================================================
# Empty input handling
# ============================================================


@pytest.mark.asyncio
async def test_empty_set_a():
    """Empty set_a with intersection returns empty."""
    cube = SetOperationsCube()
    result = await cube.execute(
        set_a=[],
        set_b=["a", "b"],
        operation="intersection",
    )
    assert result["result"] == []
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_empty_set_b():
    """Empty set_b with difference returns all of A."""
    cube = SetOperationsCube()
    result = await cube.execute(
        set_a=["a", "b"],
        set_b=[],
        operation="difference",
    )
    assert result["result"] == ["a", "b"]
    assert result["count"] == 2


# ============================================================
# Default operation
# ============================================================


@pytest.mark.asyncio
async def test_default_operation_is_intersection():
    """When operation is not specified, defaults to intersection."""
    cube = SetOperationsCube()
    result = await cube.execute(
        set_a=["a", "b", "c"],
        set_b=["b", "c", "d"],
    )
    assert result["result"] == ["b", "c"]
    assert result["count"] == 2


# ============================================================
# Unknown operation
# ============================================================


@pytest.mark.asyncio
async def test_unknown_operation_raises():
    """Unknown operation raises ValueError."""
    cube = SetOperationsCube()
    with pytest.raises(ValueError, match="Unknown operation"):
        await cube.execute(
            set_a=["a"],
            set_b=["b"],
            operation="xor",
        )


# ============================================================
# Result is sorted alphabetically
# ============================================================


@pytest.mark.asyncio
async def test_result_sorted_alphabetically():
    """Result is sorted alphabetically regardless of input order."""
    cube = SetOperationsCube()
    result = await cube.execute(
        set_a=["delta", "bravo", "alpha"],
        set_b=["charlie", "bravo", "echo"],
        operation="union",
    )
    assert result["result"] == ["alpha", "bravo", "charlie", "delta", "echo"]


# ============================================================
# Duplicates in input are handled
# ============================================================


@pytest.mark.asyncio
async def test_duplicates_in_input_deduplicated():
    """Duplicate values in input lists are deduplicated."""
    cube = SetOperationsCube()
    result = await cube.execute(
        set_a=["a", "a", "b", "b"],
        set_b=["b", "b", "c"],
        operation="union",
    )
    assert result["result"] == ["a", "b", "c"]
    assert result["count"] == 3
