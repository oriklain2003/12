# Deferred Items — Phase 16

## Out-of-Scope Failures Found During Plan 03 Execution

The following test failures were discovered during full suite verification.
These pre-exist Phase 16 changes and are NOT caused by signal health modifications.

### test_area_spatial_filter.py (8 failures)

- test_alison_provider_polygon
- test_movement_classification_landing
- test_movement_classification_takeoff
- test_movement_classification_cruise_fr
- test_fr_movement_classification_landing
- test_fr_movement_classification_takeoff
- test_per_flight_details_structure
- test_polygon_lat_lon_order

Root cause: AreaSpatialFilterCube mock setup mismatches — likely due to Phase 17 SQL pushdown changes to SquawkFilterCube affecting shared test infrastructure, or pre-existing failures from Phase 12/15.

### test_stream_graph.py (1 failure)

- test_stream_graph_row_limiting

Root cause: `truncated` flag not set as expected — stream graph row truncation behavior may have changed in Phase 17 optimizations.

### Action

These failures should be investigated and fixed in a dedicated phase or as part of the next maintenance cycle. They are not regressions from Phase 16.
