# Phase 15: Cube Unit Tests and Integration Tests - Research

**Researched:** 2026-03-09
**Domain:** Python async testing (pytest-asyncio), DB mocking, cube framework testing
**Confidence:** HIGH

## Summary

This phase adds comprehensive tests for all 14 production cubes (plus 2 utility cubes), 2 signal detection modules, 3 geo loaders, and multi-cube integration through the WorkflowExecutor. The project already has 6 well-structured test files establishing clear patterns: pytest-asyncio with `asyncio_mode = "auto"`, `unittest.mock.AsyncMock` + `patch` for DB isolation, helper functions for building test data, and direct cube instantiation for unit tests.

The existing test infrastructure is mature and consistent. No new libraries or frameworks are needed. The main work is applying established patterns systematically across all untested cubes and modules. Cubes fall into three complexity tiers: (1) pure-logic cubes needing no mocking (echo, add_numbers, set_operations, count_by_field, geo_temporal_playback), (2) DB-querying cubes needing `engine.connect()` mocking (all_flights, alison_flights, get_anomalies, get_flight_course, get_learned_paths, filter_flights, squawk_filter, registration_country_filter, area_spatial_filter, dark_flight_detector), and (3) the signal_health_analyzer which requires mocking its signal module dependencies. Signal modules (rule_based.py, kalman.py) have both pure-computation functions testable without mocking and async DB functions requiring mocking.

**Primary recommendation:** Follow the established test file patterns exactly. Use one test file per cube/module. Mock at the `engine.connect()` boundary for DB cubes, and mock at the signal function boundary for signal_health_analyzer. Test metadata, empty guards, core logic, and edge cases for each cube.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- All 14 cubes get tested equally -- no prioritization, every cube gets unit tests
- Signal modules (rule_based.py, kalman.py) tested independently as well as through their cube
- Geo loaders (country_loader, fir_loader, land_water_loader) tested independently
- Integration tests = multi-cube pipeline execution through the WorkflowExecutor
- Test realistic cube chains (e.g., data_source -> filter -> analysis)
- No live DB integration tests -- mock all DB access
- Use realistic flight data for test fixtures
- For signal cubes (jamming, spoofing, transponder gaps): create mock data that represents real scenarios
- Strategy: search the DB for real examples first; if too hard to extract, invent realistic mock data
- Existing cubes with simpler inputs: inline data is fine (following existing test patterns)

### Claude's Discretion
- DB mocking strategy (session-level patching, shared fixtures, or mix)
- Test file organization (one file per cube vs grouped)
- Fixture sharing approach
- Assertion granularity

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=9.0.2 | Test runner and assertions | Already installed, project standard |
| pytest-asyncio | >=1.3.0 | Async test support | Already installed, `asyncio_mode = "auto"` configured |
| unittest.mock | stdlib | AsyncMock, patch, MagicMock | Already used in all existing tests, no external dep |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | >=0.28.1 | ASGI test client for SSE/HTTP endpoint tests | Already installed, used in test_sse_stream.py |
| numpy | >=2.4.2 | Test data generation for Kalman tests | Already installed for signal modules |

**No new dependencies needed.** All testing libraries are already in `[dependency-groups] dev`.

**Installation:**
```bash
cd backend && uv sync
```

## Architecture Patterns

### Recommended Test File Organization

Use **one test file per cube/module** -- matches existing patterns, allows parallel execution, makes test ownership clear.

```
backend/tests/
├── __init__.py                          # existing
├── conftest.py                          # NEW: shared fixtures
├── test_executor.py                     # existing (engine tests)
├── test_stream_graph.py                 # existing (SSE engine tests)
├── test_sse_stream.py                   # existing (HTTP SSE tests)
├── test_filter_flights.py               # existing
├── test_dark_flight_detector.py         # existing
├── test_set_operations.py              # existing
│
│ # ---- NEW unit tests (one per untested cube) ----
├── test_echo_cube.py                   # trivial, quick
├── test_add_numbers.py                 # trivial, quick
├── test_count_by_field.py              # pure logic + pandas
├── test_geo_temporal_playback.py       # passthrough cube
├── test_all_flights.py                 # DB-mocking cube
├── test_alison_flights.py             # DB-mocking cube
├── test_get_anomalies.py              # DB-mocking cube
├── test_get_flight_course.py          # DB-mocking cube
├── test_get_learned_paths.py          # DB-mocking cube
├── test_squawk_filter.py             # DB-mocking + dual-provider
├── test_registration_country_filter.py # DB + icao24_lookup
├── test_area_spatial_filter.py        # DB + Shapely
├── test_signal_health_analyzer.py     # signal module mocking
│
│ # ---- NEW signal module tests ----
├── test_signal_rule_based.py          # pure functions + async DB
├── test_signal_kalman.py             # pure functions + async DB
│
│ # ---- NEW geo loader tests ----
├── test_geo_country_loader.py        # loaded data + classify_point
├── test_geo_fir_loader.py           # loaded data + classify_point
├── test_geo_land_water_loader.py    # loaded data + is_land
│
│ # ---- NEW integration tests ----
├── test_integration_pipelines.py     # multi-cube via WorkflowExecutor
└── test_icao24_lookup.py            # pure lookup module
```

