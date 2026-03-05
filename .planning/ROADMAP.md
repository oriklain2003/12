# Roadmap: Project 12 — Visual Dataflow Workflow Builder

**Created:** 2026-03-03
**Phases:** 10
**Requirements covered:** 55/55 (48 v1 + 7 Phase 8)

## Phase Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Types, Schemas & Project Scaffolding | Foundational data contracts + both projects bootable | CUBE-01, CUBE-02, CUBE-03, BACK-01, BACK-02, FRONT-01 | 3 | 1/1 | Complete   | 2026-03-03 | Complete   | 2026-03-03 | 4 | 3/3 | Complete   | 2026-03-03 | Background execution with real-time streaming | BACK-13 | 2 |
| 4 | Frontend Canvas, Nodes, Sidebar & Dark Theme | Full visual editor with drag, configure, connect | FRONT-02 to FRONT-12 | 5 | 3/3 | Complete   | 2026-03-04 | Full loop — dashboard, save/load, run with live status | WFLOW-01 to WFLOW-08 | 4 |
| 6 | 2/2 | Complete   | 2026-03-04 | 5 |
| 7 | 3/3 | Complete   | 2026-03-04 | 5 |

---

## Phase 1: Types, Schemas & Project Scaffolding

**Goal:** Foundational data contracts + both projects bootable

**Requirements:** CUBE-01, CUBE-02, CUBE-03, BACK-01, BACK-02, FRONT-01

**Plans:** 2 plans

Plans:
- [x] 01-01-PLAN.md — Backend cube schemas, BaseCube abstract class, and FastAPI app entry point
- [x] 01-02-PLAN.md — Frontend Vite+React scaffold and TypeScript type mirrors

**Key files:**
- `backend/pyproject.toml` — Python project with FastAPI, SQLAlchemy, asyncpg dependencies
- `backend/app/main.py` — FastAPI app with CORS, health endpoint
- `backend/app/config.py` — Settings from .env via pydantic-settings
- `backend/app/database.py` — Async SQLAlchemy engine + session factory
- `backend/app/schemas/cube.py` — ParamType, CubeCategory, ParamDefinition, CubeDefinition
- `backend/app/schemas/workflow.py` — WorkflowNode, WorkflowEdge, WorkflowGraph, CRUD schemas
- `backend/app/cubes/base.py` — BaseCube abstract class
- `frontend/package.json` — React 18, @xyflow/react, Zustand, Leaflet, Vite
- `frontend/vite.config.ts` — API proxy to backend
- `frontend/src/main.tsx`, `frontend/src/App.tsx` — Entry point
- `frontend/src/types/cube.ts`, `frontend/src/types/workflow.ts` — TypeScript type mirrors

**Success criteria:**
1. `cd backend && uv run uvicorn app.main:app` starts and GET /health returns 200
2. `cd frontend && pnpm dev` starts and browser shows "Project 12" page
3. TypeScript compiles clean with `pnpm tsc --noEmit`

---

## Phase 2: Backend Core — Registry, DB, CRUD, Executor

**Goal:** Full backend API functional via curl/Postman

**Requirements:** BACK-03, BACK-04, BACK-05, BACK-06, BACK-07, BACK-08, BACK-09, BACK-10, BACK-11, BACK-12

**Plans:** 2/2 plans complete

Plans:
- [ ] 02-01-PLAN.md — CubeRegistry, stub cubes, Workflow model, Alembic migration, catalog + CRUD API
- [ ] 02-02-PLAN.md — WorkflowExecutor engine, run endpoint, all_flights production cube

**Key files:**
- `backend/app/engine/registry.py` — CubeRegistry with auto-discovery of BaseCube subclasses
- `backend/app/engine/executor.py` — WorkflowExecutor: topo sort, cycle detection, input resolution, Full Result, row limiting
- `backend/app/models/workflow.py` — SQLAlchemy Workflow model (UUID, name, graph_json JSONB)
- `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/001_create_workflows.py`
- `backend/app/routers/cubes.py` — GET /api/cubes/catalog
- `backend/app/routers/workflows.py` — Full CRUD + run endpoint
- `backend/app/cubes/echo_cube.py` — Stub cube echoing input
- `backend/app/cubes/add_numbers.py` — Stub cube adding two numbers
- `backend/app/cubes/all_flights.py` — Production cube querying Tracer 42 flight metadata

