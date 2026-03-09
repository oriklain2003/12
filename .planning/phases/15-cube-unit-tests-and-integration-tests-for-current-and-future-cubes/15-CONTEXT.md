# Phase 15: Cube Unit Tests and Integration Tests - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Comprehensive test suite for all existing cubes (14), signal detection modules (rule_based, kalman), geo loaders, and multi-cube integration through the workflow executor. Safety net for current and future cube development.

</domain>

<decisions>
## Implementation Decisions

### Test scope and priority
- All 14 cubes get tested equally — no prioritization, every cube gets unit tests
- Signal modules (rule_based.py, kalman.py) tested independently as well as through their cube
- Geo loaders (country_loader, fir_loader, land_water_loader) tested independently

### Integration test boundaries
- Integration tests = multi-cube pipeline execution through the WorkflowExecutor
- Test realistic cube chains (e.g., data_source → filter → analysis)
- No live DB integration tests — mock all DB access

### Test data and fixtures
- Use realistic flight data for test fixtures
- For signal cubes (jamming, spoofing, transponder gaps): create mock data that represents real scenarios
- Strategy: search the DB for real examples first; if too hard to extract, invent realistic mock data
- Existing cubes with simpler inputs: inline data is fine (following existing test patterns)

### Claude's Discretion
- DB mocking strategy (session-level patching, shared fixtures, or mix)
- Test file organization (one file per cube vs grouped)
- Fixture sharing approach
- Assertion granularity

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `test_dark_flight_detector.py`: Pattern for cube metadata tests + position data helpers (`make_position`, `positions_to_rows`)
- `test_executor.py`: Pattern for workflow graph construction (`make_node`, `make_edge`) + executor testing
- `test_filter_flights.py`, `test_sse_stream.py`, `test_stream_graph.py`: Additional test patterns

### Established Patterns
- pytest-asyncio with `asyncio_mode = "auto"` — all async tests work without markers
- `unittest.mock.AsyncMock` + `patch` for DB isolation
- Helper functions at top of test files for building test data
- Direct cube instantiation (`CubeClass()`) for unit tests

### Integration Points
- `backend/app/engine/executor.py` — WorkflowExecutor for integration tests
- `backend/app/engine/registry.py` — CubeRegistry for cube discovery
- `backend/app/cubes/base.py` — BaseCube interface all cubes implement
- `backend/app/signal/` — rule_based.py and kalman.py modules
- `backend/app/geo/` — loader modules with bundled GeoJSON data

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-cube-unit-tests-and-integration-tests-for-current-and-future-cubes*
*Context gathered: 2026-03-09*