### Pattern 1: Cube Metadata Tests (Mandatory per Cube)
**What:** Every cube test file starts with metadata validation tests.
**When to use:** Always -- first tests in every cube test file.
**Example:**
```python
# Source: existing pattern from test_dark_flight_detector.py
def test_cube_metadata():
    from app.cubes.some_cube import SomeCube
    from app.schemas.cube import CubeCategory

    cube = SomeCube()
    assert cube.cube_id == "some_cube"
    assert cube.name == "Some Cube"
    assert cube.category == CubeCategory.FILTER

def test_cube_inputs():
    from app.cubes.some_cube import SomeCube
    cube = SomeCube()
    input_names = {p.name for p in cube.inputs}
    assert "expected_input" in input_names

def test_cube_outputs():
    from app.cubes.some_cube import SomeCube
    cube = SomeCube()
    output_names = {p.name for p in cube.outputs}
    assert "expected_output" in output_names
```

### Pattern 2: DB-Mocking for Engine-Connected Cubes
**What:** Patch `engine.connect()` to return mocked connection with controlled result data.
**When to use:** Any cube that imports `engine` from `app.database`.
**Example:**
```python
# Source: existing pattern from test_filter_flights.py
@pytest.mark.asyncio
async def test_db_cube_operation():
    from app.cubes.all_flights import AllFlightsCube

    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.keys.return_value = ["flight_id", "callsign"]
    mock_result.fetchall.return_value = [("F1", "CS1"), ("F2", "CS2")]
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.execute = AsyncMock(return_value=mock_result)

    cube = AllFlightsCube()
    with patch("app.cubes.all_flights.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = await cube.execute(time_range_seconds=3600)

    assert len(result["flights"]) == 2
```

### Pattern 3: Internal Method Mocking (for Complex Cubes)
**What:** Patch private query methods directly on the cube instance for cleaner tests.
**When to use:** Cubes with private query methods like `_query_positions`.
**Example:**
```python
# Source: existing pattern from test_dark_flight_detector.py
@pytest.mark.asyncio
async def test_with_internal_mock():
    cube = DarkFlightDetectorCube()
    with patch.object(cube, "_query_positions", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = positions
        result = await cube.execute(hex_list=["ABC123"])
```

### Pattern 4: Pure Function Testing (Signal Modules)
**What:** Test computation functions directly without mocking -- pass data in, check output.
**When to use:** kalman_filter(), detect_position_jumps(), detect_altitude_divergence(), physics_cross_validation(), score_event(), classify_event().
**Example:**
```python
# Test pure Kalman computation
from datetime import datetime, timezone

def test_kalman_filter_flags_jump():
    from app.signal.kalman import kalman_filter

    base_time = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    positions = [
        {"lat": 32.0, "lon": 34.0, "ts": base_time},
        {"lat": 32.001, "lon": 34.001, "ts": base_time + timedelta(seconds=10)},
        # ... normal positions ...
        # big jump:
        {"lat": 35.0, "lon": 37.0, "ts": base_time + timedelta(seconds=20)},
    ]
    results = kalman_filter(positions)
    assert any(r["flagged"] for r in results)
```