**Success criteria:**
1. GET /api/cubes/catalog returns echo + add_numbers + all_flights cube definitions
2. Workflow CRUD works (create -> list -> get -> update -> delete)
3. POST /api/workflows/{id}/run with echo->echo graph returns correct chained results
4. Workflow graph containing a cycle returns 400 error

---

## Phase 3: Async Execution with SSE Progress

**Goal:** Background execution with real-time per-cube status streaming

**Requirements:** BACK-13

**Plans:** 1/1 plans complete

Plans:
- [ ] 03-01-PLAN.md — CubeStatusEvent schema, stream_graph async generator, SSE route handler + tests

**Key files:**
- `backend/app/engine/executor.py` — Refactor execute() to async generator yielding CubeStatusEvent
- `backend/app/schemas/execution.py` — CubeStatusEvent model (node_id, status, outputs, error)
- `backend/app/routers/workflows.py` — GET /api/workflows/{id}/run/stream SSE endpoint via sse-starlette

**Success criteria:**
1. curl to SSE endpoint shows streaming events: `data: {"node_id":"...", "status":"running"}` then `data: {"node_id":"...", "status":"done", "outputs":{...}}`
2. Events arrive in real-time as each cube executes, not buffered until completion

---

## Phase 4: Frontend Canvas, Nodes, Sidebar & Dark Theme

**Goal:** Full visual editor — drag cubes, configure params, connect nodes

**Requirements:** FRONT-02, FRONT-03, FRONT-04, FRONT-05, FRONT-06, FRONT-07, FRONT-08, FRONT-09, FRONT-10, FRONT-11, FRONT-12

**Plans:** 3/3 plans complete

Plans:
- [ ] 04-01-PLAN.md — Fix TypeScript types, dark theme CSS, glass effects, API client layer
- [ ] 04-02-PLAN.md — Zustand flow store, CubeNode components (handles, param editors, results preview)
- [ ] 04-03-PLAN.md — React Flow canvas, collapsible sidebar catalog, toolbar, connection validation, App wiring

**Key files:**
- `frontend/src/styles/theme.css` — Dark theme CSS variables
- `frontend/src/styles/glass.css` — Liquid glass utility classes (backdrop-filter: blur(12px) saturate(150%))
- `frontend/src/api/client.ts` — Fetch wrapper with base URL
- `frontend/src/api/cubes.ts`, `frontend/src/api/workflows.ts` — API functions
- `frontend/src/store/flowStore.ts` — Zustand store (nodes, edges, catalog, results, status)
- `frontend/src/components/Canvas/FlowCanvas.tsx` — React Flow wrapper with drop handler
- `frontend/src/components/CubeNode/CubeNode.tsx` — Custom node with handles, fields, status indicator
- `frontend/src/components/CubeNode/ParamHandle.tsx` — Color-coded handle by ParamType
- `frontend/src/components/CubeNode/ParamField.tsx` — Inline editor (hidden when connected)
- `frontend/src/components/CubeNode/ResultsPanel.tsx` — Compact results preview
- `frontend/src/components/Sidebar/CubeCatalog.tsx` — Grouped, draggable, searchable catalog
- `frontend/src/components/Toolbar/Toolbar.tsx` — Run, Save, name, dashboard link

**Success criteria:**
1. Dark canvas with grid background, sidebar with cube catalog grouped by category
2. Drag cube from sidebar → styled glass node appears on canvas at drop position
3. Input handles on left (color-coded), output handles + Full Result on right
4. Typing param values persists in Zustand store
5. Connecting nodes creates styled edges; type mismatch shown as dashed orange edge
6. Full Result handle only connects to inputs with accepts_full_result=true; incompatible connections prevented
7. Sidebar collapses/expands via toggle button

