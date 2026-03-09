"""Unit tests for the fir_loader geo module.

Tests pure spatial classification functions against bundled fir_uir_europe.geojson.
No database or mocking needed — these operate on static GeoJSON data loaded
at module import time.

Coverage is European FIRs only. Points outside Europe return None.
"""

from app.geo.fir_loader import classify_point, get_fir_polygon, list_firs


class TestClassifyPoint:
    """Tests for classify_point(lat, lon) -> dict | None."""

    def test_classify_point_london_fir(self):
        """A point over central London should fall within a London FIR."""
        result = classify_point(51.5, -0.1)
        assert result is not None
        assert "fir" in result
        assert "name" in result
        # London FIR designator contains "EGTT"
        assert "EGTT" in result["fir"]

    def test_classify_point_paris_fir(self):
        """A point over Paris should fall within a French FIR."""
        result = classify_point(48.85, 2.35)
        assert result is not None
        assert result["fir"] is not None

    def test_classify_point_outside_europe(self):
        """A point in the mid-Pacific should return None (outside European coverage)."""
        result = classify_point(0.0, -170.0)
        assert result is None

    def test_classify_point_south_america(self):
        """A point in South America should return None (outside European coverage)."""
        result = classify_point(-23.5, -46.6)
        assert result is None


class TestListFirs:
    """Tests for list_firs() -> list[str]."""

    def test_list_firs_returns_entries(self):
        """The European FIR dataset should have multiple entries."""
        firs = list_firs()
        assert len(firs) > 10

    def test_list_firs_contains_known_designator(self):
        """EGTTFIR (London) should appear in the designator list."""
        firs = list_firs()
        assert "EGTTFIR" in firs


class TestGetFirPolygon:
    """Tests for get_fir_polygon(designator) -> geometry | None."""

    def test_get_fir_polygon_known(self):
        """Known FIR designator returns a Shapely geometry."""
        geom = get_fir_polygon("EGTTFIR")
        assert geom is not None

    def test_get_fir_polygon_unknown(self):
        """Unknown designator returns None."""
        geom = get_fir_polygon("ZZZZ_DOES_NOT_EXIST")
        assert geom is None