### Pattern 5: Integration Pipeline Tests
**What:** Build a multi-node WorkflowGraph, mock all cube execute() methods, run through execute_graph.
**When to use:** Integration tests verifying data flows between cubes.
**Example:**
```python
# Source: existing pattern from test_executor.py
@pytest.mark.asyncio
async def test_data_source_to_filter_pipeline():
    from app.engine.executor import execute_graph

    # Create mock cubes that return realistic data
    class MockDataSource:
        cube_id = "mock_data_source"
        async def execute(self, **inputs):
            return {"flights": [...], "flight_ids": ["F1", "F2"]}

    class MockFilter:
        cube_id = "mock_filter"
        async def execute(self, **inputs):
            ids = inputs.get("flight_ids", [])
            return {"filtered_flight_ids": ids[:1]}

    mock_registry = MagicMock()
    def get_cube(cube_id):
        if cube_id == "mock_data_source": return MockDataSource()
        if cube_id == "mock_filter": return MockFilter()
    mock_registry.get.side_effect = get_cube

    graph = WorkflowGraph(
        nodes=[
            make_node("src", "mock_data_source"),
            make_node("flt", "mock_filter"),
        ],
        edges=[make_edge("e1", "src", "flt",
                         source_handle="__full_result__",
                         target_handle="full_result")],
    )

    with patch("app.engine.executor.registry", mock_registry):
        results = await execute_graph(graph)

    assert results["src"]["status"] == "done"
    assert results["flt"]["status"] == "done"
```

### Anti-Patterns to Avoid
- **Live DB tests:** Never connect to real DB -- mock all `engine.connect()` calls.
- **Cross-test imports:** Don't import helpers from one test file into another (existing pattern duplicates helpers per file). Use conftest.py for truly shared fixtures.
- **Testing SQL correctness:** Don't assert on SQL string content. Test cube behavior via mocked results.
- **Over-mocking:** For pure-logic cubes (echo, add_numbers, count_by_field), don't mock -- call execute() directly with real data.
- **Importing at module level in tests:** Use inline imports inside test functions (established pattern prevents import-time side effects from DB connections).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async test execution | Custom event loop management | pytest-asyncio with `asyncio_mode = "auto"` | Already configured, handles all async test lifecycle |
| DB connection mocking | Custom DB test doubles | `unittest.mock.AsyncMock` + `patch("app.cubes.xxx.engine")` | Established pattern, type-safe enough for tests |
| Workflow graph construction | Manual dict building | `make_node()` + `make_edge()` helper functions | Already proven in test_executor.py and test_stream_graph.py |
| Mock flight data builders | One-off dict literals | `make_position()`, `make_flight()` helper functions | Reusable across tests, self-documenting |

**Key insight:** The existing test files already solve all infrastructure problems. This phase is about applying established patterns, not inventing new test infrastructure.

## Common Pitfalls

### Pitfall 1: Forgetting to Mock Multiple DB Calls
**What goes wrong:** Cubes like AllFlightsCube and AlisonFlightsCube make 2 DB calls when polygon filter is active (first for metadata, second for positions). Only mocking one call causes test failures.
**Why it happens:** Not reading the cube source code carefully -- the second call is inside a conditional block.
**How to avoid:** Use `mock_conn.execute = AsyncMock(side_effect=[result1, result2])` for cubes with polygon filters.
**Warning signs:** Tests pass without polygon but fail with polygon filter active.

