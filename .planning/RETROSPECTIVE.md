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

## Milestone: v3.0 — AI Workflow Agents

**Shipped:** 2026-03-27
**Phases:** 5 | **Plans:** 16 | **Commits:** 89

### What Was Built
- Gemini LLM integration layer with async SSE streaming, 5 skill files (agent personas), decorator-based tool registry, and context management with history pruning
- Structural workflow validation engine (7 rules: missing params, dangling handles, type mismatches, cycles, etc.) with pre-run blocking and visual IssuesPanel with node highlighting
- Canvas Agent chat panel with 3 modes (optimize/fix/general), atomic applyAgentDiff canvas updates with snapshot-based undo, and auto-open Fix mode on execution failure
- Build Wizard with guided option cards, mission discovery Q&A, intent preview with mini-graph, and one-click workflow generation with automatic validation
- Results Interpreter with mission-context explanation, fallback cube-type framing, and seamless handoff to follow-up Q&A via canvas chat

### What Worked
- 4-day delivery of 5 interconnected agent phases (+8,249 LOC) — aggressive but well-scoped
- One-way dependency rule (agents import from existing packages, never reverse) kept existing system stable throughout
- Manual tool dispatch pattern (not Gemini auto function calling) gave reliable control over tool→response flow
- Two-tier catalog design prevented context explosion — summaries for browsing, full definitions on demand
- Client-carried history (stateless agents) eliminated need for server-side session store
- Wizard option cards (no free text for cube selection) completely prevented LLM hallucination on analyst input

### What Was Inefficient
- VERIFICATION.md files skipped for 4/5 phases (same pattern as v1.0) — only Phase 20 has formal verification
- CubeExpert class was designed as a sub-agent but ended up as dead code — agents call catalog tools directly via registry; should have been caught during Phase 19 planning
- validation_agent.md skill file loaded at startup but persona never invoked — validation is pure rule-based, not LLM-generated as originally specified
- POST /api/agent/mission endpoint built but has no frontend caller — mission context works only through wizard path
- Milestone audit discovered gaps late — should have audited after each phase, not at the end

### Patterns Established
- `@agent_tool` decorator pattern for tool registration with auto-schema generation from type hints
- `ToolContext` dataclass for injecting workflow state into tool functions without changing signatures
- SSE streaming for both workflow execution and agent responses — same pattern, different endpoints
- `applyAgentDiff` with `pushSnapshot` for safe agent-driven canvas mutations
- Persona-based model routing: `pro_personas` set in router.py for heavyweight tasks, flash for everything else
- One-shot SSE + follow-up persona pattern for Results Interpreter → results_followup handoff

### Key Lessons
1. Formal verification should be automated or templated — manual VERIFICATION.md creation is consistently skipped under time pressure
2. Sub-agent designs should be validated against actual usage patterns before building — CubeExpert was over-engineered for the actual tool-calling workflow
3. Mission context persistence through workflow JSONB metadata was the right call — simple, queryable, no separate store
4. Wizard skill file required 2 rewrites during Phase 21 — LLM prompting is iterative, plan for it
5. The `pro_personas` set pattern is extensible and correct — easy to add new personas to heavyweight model routing

### Cost Observations
- Model mix: primarily sonnet for execution, opus for planning/auditing/milestone-completion
- Sessions: ~8 sessions across 4 days
- Notable: 16 plans in 5 phases — average 3.2 plans per phase; phases 18 and 20 (4 plans each) were the heaviest

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Commits | Phases | Key Change |
|-----------|---------|--------|------------|
| v1.0 | 111 | 10 | Initial delivery — established cube system, execution engine, visual editor |
| v3.0 | 89 | 5 | AI agent layer — Gemini-powered build wizard, canvas chat, validation, results interpreter |

### Cumulative Quality

| Milestone | Tests | Audit Score | Tech Debt Items |
|-----------|-------|-------------|-----------------|
| v1.0 | ~20 | 53/55 | 8 |
| v3.0 | ~18 (agent integration) | 7/28 verified (functional: 28/28) | 8 |

### Top Lessons (Verified Across Milestones)

1. Audit early, audit often — gap closure phases are expensive context switches (v1.0, v3.0)
2. Track requirement completion in SUMMARY frontmatter as you go (v1.0)
3. VERIFICATION.md is consistently skipped — automate or template it (v1.0: 0/10, v3.0: 1/5)
4. Sub-agent/abstraction designs should be validated against actual usage before building — dead code results otherwise (v3.0: CubeExpert)
