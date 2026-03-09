"""Tests for AddNumbersCube -- numeric addition.

Tests cover:
- Cube metadata (id, category, inputs, outputs)
- Integer addition
- Float addition (approx comparison)
- Zero defaults when no args provided
- Negative number handling
"""

import pytest


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """AddNumbersCube has correct cube_id, name, and category."""
    from app.cubes.add_numbers import AddNumbersCube
    from app.schemas.cube import CubeCategory

    cube = AddNumbersCube()
    assert cube.cube_id == "add_numbers"
    assert cube.name == "Add Numbers"
    assert cube.category == CubeCategory.ANALYSIS


def test_cube_inputs():
    """AddNumbersCube has 'a' and 'b' inputs."""
    from app.cubes.add_numbers import AddNumbersCube

    cube = AddNumbersCube()
    input_names = {p.name for p in cube.inputs}
    assert "a" in input_names
    assert "b" in input_names


def test_cube_outputs():
    """AddNumbersCube has a 'sum' output."""
    from app.cubes.add_numbers import AddNumbersCube

    cube = AddNumbersCube()
    output_names = {p.name for p in cube.outputs}
    assert "sum" in output_names


# ============================================================
# Execute behavior
# ============================================================


@pytest.mark.asyncio
async def test_add_integers():
    """Adding two integers returns correct float sum."""
    from app.cubes.add_numbers import AddNumbersCube

    cube = AddNumbersCube()
    result = await cube.execute(a=3, b=4)
    assert result == {"sum": 7.0}


@pytest.mark.asyncio
async def test_add_floats():
    """Adding two floats returns approximately correct sum."""
    from app.cubes.add_numbers import AddNumbersCube

    cube = AddNumbersCube()
    result = await cube.execute(a=1.5, b=2.7)
    assert result["sum"] == pytest.approx(4.2, abs=1e-9)


@pytest.mark.asyncio
async def test_add_zero_defaults():
    """No arguments defaults to 0 + 0 = 0.0."""
    from app.cubes.add_numbers import AddNumbersCube

    cube = AddNumbersCube()
    result = await cube.execute()
    assert result == {"sum": 0.0}


@pytest.mark.asyncio
async def test_add_negative():
    """Adding a negative number works correctly."""
    from app.cubes.add_numbers import AddNumbersCube

    cube = AddNumbersCube()
    result = await cube.execute(a=-5, b=3)
    assert result == {"sum": -2.0}


@pytest.mark.asyncio
async def test_add_single_argument():
    """Providing only one argument defaults the other to 0."""
    from app.cubes.add_numbers import AddNumbersCube

    cube = AddNumbersCube()
    result = await cube.execute(a=10)
    assert result == {"sum": 10.0}
