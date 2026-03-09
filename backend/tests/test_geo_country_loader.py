"""Unit tests for the country_loader geo module.

Tests pure spatial classification functions against bundled countries.geojson.
No database or mocking needed — these operate on static GeoJSON data loaded
at module import time.
"""

from app.geo.country_loader import classify_point, get_country_polygon, list_countries


class TestClassifyPoint:
    """Tests for classify_point(lat, lon) -> dict | None."""

    def test_classify_point_known_country_israel(self):
        """Tel Aviv should resolve to Israel."""
        result = classify_point(32.08, 34.78)
        assert result is not None
        assert result["country"] == "Israel"
        assert result["iso3"] == "ISR"

    def test_classify_point_known_country_france(self):
        """Paris should resolve to France."""
        result = classify_point(48.85, 2.35)
        assert result is not None
        assert result["country"] == "France"
        # iso3 present (dataset uses "-99" for some countries instead of standard codes)
        assert "iso3" in result

    def test_classify_point_ocean_returns_none(self):
        """A point in the mid-Atlantic ocean should return None."""
        result = classify_point(30.0, -40.0)
        assert result is None

    def test_classify_point_another_country_usa(self):
        """New York should resolve to United States of America."""
        result = classify_point(40.71, -74.01)
        assert result is not None
        assert "United States" in result["country"]
        assert result["iso3"] == "USA"


class TestListCountries:
    """Tests for list_countries() -> list[str]."""

    def test_list_countries_returns_many(self):
        """The bundled dataset has 258 countries; expect >100 entries."""
        countries = list_countries()
        assert len(countries) > 100

    def test_list_countries_contains_known(self):
        """Israel and France should appear in the list."""
        countries = list_countries()
        assert "Israel" in countries
        assert "France" in countries


class TestGetCountryPolygon:
    """Tests for get_country_polygon(name_or_iso3) -> geometry | None."""

    def test_get_country_polygon_by_name(self):
        """Lookup by country name returns a Shapely geometry."""
        geom = get_country_polygon("Israel")
        assert geom is not None

    def test_get_country_polygon_by_iso3(self):
        """Lookup by ISO3 code returns a Shapely geometry."""
        # Israel has standard ISO3 "ISR" in this dataset
        geom = get_country_polygon("ISR")
        assert geom is not None

    def test_get_country_polygon_unknown_returns_none(self):
        """Unknown country name returns None."""
        geom = get_country_polygon("Narnia")
        assert geom is None
