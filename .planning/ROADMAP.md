# Roadmap: Project 12 — Visual Dataflow Workflow Builder

**Created:** 2026-03-03
**Phases:** 7
**Requirements covered:** 48/48

## Phase Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Types, Schemas & Project Scaffolding | Foundational data contracts + both projects bootable | CUBE-01, CUBE-02, CUBE-03, BACK-01, BACK-02, FRONT-01 | 3 | 1/1 | Complete   | 2026-03-03 | Complete   | 2026-03-03 | 4 | 3/3 | Complete   | 2026-03-03 | Background execution with real-time streaming | BACK-13 | 2 |
| 4 | Frontend Canvas, Nodes, Sidebar & Dark Theme | Full visual editor with drag, configure, connect | FRONT-02 to FRONT-12 | 5 | 3/3 | Complete   | 2026-03-04 | Full loop — dashboard, save/load, run with live status | WFLOW-01 to WFLOW-08 | 4 |
| 6 | Results Display — Tables, Map, Bidirectional | Rich results with tables + map for geo data | RSLT-01, RSLT-02, RSLT-03 | 5 |
| 7 | Real DB Cubes, End-to-End & Docker | Working pipeline with real data + deployable containers | DATA-01 to DATA-05, DEPL-01 to DEPL-03 | 5 |

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

**Plans:** 2 plans

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

**Key files:**
- `backend/app/cubes/get_flights.py` — Queries research.flight_metadata with time/airport/region filters
- `backend/app/cubes/filter_flights.py` — Filters flight_ids by country, days_back, altitude
- `backend/app/cubes/get_anomalies.py` — Queries research.anomaly_reports for flight_ids
- `backend/app/cubes/count_by_field.py` — Pure Python groupby aggregation
- `backend/Dockerfile` — Multi-stage: uv sync → slim Python runtime
- `frontend/Dockerfile` — Multi-stage: pnpm build → nginx serving SPA
- `frontend/nginx.conf` — Serves SPA, proxies /api to backend
- `docker-compose.yml` — Backend + frontend services with .env

**Success criteria:**
1. Get Flights (168h) → Filter (country) → Get Anomalies pipeline returns real data
2. Results table shows real flight_ids, callsigns, airlines from database
3. Map shows markers at flight origin/destination lat/lon positions
4. Count By Field groups by airline and shows counts table
5. `docker-compose up --build` → full app accessible at localhost:3000

**End-to-end verification:**
1. Open /workflow/new
2. Drag Get Flights → set time_range_hours=168
3. Drag Filter Flights → connect flight_ids, set country filter
4. Drag Get Anomalies → connect filtered_flight_ids
5. Drag Count By Field → connect Full Result, set group_by_field=airline
6. Run → watch live status → see real results in tables + map
7. Save → dashboard → reopen → verify state preserved

---

## Requirement Coverage Validation

All 48 v1 requirements mapped:

- **Phase 1 (6):** CUBE-01, CUBE-02, CUBE-03, BACK-01, BACK-02, FRONT-01
- **Phase 2 (10):** BACK-03 through BACK-12
- **Phase 3 (1):** BACK-13
- **Phase 4 (11):** FRONT-02 through FRONT-12
- **Phase 5 (8):** WFLOW-01 through WFLOW-08
- **Phase 6 (3):** RSLT-01, RSLT-02, RSLT-03
- **Phase 7 (8):** DATA-01 through DATA-05, DEPL-01 through DEPL-03

**Unmapped:** 0

---
*Roadmap created: 2026-03-03*
*Last updated: 2026-03-04 — Phase 6 plans created (06-01 geo detect + table + store, 06-02 map + drawer + wiring)*
