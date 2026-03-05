---
phase: 08-geo-temporal-playback-learned-paths-and-flight-course-cubes
plan: "02"
requirements_completed: [GEO-04]
subsystem: backend-cubes
tags: [cubes, learned-paths, geospatial, shapely, geojson, corridor]
dependency_graph:
  requires: []
  provides: [get_learned_paths_cube]
  affects: [cube_catalog, geospatial_visualization]
tech_stack:
  added: [shapely==2.1.2]
  patterns: [shapely-buffer-corridor, ray-casting-polygon-filter, geojson-linestring, geojson-polygon]
key_files:
  created:
    - backend/app/cubes/get_learned_paths.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
key_decisions:
  - "Centerline points stored as {lat, lon, alt} JSONB dicts — parsed at query time"
  - "Corridor buffer approximation: 1 NM = 1/60 degree (flat-cap Shapely buffer)"
  - "Polygon filter uses ray-casting on centerline points, same pattern as AllFlights"
  - "Paths with fewer than 2 centerline points are silently skipped (cannot form geometry)"
metrics:
  duration: 2 min
  completed: "2026-03-05"
  tasks_completed: 2
  files_changed: 3
---

# Phase 08 Plan 02: Get Learned Paths Cube Summary

Implemented Shapely-backed GetLearnedPathsCube querying `public.learned_paths` with centerline (GeoJSON LineString) and corridor (Shapely-buffered GeoJSON Polygon) geometry modes.

## What Was Built

### GetLearnedPathsCube (`backend/app/cubes/get_learned_paths.py`)

A `DATA_SOURCE` cube that queries `public.learned_paths` with seven optional input parameters:

| Input | Type | Purpose |
|-------|------|---------|
| origin | string | ILIKE filter on origin airport ICAO |
| destination | string | ILIKE filter on destination airport ICAO |
| path_id | string | Exact path ID lookup |
| polygon | json_object (widget_hint=polygon) | Geofence — keep paths whose centerline passes through |
| min_member_count | number | Minimum confidence threshold |
| output_geometry | string | "centerline" or "corridor" (default: centerline) |
| width_override | number | Override DB width_nm for corridor generation |

Outputs: `paths` (JSON array with geometry) and `path_ids` (list of strings).

### Geometry Modes

**Centerline mode** — GeoJSON LineString with coordinates in [lon, lat] order per RFC 7946:
```json
{"type": "LineString", "coordinates": [[lon1, lat1], [lon2, lat2], ...]}
```

**Corridor mode** — Shapely `LineString.buffer()` creates a flat-cap polygon:
```python
buffer_deg = (width_nm / 2.0) / 60.0  # 1 NM ≈ 1/60 degree
polygon_geom = line.buffer(buffer_deg, cap_style="flat", join_style="round")
geometry = dict(mapping(polygon_geom))  # GeoJSON Polygon
```

### Schema Discovery

Actual `public.learned_paths` columns (inspected against Tracer 42 RDS):
- `id` (varchar), `origin` (varchar), `destination` (varchar)
- `centerline` (jsonb) — array of `{lat, lon, alt}` dicts
- `width_nm` (float8), `member_count` (int)
- `min_alt_ft` / `max_alt_ft` (float8, nullable)
- `created_at` (timestamp)

## Decisions Made

- **Centerline format:** DB stores `{lat, lon, alt}` JSONB dicts; cube parses at execute time
- **Corridor approximation:** 1 NM = 1/60 degree; Shapely flat-cap buffer; simple and avoids PostGIS dependency
- **Polygon filter reuse:** Imported `point_in_polygon` from `app.cubes.all_flights` — same ray-casting pattern
- **Skip short paths:** Paths with < 2 valid centerline points are skipped silently (cannot form LineString/Polygon)

## Deviations from Plan

None — plan executed exactly as written.

## Verification

```
$ uv run python -c "from app.cubes.get_learned_paths import GetLearnedPathsCube; c = GetLearnedPathsCube(); d = c.definition; assert d.cube_id == 'get_learned_paths'; assert any(i.name == 'output_geometry' for i in d.inputs); assert any(i.name == 'polygon' and i.widget_hint == 'polygon' for i in d.inputs); assert any(o.name == 'paths' for o in d.outputs); print('OK')"
OK

$ uv run python -c "from app.engine.registry import registry; ids = [c.cube_id for c in registry.catalog()]; assert 'get_learned_paths' in ids; print('OK')"
OK
```

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 119d947 | chore(08-02): add shapely 2.x dependency |
| Task 2 | 028584f | feat(08-02): implement GetLearnedPathsCube |

## Self-Check: PASSED

- backend/app/cubes/get_learned_paths.py — FOUND
- backend/pyproject.toml contains shapely — FOUND
- Commit 119d947 — FOUND
- Commit 028584f — FOUND
