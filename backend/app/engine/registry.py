"""CubeRegistry: auto-discovers BaseCube subclasses from the cubes package."""

import importlib
import pkgutil
from typing import TYPE_CHECKING

import app.cubes as cubes_package
from app.cubes.base import BaseCube
from app.schemas.cube import CubeDefinition

if TYPE_CHECKING:
    pass


class CubeRegistry:
    """Registry that auto-discovers and holds all registered cube instances."""

    def __init__(self) -> None:
        self._cubes: dict[str, BaseCube] = {}

    def load(self) -> None:
        """Scan the app.cubes package and import all cube modules.

        After importing, collect all BaseCube subclasses and store instances
        keyed by cube_id. Skips the 'base' module.
        """
        for _finder, module_name, _is_pkg in pkgutil.iter_modules(cubes_package.__path__):
            if module_name == "base":
                continue
            full_module = f"app.cubes.{module_name}"
            importlib.import_module(full_module)

        # Collect all BaseCube subclasses (direct and indirect)
        for subclass in BaseCube.__subclasses__():
            try:
                instance = subclass()
                self._cubes[instance.cube_id] = instance
            except Exception:
                pass

    def get(self, cube_id: str) -> BaseCube | None:
        """Return a cube instance by its cube_id, or None if not found."""
        return self._cubes.get(cube_id)

    def all(self) -> list[BaseCube]:
        """Return all registered cube instances."""
        return list(self._cubes.values())

    def catalog(self) -> list[CubeDefinition]:
        """Return CubeDefinition for every registered cube."""
        return [cube.definition for cube in self._cubes.values()]


# Module-level singleton — triggers auto-discovery on import
registry = CubeRegistry()
registry.load()
