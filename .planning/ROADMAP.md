# Roadmap: Project 12 — Visual Dataflow Workflow Builder

## Milestones

- ✅ **v1.0 Visual Dataflow Workflow Builder** — Phases 1-10 (shipped 2026-03-06)
- 🔲 **v2.0 Advanced Flight Analysis Cubes** — Phases 11-17
- 🔲 **v3.0 AI Workflow Agents** — Phases 18-22

## Phases

<details>
<summary>✅ v1.0 Visual Dataflow Workflow Builder (Phases 1-10) — SHIPPED 2026-03-06</summary>

- [x] Phase 1: Types, Schemas & Project Scaffolding (2/2 plans) — completed 2026-03-03
- [x] Phase 2: Backend Core — Registry, DB, CRUD, Executor (2/2 plans) — completed 2026-03-03
- [x] Phase 3: Async Execution with SSE Progress (1/1 plans) — completed 2026-03-03
- [x] Phase 4: Frontend Canvas, Nodes, Sidebar & Dark Theme (3/3 plans) — completed 2026-03-04
- [x] Phase 5: Workflow Management & Execution Integration (3/3 plans) — completed 2026-03-04
- [x] Phase 6: Results Display — Tables, Map, Bidirectional Interaction (2/2 plans) — completed 2026-03-04
- [x] Phase 7: Real DB Cubes, End-to-End & Docker (3/3 plans) — completed 2026-03-04
- [x] Phase 8: Geo-Temporal Playback, Learned Paths & Flight Course Cubes (4/4 plans) — completed 2026-03-05
- [x] Phase 9: Filter Flights Cube — Gap Closure (1/1 plans) — completed 2026-03-05
- [x] Phase 10: Audit Remediation — Gap Closure (2/2 plans) — completed 2026-03-05

**Full details:** .planning/milestones/v1.0-ROADMAP.md

</details>

<details>
<summary>🔲 v2.0 Advanced Flight Analysis Cubes (Phases 11-17) — In Progress</summary>

### Phase 11: Simple Filters — Squawk and Registration Country Cubes

**Goal:** Implement `alison_flights` data source, `squawk_filter`, and `registration_country_filter` cubes — the Alison provider pipeline foundation plus two filter cubes with dual-provider squawk support and ICAO24 country resolution.
**Cubes:** `alison_flights`, `squawk_filter`, `registration_country_filter`
**Depends on:** v1.0 (cube framework)
**Plans:** 3/3 plans complete

Plans:
- [ ] 11-01-PLAN.md — Alison data source cube + ICAO24 lookup module
- [ ] 11-02-PLAN.md — Squawk filter cube (dual-provider, code-change detection)
- [ ] 11-03-PLAN.md — Registration country filter cube + integration verification

### Phase 12: Area Spatial Filter with Geo Data Research

**Goal:** Implement `area_spatial_filter` cube with dual-provider polygon filtering, movement classification (landing/takeoff/cruise), and build geo data loader modules (country boundaries, FIR, land/water) for future spatial modes.
**Cubes:** `area_spatial_filter`
**Depends on:** Phase 11
**Plans:** 2/2 plans executed

Plans:
- [x] 12-01-PLAN.md — AreaSpatialFilterCube with dual-provider support and movement classification
- [x] 12-02-PLAN.md — Geo data loaders (country boundaries, FIR, land/water polygons)

### Phase 13: Flight Plans Source and Compliance Analyzer

**Goal:** Implement `flight_plans_source` (FlightAware AeroAPI v4) and `flight_plan_compliance_analyzer` cubes.
**Cubes:** `flight_plans_source`, `flight_plan_compliance_analyzer`
**Depends on:** Phase 11
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd:plan-phase 13 to break down)

### Phase 14: Signal Health Analyzer

**Goal:** Implement `signal_health_analyzer` ANALYSIS cube with real detection logic ported from `scripts/` — rule-based integrity/shutdown detection + Kalman filter anomaly detection, Alison provider only, read-only.
**Cubes:** `signal_health_analyzer`
**Depends on:** Phase 11
**Plans:** 3/3 plans complete

Plans:
- [ ] 14-01-PLAN.md — Rule-based detection module (async port) + numpy/scipy dependencies
- [ ] 14-02-PLAN.md — Kalman detection module (async port)
- [ ] 14-03-PLAN.md — SignalHealthAnalyzerCube orchestrating both detection layers

