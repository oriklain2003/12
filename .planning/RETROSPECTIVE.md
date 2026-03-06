# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Visual Dataflow Workflow Builder

**Shipped:** 2026-03-06
**Phases:** 10 | **Plans:** 23 | **Commits:** 111

### What Was Built
- Full visual dataflow editor with React Flow canvas, draggable cube catalog, parameter editing, and connection validation
- Real-time SSE execution engine with topological sort, per-cube streaming, and live UI status indicators
- 8 production cubes querying live Tracer 42 PostgreSQL (AllFlights, FilterFlights, GetAnomalies, CountByField, GetFlightCourse, GetLearnedPaths, GeoTemporalPlayback + stubs)
- Results display with sortable tables, auto-detected geo columns, Leaflet map, and bidirectional interaction
- Geo-temporal playback widget with animated map, dual-handle timeline, density histogram, and speed controls
- Dashboard with workflow CRUD, Docker deployment with nginx proxy

### What Worked
- 3-day delivery of full-stack application (backend + frontend + Docker) — aggressive but achievable scope
- Phase-per-feature decomposition kept context manageable (each phase had clear, testable goal)
- SSE-first design (no WebSocket) simplified both backend and frontend significantly
- Parameter-level connections (not cube-level) proved essential for flexible pipeline design
- Zustand for state management — lightweight, no boilerplate, perfect for this scale

### What Was Inefficient
- Phase 9 and 10 were gap-closure phases created after the first audit — Filter Flights cube was missed in original Phase 7 scope
- SUMMARY frontmatter `requirements_completed` field was only added to 4 of 23 SUMMARYs — inconsistent tracking
- No VERIFICATION.md files were ever created (0/10 phases) — verification step was skipped during execution
- BACK-08 requirement text became stale after endpoint removal — requirement evolution not tracked alongside code changes

### Patterns Established
- Widget dispatch pattern: CubeDefinition.widget field + ResultsDrawer conditional rendering for custom visualization cubes
- Two-tier filtering pattern: fast metadata check (Tier 1) + expensive track aggregation (Tier 2)
- BaseCube auto-discovery via pkgutil + `__subclasses__()` — zero-registration cube pattern
- GeoJSON [lon, lat] coordinate order convention (not [lat, lon])
- `widget_hint` on ParamDefinition for custom input widgets (polygon map, relative time, datetime)

### Key Lessons
1. Run milestone audits earlier — the v1.0 audit found a missing cube (DATA-02) that required an entire gap-closure phase
2. Track requirements in SUMMARY frontmatter from day one — retrofitting traceability is tedious
3. SQL LIMIT caps in individual cubes should match or reference the global result_row_limit to avoid user confusion
4. SSE endpoints need explicit EventSource close on completion — browser auto-reconnects on server close

### Cost Observations
- Model mix: primarily sonnet for execution, opus for planning/auditing
- Sessions: ~6 sessions across 3 days
- Notable: 23 plans executed in 10 phases — average ~2.3 plans per phase, most plans executed in 2-10 minutes

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Commits | Phases | Key Change |
|-----------|---------|--------|------------|
| v1.0 | 111 | 10 | Initial delivery — established cube system, execution engine, visual editor |

### Cumulative Quality

| Milestone | Tests | Audit Score | Tech Debt Items |
|-----------|-------|-------------|-----------------|
| v1.0 | ~20 | 53/55 | 8 |

### Top Lessons (Verified Across Milestones)

1. Audit early, audit often — gap closure phases are expensive context switches
2. Track requirement completion in SUMMARY frontmatter as you go
