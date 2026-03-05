from enum import Enum
from typing import Any

from pydantic import BaseModel


class ParamType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    LIST_OF_STRINGS = "list_of_strings"
    LIST_OF_NUMBERS = "list_of_numbers"
    JSON_OBJECT = "json_object"


class CubeCategory(str, Enum):
    DATA_SOURCE = "data_source"
    FILTER = "filter"
    ANALYSIS = "analysis"
    AGGREGATION = "aggregation"
    OUTPUT = "output"


class ParamDefinition(BaseModel):
    name: str
    type: ParamType
    required: bool = False
    default: Any = None
    description: str = ""
    accepts_full_result: bool = False
    widget_hint: str | None = None


class CubeDefinition(BaseModel):
    cube_id: str
    name: str
    description: str = ""
    category: CubeCategory
    inputs: list[ParamDefinition] = []
    outputs: list[ParamDefinition] = []
    widget: str | None = None