---

## Phase 5: Workflow Management & Execution Integration

**Goal:** Full loop — dashboard, save/load, run with live status

**Requirements:** WFLOW-01, WFLOW-02, WFLOW-03, WFLOW-04, WFLOW-05, WFLOW-06, WFLOW-07, WFLOW-08

**Plans:** 3/3 plans complete

Plans:
- [ ] 05-01-PLAN.md — React Router setup, Zustand store extensions (workflow metadata + execution state), EditorPage extraction
- [ ] 05-02-PLAN.md — Dashboard page with workflow card grid, rename, delete, navigation
- [ ] 05-03-PLAN.md — SSE execution hook, Toolbar save/run/progress wiring, CubeNode status indicators, keyboard shortcuts, canvas locking

**Key files:**
- `frontend/src/main.tsx` — React Router with createBrowserRouter (/, /workflow/:id, /workflow/new)
- `frontend/src/pages/DashboardPage.tsx` — Dashboard with card grid layout
- `frontend/src/pages/EditorPage.tsx` — Canvas editor page with load-on-mount
- `frontend/src/types/execution.ts` — CubeStatusEvent TypeScript type
- `frontend/src/hooks/useWorkflowSSE.ts` — EventSource hook parsing SSE events
- `frontend/src/store/flowStore.ts` — Extended with workflow metadata, execution state, save/load/run actions
- `frontend/src/components/Toolbar/Toolbar.tsx` — Wired save/run, progress bar, keyboard shortcuts
- `frontend/src/components/CubeNode/CubeNode.tsx` — Execution status indicators + error banner
- `frontend/src/components/Canvas/FlowCanvas.tsx` — Canvas locking during execution

**Success criteria:**
1. Dashboard lists workflows with create/rename/delete functionality
2. Build flow → Save → appears on dashboard → reopen → same state restored
3. Run shows real-time status (pending → running → done/error) on each CubeNode
4. Ctrl+S saves, Ctrl+Enter runs, Delete removes selected nodes/edges
5. Overall pipeline progress bar shows "X/Y cubes completed" in toolbar during execution

---

## Phase 6: Results Display — Tables, Map, Bidirectional Interaction

**Goal:** Rich results with tables from JSON + map for geo data

**Requirements:** RSLT-01, RSLT-02, RSLT-03

**Plans:** 2/2 plans complete

Plans:
- [ ] 06-01-PLAN.md — Geo column detection utility, sortable results table, store extension for drawer state
- [ ] 06-02-PLAN.md — Leaflet map component, results drawer orchestrator with resizable split, EditorPage + CubeNode wiring

**Key files:**
- `frontend/src/utils/geoDetect.ts` — Detect lat/lon column pairs in result data
- `frontend/src/components/Results/ResultsTable.tsx` — Auto-detect columns from JSON, sortable headers, row highlighting
- `frontend/src/components/Results/ResultsTable.css` — Table dark theme styles
- `frontend/src/components/Results/ResultsMap.tsx` — Leaflet map with CartoDB dark tiles, GeoJSON layer, circle markers, flyTo
- `frontend/src/components/Results/ResultsMap.css` — Map container sizing
- `frontend/src/components/Results/ResultsDrawer.tsx` — Bottom drawer with table + map side by side, resizable split divider
- `frontend/src/components/Results/ResultsDrawer.css` — Drawer slide animation, split layout styles
- `frontend/src/store/flowStore.ts` — Extended with selectedResultNodeId for drawer trigger
- `frontend/src/pages/EditorPage.tsx` — Canvas area wrapper with ResultsDrawer mounted
- `frontend/src/components/CubeNode/CubeNode.tsx` — Header click handler opens drawer

**Success criteria:**
1. Results render as scrollable table with auto-detected columns and sortable headers
2. Rows with lat/lon coordinate pairs show Leaflet map panel alongside table
3. Click map marker → highlight + scroll to corresponding table row
4. Click table row → map flies to that location
5. Truncation warning displayed when results exceed 100 rows
6. Resizable split between table and map via draggable divider
7. Drawer slides up from bottom of canvas, taking 1/3 height

