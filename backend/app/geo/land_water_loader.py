"""Land vs water classification module.

Loads the ne_50m_land.geojson dataset (Natural Earth 50m land polygons, 1420
features, public domain) at module import and builds a prepared Shapely STRtree
spatial index for fast point-in-land queries.

The ne_50m_land.geojson dataset contains anonymous land polygon features with
no name property. This module exposes land/water classification only.

Data source: nvkelso/natural-earth-vector (Natural Earth 50m, public domain)
Resolution: 1:50m scale (~1km accuracy) — appropriate for aviation use.

Performance strategy: STRtree.query() narrows candidates to polygons whose
bounding box contains the query point, then shapely.contains_xy() is applied
only to those candidates. With 1420 large land polygons, naive linear search
would test all polygons — STRtree brings this to O(log n) bbox candidates.

Coordinate order: Shapely / GeoJSON use (lon, lat) / (x, y) order. The
is_land() and classify_point() functions accept (lat, lon) and swap internally.
"""
import logging

import shapely
from shapely import STRtree
from shapely.geometry import Point, shape

from app.geo.loader import load_geojson

logger = logging.getLogger(__name__)

# Module-level cache: loaded once at import
_LAND_GEOMETRIES: list[object] = []  # list of prepared Shapely geometries
_LAND_TREE: STRtree | None = None

try:
    _features = load_geojson("ne_50m_land.geojson")
    _geoms = []
    for _feat in _features:
        try:
            _geom = shape(_feat["geometry"])
            _geoms.append(_geom)
        except Exception as _err:
            logger.warning("land_water_loader: skipping feature — geometry error: %s", _err)
            continue

    if _geoms:
        # STRtree is built from unprepared geometries — prepare separately for
        # efficient contains_xy() calls after bbox pre-filtering.
        for _g in _geoms:
            shapely.prepare(_g)
        _LAND_GEOMETRIES = _geoms
        # Build STRtree with unprepared copies is not possible after prepare(),
        # but STRtree.query() uses the envelope for fast pre-filtering which works
        # with prepared geometries as well.
        _LAND_TREE = STRtree(_geoms)
        logger.info("land_water_loader: loaded %d land polygons", len(_LAND_GEOMETRIES))
except Exception as _load_err:
    logger.warning(
        "land_water_loader: failed to load ne_50m_land.geojson — is_land() will return False. Error: %s",
        _load_err,
    )


def is_land(lat: float, lon: float) -> bool:
    """Return True if the point (lat, lon) is on land, False if over water.

    Uses STRtree for fast bbox pre-filtering, then shapely.contains_xy() for
    precise polygon containment check.

    Returns False (water) if the land polygon data failed to load.

    Note: Shapely uses (x=lon, y=lat) coordinate order — this function
    accepts (lat, lon) and swaps internally.
    """
    if _LAND_TREE is None or not _LAND_GEOMETRIES:
        return False

    # STRtree.query() returns indices of candidate geometries whose envelopes
    # intersect the query point's envelope (i.e., the point itself).
    pt = Point(float(lon), float(lat))
    candidate_indices = _LAND_TREE.query(pt, predicate=None)

    for idx in candidate_indices:
        geom = _LAND_GEOMETRIES[idx]
        if shapely.contains_xy(geom, float(lon), float(lat)):
            return True
    return False


def classify_point(lat: float, lon: float) -> str:
    """Return "land" or "water" for a lat/lon point.

    Convenience wrapper around is_land() that returns a string classification
    suitable for use as a display value or filter criterion.
    """
    return "land" if is_land(lat, lon) else "water"