### Phase 15: Cube unit tests and integration tests for current and future cubes

**Goal:** Comprehensive test suite for all 14+ cubes, signal detection modules (rule_based, kalman), geo loaders (country, FIR, land/water), icao24_lookup, and multi-cube integration pipelines through the WorkflowExecutor. Safety net for current and future cube development.
**Requirements**: TBD
**Depends on:** Phase 14
**Plans:** 7/7 plans complete

Plans:
- [ ] 15-01-PLAN.md — Shared conftest.py + pure-logic cube tests (echo, add_numbers, count_by_field, geo_temporal_playback) + icao24_lookup
- [x] 15-02-PLAN.md — Data-source cube tests (all_flights, alison_flights, get_anomalies)
- [ ] 15-03-PLAN.md — Data-source cube tests (get_flight_course, get_learned_paths)
- [ ] 15-04-PLAN.md — v2.0 filter cube tests (squawk_filter, registration_country_filter, area_spatial_filter)
- [ ] 15-05-PLAN.md — Geo loader tests (country_loader, fir_loader, land_water_loader)
- [ ] 15-06-PLAN.md — Signal module tests (rule_based, kalman)
- [ ] 15-07-PLAN.md — SignalHealthAnalyzerCube tests + integration pipeline tests

### Phase 16: Fix signal health cube bugs and performance

**Goal:** Fix performance (4*N queries to 3 batch queries), bugs (missing n_severe_alt_div, _serialize_datetimes overhead, TTL baseline), and architecture issues (event loop blocking, startup baseline) in the signal health detection system.
**Requirements**: SH-BATCH, SH-BASELINE, SH-KALMAN, SH-ORCHESTRATOR, SH-NSEVERE, SH-TESTS
**Depends on:** Phase 15
**Plans:** 3/3 plans complete

Plans:
- [ ] 16-01-PLAN.md — Batch query functions in rule_based.py + kalman.py + lifespan hook
- [ ] 16-02-PLAN.md — Restructure SignalHealthAnalyzerCube execute() for batch architecture
- [ ] 16-03-PLAN.md — Update signal test suite for batch signatures

### Phase 17: Optimize squawk filter cube performance

**Goal:** Apply SQL pushdown, set-based accumulation, and loop hoisting optimizations to SquawkFilterCube to eliminate unnecessary network bandwidth and reduce per-row CPU overhead.
**Requirements**: SQ-SQL-PUSHDOWN, SQ-SET-ACCUM, SQ-LOOP-HOIST, SQ-TEST-UPDATE
**Depends on:** Phase 16
**Plans:** 1/1 plans complete

Plans:
- [ ] 17-01-PLAN.md — SQL pushdown + set accumulation + loop hoisting + test updates

</details>

### v3.0 AI Workflow Agents (Phases 18-22)

- [x] **Phase 18: Agent Infrastructure** — Gemini client, SSE streaming, skill files, tool dispatch, context management, mission persistence (completed 2026-03-24)
- [x] **Phase 19: Cube Expert + Validation Agent** — Two-tier catalog sub-agent, structural validation checks, pre-run validation trigger (completed 2026-03-24)
- [x] **Phase 20: Canvas Agent** — Chat panel UI, three modes (optimize/fix/general), canvas diff application, agent streaming (completed 2026-03-24)
- [ ] **Phase 21: Build Wizard Agent** — Wizard page with option cards, mission discovery, workflow generation, intent preview
- [ ] **Phase 22: Results Interpreter** — Post-execution analysis, mission-context explanation, fallback generic framing

## Phase Details

### Phase 18: Agent Infrastructure
**Goal**: The application has a working Gemini LLM layer that all agents can build on — async client, SSE streaming, tool dispatch, context management, and skill files
**Depends on**: Phase 17 (existing backend)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07
**Success Criteria** (what must be TRUE):
  1. A developer can send a test prompt to a new `/api/agent/chat` SSE endpoint and receive a streaming Gemini response without blocking the existing workflow execution endpoints
  2. Agent tool calls resolve via internal Python function dispatch — the Gemini client calls `list_cubes_summary` or `get_cube_detail` and gets back the correct data without making HTTP calls
  3. A skill file (system prompt) for each agent persona loads from disk at startup and is injected into every agent request without duplication in the request body
  4. Sending 20 chat turns does not cause a context explosion — history is pruned at the token threshold and the latest turn still receives a coherent response
  5. Mission context (analysis intent, parameters) persists in the workflow JSONB metadata and is retrievable in subsequent sessions
