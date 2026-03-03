from enum import Enum

from pydantic import BaseModel


class ParamType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    STRING_ARRAY = "string_array"
    NUMBER_ARRAY = "number_array"
    FLIGHT_IDS = "flight_ids"
    JSON = "json"


class CubeCategory(str, Enum):
    DATA_SOURCE = "data_source"
    FILTER = "filter"
    ANALYSIS = "analysis"
    AGGREGATION = "aggregation"
    OUTPUT = "output"


class ParamDefinition(BaseModel):
    name: str
    type: ParamType
    label: str
    description: str = ""
    required: bool = False
    default: str | int | float | bool | list | None = None
    is_output: bool = False
    accepts_full_result: bool = False


class CubeDefinition(BaseModel):
    id: str
    name: str
    description: str
    category: CubeCategory
    inputs: list[ParamDefinition]
    outputs: list[ParamDefinition]

    @property
    def full_result_output(self) -> ParamDefinition:
        return ParamDefinition(
            name="__full_result__",
            type=ParamType.JSON,
            label="Full Result",
            description="All outputs bundled as JSON",
            is_output=True,
        )
