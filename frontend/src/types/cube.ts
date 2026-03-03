/**
 * TypeScript type definitions for cube schemas.
 * Mirrors backend/app/schemas/cube.py
 */

export enum ParamType {
  STRING = 'string',
  NUMBER = 'number',
  BOOLEAN = 'boolean',
  STRING_ARRAY = 'string_array',
  NUMBER_ARRAY = 'number_array',
  FLIGHT_IDS = 'flight_ids',
  JSON = 'json',
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
  label: string;
  description: string;
  required: boolean;
  default: string | number | boolean | unknown[] | null;
  is_output: boolean;
  accepts_full_result: boolean;
}

export interface CubeDefinition {
  id: string;
  name: string;
  description: string;
  category: CubeCategory;
  inputs: ParamDefinition[];
  outputs: ParamDefinition[];
}