**Plans**: 4 plans

Plans:
- [x] 18-01-PLAN.md — Gemini client singleton + Settings extension + google-genai install
- [x] 18-02-PLAN.md — Skill files (system brief + 5 agent personas) + loader module
- [x] 18-03-PLAN.md — Tool registry + dispatcher + context management + placeholder catalog tools
- [x] 18-04-PLAN.md — SSE chat endpoint + sessions + lifespan wiring + integration tests

### Phase 19: Cube Expert + Validation Agent
**Goal**: Analysts can run pre-flight validation before executing a workflow and see human-readable explanations of structural issues; agents have a reliable two-tier catalog tool to look up cubes
**Depends on**: Phase 18
**Requirements**: CUBE-01, CUBE-02, CUBE-03, VALID-01, VALID-02, VALID-03
**Success Criteria** (what must be TRUE):
  1. Running validation on a workflow with a missing required parameter shows a specific, named explanation of which cube and which parameter is the problem — not a generic error
  2. Running validation on a structurally correct workflow returns a clean result with zero issues, not a false positive
  3. Validation runs automatically when the user clicks Run — if issues are found, execution is blocked and the issues panel opens before any cube executes
  4. The Cube Expert sub-agent, given a description like "I need to filter flights by geographic area", returns the correct cube name (`area_spatial_filter`) with reasoning — not a hallucinated cube name
  5. The two-tier catalog lookup returns only summaries on the first call (no parameter detail), and loads full parameter definitions only when a specific cube name is requested
**Plans**: 3 plans

Plans:
- [x] 19-01-PLAN.md — Validation engine + schemas + POST /api/agent/validate endpoint + tests
- [x] 19-02-PLAN.md — Cube Expert class + find_cubes_for_task tool + tests
- [x] 19-03-PLAN.md — Frontend IssuesPanel + pre-run validation trigger + node highlighting

### Phase 20: Canvas Agent
**Goal**: Analysts working in the editor can open a chat panel, describe what they want to change, and see the agent apply diffs to the canvas — without breaking existing node connections or workflow state
**Depends on**: Phase 18, Phase 19
**Requirements**: CANVAS-01, CANVAS-02, CANVAS-03, CANVAS-04, CANVAS-05, CANVAS-06, CANVAS-07
**Success Criteria** (what must be TRUE):
  1. The chat panel opens and closes from the editor without covering the canvas — it appears as a collapsible sidebar with a visible mode badge (Optimize / Fix / General)
  2. In Error-Fix mode, the agent reads the error output from the last run and suggests a specific corrective action for the failing cube — not a generic "check your parameters" response
  3. When the agent suggests a canvas change and the user accepts it, the canvas updates atomically — all proposed nodes and edges appear together, or none do, with no partial broken state
  4. After an agent applies a diff, the user can discard the change by reloading the last saved workflow — the canvas returns to exactly the pre-agent state
  5. In Optimize mode, the agent reads the current workflow graph and suggests a specific improvement (e.g., removing a redundant filter step) with reasoning tied to the actual cubes present
**Plans**: 4 plans

Plans:
- [x] 20-01-PLAN.md — Backend canvas tools + ToolContext/schema extension + tests
- [x] 20-02-PLAN.md — Frontend store extensions (applyAgentDiff, chat state) + SSE client
- [x] 20-03-PLAN.md — ChatPanel UI components (8 components in Chat/ directory)
- [x] 20-04-PLAN.md — EditorPage/Toolbar wiring + auto-open Fix mode + skill file update

### Phase 21: Build Wizard Agent
**Goal**: A new analyst with no existing workflow can use the wizard to answer 3-5 guided questions and have a complete, valid workflow generated on the canvas — ready to run without manual parameter editing
**Depends on**: Phase 18, Phase 19
**Requirements**: BUILD-01, BUILD-02, BUILD-03, BUILD-04, BUILD-05
**Success Criteria** (what must be TRUE):
  1. The wizard page presents clickable option cards at each step — the analyst never types free text to describe what cubes they need
  2. After completing all wizard steps, the analyst sees an intent preview summarizing what will be built (cube names, connections, key parameters) before any canvas changes occur
  3. The generated workflow loads onto the canvas with all required parameters pre-filled — the analyst can click Run immediately without touching any parameter editor
  4. The Validation Agent runs automatically on the generated workflow before it is presented — a workflow with invalid connections is never delivered to the canvas
  5. The mission description and analysis intent from the wizard are saved to the workflow metadata — visible in the workflow title and accessible to the Results Interpreter later
