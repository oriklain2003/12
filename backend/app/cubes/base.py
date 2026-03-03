import abc
from typing import Any

from app.schemas.cube import CubeCategory, CubeDefinition, ParamDefinition, ParamType


class BaseCube(abc.ABC):
    """Abstract base class for all cubes.

    Subclasses must define class-level attributes:
        cube_id, name, description, category, inputs, outputs

    And implement the async execute() method.
    """

    cube_id: str
    name: str
    description: str = ""
    category: CubeCategory
    inputs: list[ParamDefinition] = []
    outputs: list[ParamDefinition] = []

    @property
    def definition(self) -> CubeDefinition:
        """Build and return a CubeDefinition from this cube's class properties.

        Automatically appends the __full_result__ output so every cube
        always exposes the Full Result port.
        """
        full_result = ParamDefinition(
            name="__full_result__",
            type=ParamType.JSON_OBJECT,
            description="Full result bundle of all outputs",
        )
        return CubeDefinition(
            cube_id=self.cube_id,
            name=self.name,
            description=self.description,
            category=self.category,
            inputs=list(self.inputs),
            outputs=list(self.outputs) + [full_result],
        )

    @abc.abstractmethod
    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Execute the cube's logic with the given input values.

        Args:
            **inputs: Keyword arguments matching the cube's input param names.

        Returns:
            A dict mapping output param names to their computed values.
        """
        ...
