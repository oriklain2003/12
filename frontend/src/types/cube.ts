/**
 * TypeScript type definitions for cube schemas.
 * Mirrors backend/app/schemas/cube.py
 *
 * Uses const objects + type aliases instead of enum to satisfy erasableSyntaxOnly.
 */

export const ParamType = {
  STRING: 'string',
  NUMBER: 'number',
  BOOLEAN: 'boolean',
  LIST_OF_STRINGS: 'list_of_strings',
  LIST_OF_NUMBERS: 'list_of_numbers',
  JSON_OBJECT: 'json_object',
} as const;
export type ParamType = (typeof ParamType)[keyof typeof ParamType];

export const CubeCategory = {
  DATA_SOURCE: 'data_source',
  FILTER: 'filter',
  ANALYSIS: 'analysis',
  AGGREGATION: 'aggregation',
  OUTPUT: 'output',
} as const;
export type CubeCategory = (typeof CubeCategory)[keyof typeof CubeCategory];

export interface ParamDefinition {
  name: string;
  type: ParamType;
  description: string;
  required: boolean;
  default: string | number | boolean | unknown[] | null;
  accepts_full_result: boolean;
  widget_hint?: string | null;
  options?: string[] | null;
}

export interface CubeDefinition {
  cube_id: string;
  name: string;
  description: string;
  category: CubeCategory;
  inputs: ParamDefinition[];
  outputs: ParamDefinition[];
  widget?: string | null;
}
