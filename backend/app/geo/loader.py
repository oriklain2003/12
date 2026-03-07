"""Shared utilities for loading and indexing GeoJSON data files.

All GeoJSON files are bundled as static data in the data/ subdirectory.
No network calls are made at runtime — data is loaded once at module import
and cached as prepared Shapely geometries for fast repeated point-in-polygon
queries.

Coordinate order note: GeoJSON and Shapely use (lon, lat) / (x, y) order.
Callers that accept (lat, lon) must swap when calling shapely.contains_xy().
"""
import json
import pathlib

import shapely
from shapely.geometry import shape

_DATA_DIR = pathlib.Path(__file__).parent / "data"


def load_geojson(filename: str) -> list[dict]:
    """Load a GeoJSON FeatureCollection from the data/ directory.

    Returns the list of GeoJSON features. Raises FileNotFoundError if the
    file does not exist in the data/ directory.
    """
    path = _DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        fc = json.load(f)
    return fc["features"]


def build_polygon_index(
    features: list[dict], name_property: str
) -> dict[str, object]:
    """Build a dict mapping name -> prepared Shapely geometry.

    Geometries are prepared at build time (shapely.prepare()), which
    pre-computes internal GEOS spatial indexes. This amortizes the
    preparation cost across all future point-in-polygon queries — each
    subsequent contains_xy() call on a prepared geometry is significantly
    faster than on an unprepared one.

    Handles both Polygon and MultiPolygon geometry types automatically via
    shapely.geometry.shape().

    Features whose name_property is None or missing are silently skipped.
    """
    index: dict[str, object] = {}
    for feature in features:
        name = feature["properties"].get(name_property)
        if name is None:
            continue
        geom = shape(feature["geometry"])
        shapely.prepare(geom)
        index[name] = geom
    return index
