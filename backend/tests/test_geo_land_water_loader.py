"""Unit tests for the land_water_loader geo module.

Tests pure spatial classification functions against bundled ne_50m_land.geojson.
No database or mocking needed — these operate on static GeoJSON data loaded
at module import time via STRtree spatial index.
"""

from app.geo.land_water_loader import classify_point, is_land


class TestIsLand:
    """Tests for is_land(lat, lon) -> bool."""

    def test_is_land_over_land_paris(self):
        """Paris is clearly on land."""
        assert is_land(48.85, 2.35) is True

    def test_is_land_over_land_denver(self):
        """Denver, Colorado is well inland -- clearly land."""
        assert is_land(39.74, -104.99) is True

    def test_is_land_over_ocean_atlantic(self):
        """A point in the mid-Atlantic ocean should be water."""
        assert is_land(30.0, -40.0) is False

    def test_is_land_over_ocean_pacific(self):
        """A point in the mid-Pacific ocean should be water."""
        assert is_land(0.0, -170.0) is False

    def test_is_land_inland_point(self):
        """Moscow is deeply inland -- clearly land."""
        assert is_land(55.75, 37.62) is True

    def test_is_land_offshore_point(self):
        """A point well off the coast of Africa in the Indian Ocean."""
        assert is_land(-30.0, 50.0) is False


class TestClassifyPoint:
    """Tests for classify_point(lat, lon) -> 'land' | 'water'."""

    def test_classify_point_land(self):
        """Paris should classify as land."""
        assert classify_point(48.85, 2.35) == "land"

    def test_classify_point_water(self):
        """Mid-Atlantic should classify as water."""
        assert classify_point(30.0, -40.0) == "water"

    def test_classify_point_returns_string(self):
        """classify_point always returns a string, never None."""
        result = classify_point(0.0, 0.0)
        assert isinstance(result, str)
        assert result in ("land", "water")