**Plans**: 3 plans

Plans:
- [x] 21-01-PLAN.md — Backend wizard tools (present_options, show_intent_preview, generate_workflow) + skill file + model routing
- [x] 21-02-PLAN.md — Frontend WizardPage + Wizard components (WizardChat, WizardWelcome, OptionCards, MiniGraph, WizardInput) + types + API extension
- [ ] 21-03-PLAN.md — Dashboard two-button split + /wizard routing + human verification

### Phase 22: Results Interpreter
**Goal**: After a workflow executes, analysts can ask for an interpretation of the results and receive an explanation grounded in their stated mission — not a generic statistical summary
**Depends on**: Phase 21
**Requirements**: RESULT-01, RESULT-02, RESULT-03
**Success Criteria** (what must be TRUE):
  1. An "Interpret Results" button appears in the results drawer after a successful workflow execution, and clicking it triggers the interpreter without navigating away from the results
  2. For a workflow created via the Build Wizard, the interpretation references the analyst's original mission intent (e.g., "You were looking for squawk 7700 activity in the Jordan FIR — 3 matching flights were found") rather than just describing the data schema
  3. For a workflow with no wizard-derived mission context, the interpretation still produces a useful flight-analysis framing (e.g., "This result contains 47 flights with anomaly scores above threshold — the top anomaly type is...") rather than refusing to interpret
**Plans**: 2 plans

Plans:
- [ ] 22-01-PLAN.md — Backend: InterpretRequest schema + interpreter tools + skill files + SSE interpret endpoint
- [ ] 22-02-PLAN.md — Frontend: InterpretPanel component + ResultsDrawer integration + streamInterpret API + human verification

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|---------------|--------|-----------|
| 1. Types & Schemas | v1.0 | 2/2 | Complete | 2026-03-03 |
| 2. Backend Core | v1.0 | 2/2 | Complete | 2026-03-03 |
| 3. SSE Execution | v1.0 | 1/1 | Complete | 2026-03-03 |
| 4. Frontend Canvas | v1.0 | 3/3 | Complete | 2026-03-04 |
| 5. Workflow Mgmt | v1.0 | 3/3 | Complete | 2026-03-04 |
| 6. Results Display | v1.0 | 2/2 | Complete | 2026-03-04 |
| 7. Real DB + Docker | v1.0 | 3/3 | Complete | 2026-03-04 |
| 8. Geo-Temporal | v1.0 | 4/4 | Complete | 2026-03-05 |
| 9. Filter Flights | v1.0 | 1/1 | Complete | 2026-03-05 |
| 10. Audit Remediation | v1.0 | 2/2 | Complete | 2026-03-05 |
| 11. Squawk & Reg Country | v2.0 | 3/3 | Complete | 2026-03-06 |
| 12. Area Spatial Filter | v2.0 | 2/2 | Complete | 2026-03-08 |
| 13. Flight Plans & Compliance | v2.0 | 0/0 | Pending | — |
| 14. Signal Health Analyzer | v2.0 | 3/3 | Complete | 2026-03-08 |
| 15. Cube Tests | v2.0 | 7/7 | Complete | 2026-03-09 |
| 16. Signal Health Fixes | v2.0 | 3/3 | Complete | 2026-03-13 |
| 17. Squawk Optimization | v2.0 | 1/1 | Complete | 2026-03-13 |
| 18. Agent Infrastructure | v3.0 | 4/4 | Complete    | 2026-03-24 |
| 19. Cube Expert + Validation | v3.0 | 3/3 | Complete   | 2026-03-24 |
| 20. Canvas Agent | v3.0 | 4/4 | Complete    | 2026-03-25 |
| 21. Build Wizard Agent | v3.0 | 2/3 | In Progress|  |
| 22. Results Interpreter | v3.0 | 0/2 | Not started | — |

---
*Roadmap created: 2026-03-03*
*v1.0 shipped: 2026-03-06*
*v2.0 roadmap added: 2026-03-06*
*v3.0 roadmap added: 2026-03-22*