---

## Phase 7: Real DB Cubes, End-to-End & Docker

**Goal:** Working pipeline with real Tracer 42 data + deployable containers

**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DEPL-01, DEPL-02, DEPL-03

**Plans:** 3/3 plans complete

Plans:
- [ ] 07-01-PLAN.md — Enhance AllFlights cube + add GetAnomalies and CountByField cubes
- [ ] 07-02-PLAN.md — Polygon map drawing widget for geofence input on AllFlights
- [ ] 07-03-PLAN.md — Docker containerization (backend + frontend Dockerfiles, nginx, docker-compose)

**Key files:**
- `backend/app/cubes/all_flights.py` — Enhanced with airport/region filters and airline output columns
- `backend/app/cubes/get_anomalies.py` — Queries research.anomaly_reports for flight_ids
- `backend/app/cubes/count_by_field.py` — Pandas groupby aggregation
- `frontend/src/components/CubeNode/PolygonMapWidget.tsx` — Leaflet overlay for geofence drawing
- `backend/Dockerfile` — Multi-stage: uv sync → slim Python runtime
- `frontend/Dockerfile` — Multi-stage: pnpm build → nginx serving SPA
- `frontend/nginx.conf` — Serves SPA, proxies /api to backend
- `docker-compose.yml` — Backend + frontend services with .env

**Success criteria:**
1. AllFlights (168h) → GetAnomalies → CountByField pipeline returns real data
2. Results table shows real flight_ids, callsigns, airlines from database
3. Map shows markers at flight origin/destination lat/lon positions
4. Count By Field groups by airline and shows counts table
5. Polygon widget draws geofence on map for AllFlights filtering
6. `docker-compose up --build` → full app accessible at localhost:3000

**End-to-end verification:**
1. Open /workflow/new
2. Drag All Flights → set time_range_seconds=604800
3. Drag Get Anomalies → connect flight_ids from All Flights
4. Drag Count By Field → connect Full Result from All Flights, set group_by_field=airline
5. Run → watch live status → see real results in tables + map
6. Save → dashboard → reopen → verify state preserved

---

## Phase 8: Geo-Temporal Playback, Learned Paths & Flight Course Cubes

**Goal:** Three new cubes (Get Flight Course, Get Learned Paths, Geo-Temporal Playback) plus visualization infrastructure enabling output cubes to render custom widgets in ResultsDrawer, with global row cap bumped to 10,000.

**Requirements:** GEO-01, GEO-02, GEO-03, GEO-04, GEO-05, GEO-06, GEO-07

**Depends on:** Phase 7

**Plans:** 4/4 plans complete

Plans:
- [ ] 08-01-PLAN.md — Widget field on CubeDefinition (Python + TS), row cap bump, Get Flight Course cube
- [ ] 08-02-PLAN.md — Install Shapely, Get Learned Paths cube with corridor buffering
- [ ] 08-03-PLAN.md — Geo-Temporal Playback cube (backend) + ResultsDrawer widget dispatch
- [ ] 08-04-PLAN.md — GeoPlaybackWidget (animated Leaflet map + timeline + histogram)

**Key files:**
- `backend/app/schemas/cube.py` — CubeDefinition with `widget` field
- `backend/app/cubes/base.py` — BaseCube passes `widget` through definition property
- `backend/app/config.py` — result_row_limit bumped to 10,000
- `frontend/src/types/cube.ts` — CubeDefinition with `widget` field
- `backend/app/cubes/get_flight_course.py` — Points and lines modes from normal_tracks
- `backend/app/cubes/get_learned_paths.py` — Learned paths with centerline/corridor geometry
- `backend/app/cubes/geo_temporal_playback.py` — Output cube with widget=geo_playback
- `frontend/src/components/Results/ResultsDrawer.tsx` — Widget dispatch to custom components
- `frontend/src/components/Visualization/GeoPlaybackWidget.tsx` — Animated map + timeline
- `frontend/src/components/Visualization/GeoPlaybackWidget.css` — Playback widget styles

