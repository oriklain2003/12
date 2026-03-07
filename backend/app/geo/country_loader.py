"""Country boundary lookup module.

Loads the countries.geojson dataset (258 countries, public domain) at module
import and builds two prepared Shapely geometry indexes:
- _COUNTRY_INDEX: list of (name, iso3, prepared_geometry) tuples for PIP
- _BY_NAME: dict mapping country name -> prepared geometry
- _BY_ISO3: dict mapping ISO 3166 Alpha-3 code -> prepared geometry

The countries.geojson dataset uses:
- Property 'name': country name (e.g. "United Kingdom")
- Property 'ISO3166-1-Alpha-3': ISO3 code (e.g. "GBR")

Coordinate order: Shapely / GeoJSON use (lon, lat) / (x, y) order. The
classify_point() function accepts (lat, lon) and swaps before calling
shapely.contains_xy().
"""
import logging
import warnings

import shapely
from shapely.geometry import shape

from app.geo.loader import load_geojson

logger = logging.getLogger(__name__)

# Module-level cache: loaded once at import
_COUNTRY_INDEX: list[tuple[str, str, object]] = []  # (name, iso3, geom)
_BY_NAME: dict[str, object] = {}
_BY_ISO3: dict[str, object] = {}

# Property keys for countries.geojson
_NAME_KEY = "name"
_ISO3_KEY = "ISO3166-1-Alpha-3"

try:
    _features = load_geojson("countries.geojson")
    for _feat in _features:
        _props = _feat.get("properties") or {}
        _name = _props.get(_NAME_KEY)
        _iso3 = _props.get(_ISO3_KEY) or ""
        if _name is None:
            continue
        try:
            _geom = shape(_feat["geometry"])
            shapely.prepare(_geom)
        except Exception as _err:
            logger.warning("country_loader: skipping %s — geometry error: %s", _name, _err)
            continue
        _COUNTRY_INDEX.append((_name, _iso3, _geom))
        _BY_NAME[_name] = _geom
        if _iso3:
            _BY_ISO3[_iso3] = _geom
    logger.info("country_loader: loaded %d countries", len(_COUNTRY_INDEX))
except Exception as _load_err:
    logger.warning(
        "country_loader: failed to load countries.geojson — classify_point() will return None. Error: %s",
        _load_err,
    )


def classify_point(lat: float, lon: float) -> dict | None:
    """Classify a lat/lon point to a country.

    Returns {"country": name, "iso3": iso3_code} if the point falls within
    a country boundary, or None if the point is over an ocean or unclaimed
    territory.

    Note: Shapely uses (x=lon, y=lat) coordinate order — this function
    accepts (lat, lon) and swaps internally.
    """
    if not _COUNTRY_INDEX:
        return None
    for name, iso3, geom in _COUNTRY_INDEX:
        if shapely.contains_xy(geom, float(lon), float(lat)):
            return {"country": name, "iso3": iso3}
    return None


def get_country_polygon(name_or_iso3: str) -> object | None:
    """Return the prepared Shapely geometry for a country by name or ISO3 code.

    Returns None if the country is not found in the dataset.
    """
    geom = _BY_NAME.get(name_or_iso3)
    if geom is None:
        geom = _BY_ISO3.get(name_or_iso3)
    return geom


def list_countries() -> list[str]:
    """Return all available country names in the dataset."""
    return [name for name, _iso3, _geom in _COUNTRY_INDEX]
