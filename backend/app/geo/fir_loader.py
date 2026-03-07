"""European FIR boundary lookup module.

Loads the fir_uir_europe.geojson dataset (78 European FIR/UIR features,
derived from Eurocontrol data) at module import and builds a prepared Shapely
geometry index.

The fir_uir_europe.geojson dataset uses:
- Property 'AV_AIRSPAC': FIR designator (e.g. "EGTTFIR", "LFBBFIR")
- Property 'AV_NAME': FIR full name (e.g. "LONDON FIR", "BORDEAUX FIR")

Coverage: European FIRs/UIRs only — NOT global. Points outside Europe will
return None from classify_point().

Data source: jaluebbe/FlightMapEuropeSimple (Eurocontrol atlas, non-commercial)
Confidence: MEDIUM — suitable for research/prototype; verify AIRAC currency for
production use.

Coordinate order: Shapely / GeoJSON use (lon, lat) / (x, y) order. The
classify_point() function accepts (lat, lon) and swaps before calling
shapely.contains_xy().
"""
import logging

import shapely
from shapely.geometry import shape

from app.geo.loader import load_geojson

logger = logging.getLogger(__name__)

# Module-level cache: loaded once at import
# _FIR_INDEX: list of (designator, name, prepared_geometry) tuples
_FIR_INDEX: list[tuple[str, str, object]] = []
_BY_DESIGNATOR: dict[str, object] = {}

# Property keys for fir_uir_europe.geojson
_DESIGNATOR_KEY = "AV_AIRSPAC"
_NAME_KEY = "AV_NAME"

try:
    _features = load_geojson("fir_uir_europe.geojson")
    for _feat in _features:
        _props = _feat.get("properties") or {}
        _designator = _props.get(_DESIGNATOR_KEY)
        _name = _props.get(_NAME_KEY) or ""
        if _designator is None:
            continue
        try:
            _geom = shape(_feat["geometry"])
            shapely.prepare(_geom)
        except Exception as _err:
            logger.warning("fir_loader: skipping %s — geometry error: %s", _designator, _err)
            continue
        _FIR_INDEX.append((_designator, _name, _geom))
        _BY_DESIGNATOR[_designator] = _geom
    logger.info("fir_loader: loaded %d FIR/UIR boundaries", len(_FIR_INDEX))
except Exception as _load_err:
    logger.warning(
        "fir_loader: failed to load fir_uir_europe.geojson — classify_point() will return None. Error: %s",
        _load_err,
    )


def classify_point(lat: float, lon: float) -> dict | None:
    """Classify a lat/lon point to a European FIR/UIR.

    Returns {"fir": designator, "name": fir_name} if the point falls within
    a European FIR boundary, or None if the point is outside European FIR
    coverage.

    Note: Shapely uses (x=lon, y=lat) coordinate order — this function
    accepts (lat, lon) and swaps internally.
    """
    if not _FIR_INDEX:
        return None
    for designator, name, geom in _FIR_INDEX:
        if shapely.contains_xy(geom, float(lon), float(lat)):
            return {"fir": designator, "name": name}
    return None


def get_fir_polygon(designator: str) -> object | None:
    """Return the prepared Shapely geometry for a FIR by designator.

    Returns None if the designator is not found in the dataset.
    """
    return _BY_DESIGNATOR.get(designator)


def list_firs() -> list[str]:
    """Return all FIR designators available in the dataset."""
    return [designator for designator, _name, _geom in _FIR_INDEX]