### Pitfall 2: Coordinate Order Confusion
**What goes wrong:** Tests pass bad coordinate orders to Shapely-using cubes (AreaSpatialFilter, geo loaders).
**Why it happens:** GeoJSON and Shapely use (lon, lat) but user-facing input is [lat, lon].
**How to avoid:** Always use [lat, lon] in test polygon inputs (matching the cube's documented convention). The cube handles the swap internally.
**Warning signs:** Points that should be inside a polygon are not detected.

### Pitfall 3: Not Testing Empty/Missing Input Guards
**What goes wrong:** Cubes crash on None or empty inputs in production.
**Why it happens:** Tests only cover happy paths with valid data.
**How to avoid:** Every cube test file must include: (1) empty input guard test, (2) missing optional params test.

### Pitfall 4: Module-Level Imports Triggering DB Connections
**What goes wrong:** Importing signal modules or geo loaders at the module level in test files triggers actual DB connections or file I/O.
**Why it happens:** rule_based.py and kalman.py import `engine` at module level; geo loaders load GeoJSON at module level.
**How to avoid:** Use inline imports inside test functions (established pattern). For geo loaders, the GeoJSON files are bundled static data that loads fine -- no DB needed. For signal module async functions, mock `engine` at the function level.
**Warning signs:** Tests fail with DB connection errors before any test function runs.

### Pitfall 5: Forgetting `__full_result__` Port in Integration Tests
**What goes wrong:** Integration tests connect cubes but don't wire through the `__full_result__` source handle.
**Why it happens:** Not understanding that the full_result bundle requires `sourceHandle="__full_result__"` in edges.
**How to avoid:** Use `make_edge(source_handle="__full_result__", target_handle="full_result")` for cubes that accept full_result input.

### Pitfall 6: Datetime Timezone Awareness
**What goes wrong:** Tests create naive datetime objects, but signal modules expect timezone-aware datetimes.
**Why it happens:** Using `datetime(2025, 6, 1, 12, 0, 0)` without `tzinfo=timezone.utc`.
**How to avoid:** Always use `datetime(..., tzinfo=timezone.utc)` in test data. The existing test_dark_flight_detector.py does this correctly.

## Code Examples

### Shared conftest.py Fixture Pattern
```python
# backend/tests/conftest.py
from unittest.mock import AsyncMock, MagicMock

import pytest


def make_mock_db_conn(results=None):
    """Create a mock async DB connection context manager.

    Args:
        results: Single MagicMock result or list for side_effect.
    """
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    if results is None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.keys.return_value = []
        mock_conn.execute = AsyncMock(return_value=mock_result)
    elif isinstance(results, list):
        mock_conn.execute = AsyncMock(side_effect=results)
    else:
        mock_conn.execute = AsyncMock(return_value=results)

    return mock_conn
```

### Signal Module Pure Function Test Pattern
```python
# testing score_event (pure function -- no DB)
def test_score_event_jamming_signals():
    from app.signal.rule_based import score_event

    event = {
        "hex": "abc123",
        "source": "integrity_drop",
        "version": 2,
        "nacp_zero": True,
        "nic_zero": True,
        "gva_zero": True,
        "nacv_high": True,
        "has_gps_ok_before": True,
        "median_rssi": -10.0,  # above threshold = good coverage
        "mean_seen_pos": 3.0,  # low = jamming signal
        "msg_rate": 2.0,
        "mean_alt_divergence_ft": 500,
        "max_alt_divergence_ft": 800,
        "entry_lat": 32.0,
        "entry_lon": 34.0,
    }
    coverage_baseline = {}  # empty baseline -- no coverage hole
    scored = score_event(event, coverage_baseline)
    assert scored["jamming_score"] > 6  # strong jamming
    assert scored["spoofing_score"] < 4  # not spoofing
```

### Geo Loader Test Pattern
```python
# test_geo_country_loader.py
def test_classify_point_over_known_country():
    from app.geo.country_loader import classify_point

    # Tel Aviv, Israel
    result = classify_point(32.08, 34.78)
    assert result is not None
    assert result["country"] == "Israel"

def test_classify_point_over_ocean():
    from app.geo.country_loader import classify_point

    # Middle of Atlantic Ocean
    result = classify_point(30.0, -40.0)
    assert result is None

def test_list_countries_has_entries():
    from app.geo.country_loader import list_countries
    countries = list_countries()
    assert len(countries) > 100  # should have ~258
```

### ICAO24 Lookup Test Pattern
```python
# test_icao24_lookup.py
def test_iran_hex_resolves():
    from app.cubes.icao24_lookup import resolve_country_from_hex
    result = resolve_country_from_hex("730000")
    assert result is not None
    country, region = result
    assert country == "Iran"
    assert region == "black"

def test_expand_black_region():
    from app.cubes.icao24_lookup import expand_regions
    countries = expand_regions(["black"])
    assert "Iran" in countries
    assert "Syria" in countries
    assert "Israel" not in countries  # Israel is not black
```

## Cube Test Coverage Matrix

Every cube needs these test categories:

| Cube | Metadata | Empty Guard | Core Logic | Edge Cases | Already Tested |
|------|----------|-------------|------------|------------|----------------|
| echo | trivial | no inputs | echo value | - | No |
| add_numbers | trivial | zero/null | sum result | float edge cases | No |
| count_by_field | category | empty data | groupby+count | missing field, full_result dict | No |
| geo_temporal_playback | category | no data | passthrough | - | No |
| all_flights | DATA_SOURCE | empty result | query building | polygon filter, absolute time | No |
| alison_flights | DATA_SOURCE | empty result | fast/slow path | polygon, positions join | No |
| get_anomalies | DATA_SOURCE | empty flight_ids | query building | min_severity, is_anomaly | No |
| get_flight_course | DATA_SOURCE | empty ids | points mode | lines mode, string split | No |
| get_learned_paths | DATA_SOURCE | no filters | query + geometry | polygon filter, corridor | No |
| filter_flights | FILTER | empty input | tier 1+2 filters | AND logic, polygon | YES (comprehensive) |
| dark_flight_detector | ANALYSIS | empty hex_list | gap detection | airborne vs ground | YES (comprehensive) |
| set_operations | FILTER | empty sets | 3 operations | 3-way, unknown op | YES (comprehensive) |
| squawk_filter | FILTER | empty ids | custom+emergency | dual provider, code-change | No |
| registration_country_filter | FILTER | empty hex_list | include/exclude | unknown country, regions | No |
| area_spatial_filter | FILTER | empty ids | polygon containment | movement classification | No |
| signal_health_analyzer | ANALYSIS | empty hex_list | event detection | classify_mode, target_phase | No |

## Module Test Coverage

| Module | Pure Functions | Async Functions | Already Tested |
|--------|---------------|-----------------|----------------|
| signal/rule_based.py | score_event, classify_event | detect_integrity_events_async, detect_transponder_shutdowns_async, get_coverage_baseline | No |
| signal/kalman.py | kalman_filter, detect_position_jumps, detect_altitude_divergence, physics_cross_validation, classify_flight, haversine_km, latlon_to_enu | fetch_positions_async, fetch_time_range_async, classify_flight_async | No |
| geo/country_loader.py | classify_point, get_country_polygon, list_countries | - | No |
| geo/fir_loader.py | classify_point, get_fir_polygon, list_firs | - | No |
| geo/land_water_loader.py | is_land, classify_point | - | No |
| cubes/icao24_lookup.py | resolve_country_from_hex, resolve_country_from_registration, expand_regions | - | No |

## DB Mocking Strategy Recommendation

**Recommended: Per-test patching with shared helper functions.**

Rationale:
1. **Per-test patching** (not session-level): Each test controls its own mock data. No test pollution. Matches existing patterns exactly.
2. **Shared `make_mock_db_conn()` in conftest.py**: Reduces boilerplate for the ~40 DB-mocking tests while keeping each test self-contained.
3. **Patch target pattern**: Always patch at the import location: `patch("app.cubes.all_flights.engine")`, not `patch("app.database.engine")`. This matches existing test patterns and ensures the mock is applied where the cube accesses it.

## Integration Test Scenarios

Based on actual cube pipelines in the workflow builder:

| Pipeline | Cubes | What to Test |
|----------|-------|-------------|
| FR analysis | AllFlights -> FilterFlights -> GetAnomalies | flight_ids flow, full_result wire |
| Alison filter chain | AlisonFlights -> SquawkFilter -> DarkFlightDetector | hex_list flow, provider=alison |
| Country filtering | AlisonFlights -> RegistrationCountryFilter | hex_list extraction from full_result |
| Spatial analysis | AllFlights -> AreaSpatialFilter -> GetFlightCourse | flight_ids from spatial output |
| Signal analysis | AlisonFlights -> SignalHealthAnalyzer | hex_list flow, event output |
| Set operations | AlisonFlights -> RegistrationCountryFilter -> SetOperations | set intersection of hex lists |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| @pytest.mark.asyncio on each test | asyncio_mode = "auto" | pytest-asyncio 0.21+ | No markers needed on async tests |
| aiohttp test client | httpx.AsyncClient with ASGITransport | httpx 0.23+ | ASGI-native, no server needed |
| monkeypatch for mocks | unittest.mock.patch + AsyncMock | Python 3.8+ | Better async support |

## Open Questions

1. **Signal module realistic test data**
   - What we know: User wants realistic flight data for signal cubes (jamming, spoofing scenarios)
   - What's unclear: Whether to attempt DB queries for real examples or generate synthetic data
   - Recommendation: Generate synthetic data that matches real patterns (from code constants: CHI2_THRESHOLD=13.82, POSITION_JUMP_KM=55.56, ALT_DIVERGENCE_FT=1000). The pure functions are well-specified enough that synthetic data is reliable.

2. **Coverage targets**
   - What we know: All 14 cubes need tests
   - What's unclear: Whether a minimum coverage percentage is desired
   - Recommendation: Aim for behavioral coverage (every code path through each cube), not percentage targets. Focus on: metadata, empty guard, happy path, edge cases for each cube.

## Sources

### Primary (HIGH confidence)
- Project source code: all 18 cube files, 2 signal modules, 4 geo modules, 6 existing test files
- `backend/pyproject.toml`: pytest config with `asyncio_mode = "auto"`
- Phase 15 CONTEXT.md: user decisions and constraints

### Secondary (MEDIUM confidence)
- pytest-asyncio documentation (auto mode behavior)
- unittest.mock documentation (AsyncMock patterns)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - already installed and working in 6 test files
- Architecture: HIGH - directly derived from existing patterns in codebase
- Pitfalls: HIGH - identified from actual code review of each cube
- Test matrix: HIGH - complete enumeration from directory listing

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable -- testing stack does not change)
