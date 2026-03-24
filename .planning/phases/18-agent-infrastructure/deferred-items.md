# Deferred Items — Phase 18

## Pre-existing test failures (out of scope for 18-04)

Discovered during 18-04 full suite run. These failures exist in files modified
before phase 18 started (visible in opening git status). Not caused by 18-04 changes.

### test_all_flights.py::test_cube_inputs
- **File:** backend/tests/test_all_flights.py
- **Root cause:** `all_flights.py` has an `airport` input parameter that tests don't expect
- **Status:** Pre-existing, `all_flights.py` was already modified before phase 18

### test_area_spatial_filter.py (9 failures)
- **File:** backend/tests/test_area_spatial_filter.py
- **Root cause:** Various assertion failures in spatial filter tests
- **Status:** Pre-existing, file was already modified before phase 18

### test_stream_graph.py::test_stream_graph_row_limiting
- **File:** backend/tests/test_stream_graph.py
- **Root cause:** Row limiting assertion failure
- **Status:** Pre-existing
