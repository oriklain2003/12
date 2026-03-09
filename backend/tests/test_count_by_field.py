"""Tests for CountByFieldCube -- field-based aggregation.

Tests cover:
- Cube metadata (id, category, inputs, outputs)
- Basic grouping and counting with sorted desc output
- Empty data returns empty counts
- Missing field in data handled gracefully
- Full result dict input (extracts largest array)
- No data and no group_by_field guards
"""

import pytest


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """CountByFieldCube has correct cube_id, name, and category."""
    from app.cubes.count_by_field import CountByFieldCube
    from app.schemas.cube import CubeCategory

    cube = CountByFieldCube()
    assert cube.cube_id == "count_by_field"
    assert cube.name == "Count By Field"
    assert cube.category == CubeCategory.AGGREGATION


def test_cube_inputs():
    """CountByFieldCube has 'data' and 'group_by_field' inputs."""
    from app.cubes.count_by_field import CountByFieldCube

    cube = CountByFieldCube()
    input_names = {p.name for p in cube.inputs}
    assert "data" in input_names
    assert "group_by_field" in input_names


def test_cube_outputs():
    """CountByFieldCube has a 'counts' output."""
    from app.cubes.count_by_field import CountByFieldCube

    cube = CountByFieldCube()
    output_names = {p.name for p in cube.outputs}
    assert "counts" in output_names


def test_data_input_accepts_full_result():
    """data input has accepts_full_result=True."""
    from app.cubes.count_by_field import CountByFieldCube

    cube = CountByFieldCube()
    data_param = next(p for p in cube.inputs if p.name == "data")
    assert data_param.accepts_full_result is True


# ============================================================
# Execute behavior
# ============================================================


@pytest.mark.asyncio
async def test_count_basic():
    """Groups rows by field and returns counts sorted descending."""
    from app.cubes.count_by_field import CountByFieldCube

    cube = CountByFieldCube()
    data = [
        {"type": "A", "value": 1},
        {"type": "B", "value": 2},
        {"type": "A", "value": 3},
    ]
    result = await cube.execute(data=data, group_by_field="type")

    counts = result["counts"]
    assert len(counts) == 2
    # A appears twice, B once -> A first (sorted desc)
    assert counts[0] == {"value": "A", "count": 2}
    assert counts[1] == {"value": "B", "count": 1}


@pytest.mark.asyncio
async def test_count_empty_data():
    """Empty data array returns empty counts."""
    from app.cubes.count_by_field import CountByFieldCube

    cube = CountByFieldCube()
    result = await cube.execute(data=[], group_by_field="type")
    assert result == {"counts": []}


@pytest.mark.asyncio
async def test_count_missing_field():
    """Data rows without the group_by_field return empty counts."""
    from app.cubes.count_by_field import CountByFieldCube

    cube = CountByFieldCube()
    data = [
        {"name": "Alice"},
        {"name": "Bob"},
    ]
    result = await cube.execute(data=data, group_by_field="type")
    assert result == {"counts": []}


@pytest.mark.asyncio
async def test_count_full_result_dict():
    """Full result dict input extracts the first list value for grouping."""
    from app.cubes.count_by_field import CountByFieldCube

    cube = CountByFieldCube()
    full_result = {
        "metadata": "ignored",
        "flights": [
            {"carrier": "EL-AL", "status": "active"},
            {"carrier": "EL-AL", "status": "active"},
            {"carrier": "AA", "status": "active"},
        ],
    }
    result = await cube.execute(data=full_result, group_by_field="carrier")

    counts = result["counts"]
    assert len(counts) == 2
    assert counts[0]["value"] == "EL-AL"
    assert counts[0]["count"] == 2


@pytest.mark.asyncio
async def test_count_no_data():
    """No data provided returns empty counts."""
    from app.cubes.count_by_field import CountByFieldCube

    cube = CountByFieldCube()
    result = await cube.execute(group_by_field="type")
    assert result == {"counts": []}


@pytest.mark.asyncio
async def test_count_no_group_by_field():
    """No group_by_field provided returns empty counts."""
    from app.cubes.count_by_field import CountByFieldCube

    cube = CountByFieldCube()
    result = await cube.execute(data=[{"type": "A"}])
    assert result == {"counts": []}


@pytest.mark.asyncio
async def test_count_multiple_groups():
    """Multiple groups are all counted and sorted correctly."""
    from app.cubes.count_by_field import CountByFieldCube

    cube = CountByFieldCube()
    data = [
        {"status": "active"},
        {"status": "active"},
        {"status": "active"},
        {"status": "pending"},
        {"status": "pending"},
        {"status": "closed"},
    ]
    result = await cube.execute(data=data, group_by_field="status")

    counts = result["counts"]
    assert len(counts) == 3
    assert counts[0] == {"value": "active", "count": 3}
    assert counts[1] == {"value": "pending", "count": 2}
    assert counts[2] == {"value": "closed", "count": 1}
