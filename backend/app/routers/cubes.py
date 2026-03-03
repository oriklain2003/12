"""Cubes router: exposes the cube catalog endpoint."""

from fastapi import APIRouter

from app.engine.registry import registry
from app.schemas.cube import CubeDefinition

router = APIRouter(prefix="/api/cubes", tags=["cubes"])


@router.get("/catalog", response_model=list[CubeDefinition])
async def get_catalog() -> list[CubeDefinition]:
    """Return all registered cube definitions."""
    return registry.catalog()
