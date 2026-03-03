import { apiFetch } from './client';
import type { CubeDefinition } from '../types/cube';

export const getCatalog = () => apiFetch<CubeDefinition[]>('/cubes/catalog');