**Success criteria:**
1. All three cubes appear in catalog with correct inputs/outputs
2. Get Flight Course returns GeoJSON Points (points mode) or LineStrings (lines mode)
3. Get Learned Paths returns centerline LineStrings or corridor Polygons via Shapely
4. Playback cube has widget="geo_playback" and passes data through
5. ResultsDrawer dispatches to GeoPlaybackWidget for visualization cubes
6. Playback widget animates geo data with dual-handle timeline and density histogram
7. Pipeline: AllFlights -> Get Flight Course (points) -> Geo-Temporal Playback shows animated flights
8. Regular cubes retain existing table + auto-detected map behavior

---

## Phase 9: Filter Flights Cube (Gap Closure)

**Goal:** Implement behavioral Filter Flights cube that evaluates flight track data against thresholds, completing the 4-cube pipeline

**Requirements:** DATA-02, DATA-05
**Gap Closure:** Closes gaps from v1.0 audit — missing cube + broken E2E flow

**Depends on:** Phase 7

**Plans:** 1/1 plans complete

Plans:
- [ ] 09-01-PLAN.md — FilterFlightsCube implementation with two-tier filtering + tests

**Key files:**
- `backend/app/cubes/filter_flights.py` — Filter Flights cube querying normal_tracks for behavioral criteria
- `backend/app/cubes/all_flights.py` — May need output adjustments for pipeline compatibility

**Success criteria:**
1. Filter Flights cube appears in catalog with inputs: flight_ids, max_altitude_ft, min_speed_knots, max_speed_knots, min_duration_minutes, max_duration_minutes
2. Cube queries research.normal_tracks, evaluates per-flight behavioral stats, excludes flights violating thresholds
3. Outputs filtered_flight_ids and filtered_flights (metadata for passing flights)
4. 4-cube pipeline (AllFlights → FilterFlights → GetAnomalies → CountByField) produces real results
5. Filter Flights appears in catalog under "filter" category

---

## Phase 10: Audit Remediation (Gap Closure)

**Goal:** Fix all documentation, traceability, integration, and tech debt gaps identified by v1.0 milestone audit

**Requirements:** WFLOW-04-08, RSLT-02-03, GEO-04 (SUMMARY fixes); BACK-08, BACK-11, BACK-13, GEO-02 (integration/tech debt)
**Gap Closure:** Closes remaining gaps from v1.0 audit

**Plans:** 1/2 plans executed

Plans:
- [ ] 10-01-PLAN.md — Fix SUMMARY frontmatter traceability gaps + correct BACK-13 requirement text
- [ ] 10-02-PLAN.md — Fix stale row limit references + remove dead run endpoint

**Success criteria:**
1. All SUMMARY frontmatter lists correct requirements_completed
2. ResultsTable truncation warning matches actual row limit
3. No stale documentation referencing old limits or endpoints
4. Dead code endpoint removed

---

## Requirement Coverage Validation

All 55 requirements mapped:

- **Phase 1 (6):** CUBE-01, CUBE-02, CUBE-03, BACK-01, BACK-02, FRONT-01
- **Phase 2 (10):** BACK-03 through BACK-12
- **Phase 3 (1):** BACK-13
- **Phase 4 (11):** FRONT-02 through FRONT-12
- **Phase 5 (8):** WFLOW-01 through WFLOW-08
- **Phase 6 (3):** RSLT-01, RSLT-02, RSLT-03
- **Phase 7 (6):** DATA-01, DATA-03, DATA-04, DEPL-01 through DEPL-03
- **Phase 8 (7):** GEO-01 through GEO-07
- **Phase 9 (2):** DATA-02, DATA-05 (gap closure)
- **Phase 10 (12):** WFLOW-04-08, RSLT-02-03, GEO-04, BACK-08, BACK-11, BACK-13, GEO-02 (audit remediation)

**Unmapped:** 0

---
*Roadmap created: 2026-03-03*
*Last updated: 2026-03-05 — Phase 10 plans created*
