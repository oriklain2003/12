/**
 * TypeScript type definitions for cube schemas.
 * Mirrors backend/app/schemas/cube.py
 */

export enum ParamType {
  STRING = 'string',
  NUMBER = 'number',
  BOOLEAN = 'boolean',
  LIST_OF_STRINGS = 'list_of_strings',
  LIST_OF_NUMBERS = 'list_of_numbers',
  JSON_OBJECT = 'json_object',
}

export enum CubeCategory {
  DATA_SOURCE = 'data_source',
  FILTER = 'filter',
  ANALYSIS = 'analysis',
  AGGREGATION = 'aggregation',
  OUTPUT = 'output',
}

export interface ParamDefinition {
  name: string;
  type: ParamType;
  description: string;
  required: boolean;
  default: string | number | boolean | unknown[] | null;
  accepts_full_result: boolean;
}

export interface CubeDefinition {
  cube_id: string;
  name: string;
  description: string;
  category: CubeCategory;
  inputs: ParamDefinition[];
  outputs: ParamDefinition[];
}
