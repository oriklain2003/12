"""Tests for EchoCube -- simple value passthrough.

Tests cover:
- Cube metadata (id, category, inputs, outputs)
- Echo returns input value unchanged
- Echo with empty/missing input returns empty string
"""

import pytest


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """EchoCube has correct cube_id, name, and category."""
    from app.cubes.echo_cube import EchoCube
    from app.schemas.cube import CubeCategory

    cube = EchoCube()
    assert cube.cube_id == "echo"
    assert cube.name == "Echo"
    assert cube.category == CubeCategory.OUTPUT


def test_cube_inputs():
    """EchoCube has a 'value' input."""
    from app.cubes.echo_cube import EchoCube

    cube = EchoCube()
    input_names = {p.name for p in cube.inputs}
    assert "value" in input_names


def test_cube_outputs():
    """EchoCube has a 'result' output."""
    from app.cubes.echo_cube import EchoCube

    cube = EchoCube()
    output_names = {p.name for p in cube.outputs}
    assert "result" in output_names


# ============================================================
# Execute behavior
# ============================================================


@pytest.mark.asyncio
async def test_echo_returns_input():
    """EchoCube returns the input value unchanged."""
    from app.cubes.echo_cube import EchoCube

    cube = EchoCube()
    result = await cube.execute(value="hello")
    assert result == {"result": "hello"}


@pytest.mark.asyncio
async def test_echo_returns_numeric_string():
    """EchoCube echoes numeric strings correctly."""
    from app.cubes.echo_cube import EchoCube

    cube = EchoCube()
    result = await cube.execute(value="42")
    assert result == {"result": "42"}


@pytest.mark.asyncio
async def test_echo_empty_input():
    """EchoCube returns empty string when no value provided."""
    from app.cubes.echo_cube import EchoCube

    cube = EchoCube()
    result = await cube.execute()
    assert result == {"result": ""}
