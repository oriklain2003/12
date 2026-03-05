# Requirements: Project 12 — Visual Dataflow Workflow Builder

**Defined:** 2026-03-03
**Core Value:** Users can build and run custom flight analysis pipelines visually — connecting data source cubes to transform/analysis cubes — and see real results from live Tracer 42 data in tables and on maps.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Cube System

- [x] **CUBE-01**: Shared type definitions exist in both Python (Pydantic) and TypeScript with matching ParamType enum, CubeCategory enum (data_source, filter, analysis, aggregation, output), ParamDefinition (with accepts_full_result flag), and CubeDefinition models
- [x] **CUBE-02**: BaseCube abstract class with async execute() method, cube_id, name, description, category, inputs, outputs properties, and automatic Full Result output port
- [x] **CUBE-03**: Workflow data model types (WorkflowNode, WorkflowEdge, WorkflowGraph) defined in both Python and TypeScript

### Backend Infrastructure

- [x] **BACK-01**: FastAPI application with CORS middleware allowing frontend origin, health endpoint returning 200, config loaded from .env via pydantic-settings
- [x] **BACK-02**: Async PostgreSQL connection pool via SQLAlchemy async engine + asyncpg, with session dependency injection
- [x] **BACK-03**: CubeRegistry that auto-discovers all BaseCube subclasses from the cubes package and exposes them by cube_id
- [x] **BACK-04**: SQLAlchemy Workflow model (UUID pk, name, graph_json JSONB, created_at, updated_at) in public schema
- [x] **BACK-05**: Alembic migration creating public.workflows table
- [x] **BACK-06**: GET /api/cubes/catalog returns all registered cube definitions as JSON array
- [x] **BACK-07**: Workflow CRUD API — POST /api/workflows (create), GET /api/workflows (list), GET /api/workflows/{id} (get), PUT /api/workflows/{id} (update), DELETE /api/workflows/{id} (delete)
- [x] **BACK-08**: POST /api/workflows/{id}/run executes workflow graph and returns results
- [x] **BACK-09**: WorkflowExecutor performs topological sort of nodes, detects cycles (returns 400), resolves input values from connections, validates connection type compatibility (warn on mismatch), validates Full Result connections only attach to params with accepts_full_result=true
- [x] **BACK-10**: Full Result port (__full_result__) bundles all cube outputs into one JSON object, available as connection source
- [x] **BACK-11**: Result rows capped at 100 per cube with truncation flag in response
- [x] **BACK-12**: Connection values override manually entered param values at execution time
- [x] **BACK-13**: SSE endpoint (POST /api/workflows/run/stream) accepts WorkflowGraph in request body, streams per-cube status events (pending, running, done, error) via sse-starlette EventSourceResponse

### Frontend Infrastructure

- [x] **FRONT-01**: Vite + React 18 + TypeScript project with pnpm, dev server on port 5173 proxying /api to backend port 8000
- [x] **FRONT-02**: Dark theme CSS with CSS custom properties and liquid glass effects (backdrop-filter: blur(12px) saturate(150%))
- [x] **FRONT-03**: React Flow canvas (@xyflow/react v12+) with dark background, grid, pan/zoom, and drop handler for adding cubes
- [x] **FRONT-04**: Custom CubeNode component rendering cube name, category icon, input handles (left), output handles + Full Result (right)
- [x] **FRONT-05**: Parameter handles color-coded by ParamType (string=blue, number=green, boolean=orange, flight_ids=purple, json=gray, arrays=teal)
- [x] **FRONT-06**: Inline parameter editors on each CubeNode — text inputs, number inputs, checkboxes — hidden when a connection provides the value
- [x] **FRONT-07**: Compact results preview panel on each CubeNode showing row count and first few values
- [x] **FRONT-08**: Collapsible cube catalog sidebar grouped by CubeCategory (data_source, filter, analysis, aggregation, output), each cube draggable onto canvas, with search/filter input, toggle button to collapse/expand
- [x] **FRONT-09**: Zustand store managing nodes, edges, cube catalog, execution status, results, with JSON serialization for save/load
- [x] **FRONT-10**: Toolbar with Run button, Save button, editable workflow name field, and link back to dashboard
- [x] **FRONT-11**: API client module (fetch wrapper) for all backend endpoints with error handling
- [x] **FRONT-12**: Connection validation on canvas — type mismatch shown as dashed orange edge with warning, Full Result handle only connectable to inputs with accepts_full_result=true, incompatible connections prevented

### Workflow Management

- [x] **WFLOW-01**: React Router with routes: / (dashboard), /workflow/:id (editor), /workflow/new (new workflow)
- [x] **WFLOW-02**: Dashboard page listing all saved workflows with name, last modified date, and actions (open, rename, delete, create new)
- [x] **WFLOW-03**: Save serializes current flow state (nodes, edges, params) to backend via PUT; Load deserializes and restores canvas
- [x] **WFLOW-04**: Run button triggers SSE connection, streams per-cube status updates to Zustand store, updates CubeNode indicators in real-time
- [x] **WFLOW-05**: Each CubeNode shows execution status indicator: gray (pending), blue spinner (running), green check (done), red X (error with message)
- [x] **WFLOW-06**: Error messages from failed cubes display inline on the CubeNode with the error text
- [x] **WFLOW-07**: Keyboard shortcuts — Delete removes selected nodes/edges, Ctrl+S saves workflow, Ctrl+Enter runs workflow
- [x] **WFLOW-08**: Overall pipeline progress indicator during execution showing "X/Y cubes completed" with progress bar in toolbar area

### Results Display

- [x] **RSLT-01**: Results table auto-detects columns from JSON array data, renders as scrollable table with sortable column headers
- [x] **RSLT-02**: Leaflet map panel with CartoDB dark tiles renders markers for result rows that contain lat/lon coordinate pairs
- [x] **RSLT-03**: Bidirectional interaction — clicking a map marker highlights and scrolls to the corresponding table row; clicking a table row flies the map to that location

### Real Data Cubes

- [x] **DATA-01**: Get Flights cube queries research.flight_metadata with optional filters: time_range_hours (bigint epoch), airport (origin/dest ILIKE), region bounding box (lat/lon ranges); outputs flight_ids array and flights data array
- [x] **DATA-02**: Filter Flights cube accepts flight_ids, queries research.normal_tracks to evaluate behavioral criteria (max_altitude_ft, min_speed_knots, max_speed_knots, min_duration_minutes, max_duration_minutes), excludes flights whose track data violates thresholds; outputs filtered_flight_ids and filtered_flights metadata
- [x] **DATA-03**: Get Anomalies cube accepts flight_ids array, queries research.anomaly_reports for matching flight_ids; outputs anomaly records with severity and report data
- [x] **DATA-04**: Count By Field cube accepts any data array and group_by_field name, performs pure Python groupby aggregation; outputs grouped counts as array of {field_value, count}
- [x] **DATA-05**: End-to-end pipeline: Get Flights → Filter Flights → Get Anomalies + Count By Field produces real results from live database

### Deployment

- [x] **DEPL-01**: docker-compose.yml defining backend and frontend services with shared network, environment variables from .env
- [x] **DEPL-02**: Backend Dockerfile — multi-stage build using uv for dependency install, slim Python runtime image
- [x] **DEPL-03**: Frontend Dockerfile — multi-stage build using pnpm for build, nginx for serving SPA with /api proxy to backend

### Geo-Temporal & Visualization (Phase 8)

- [x] **GEO-01**: CubeDefinition includes a `widget` field (string | None) in both Python and TypeScript; BaseCube.definition passes widget through; enables cubes to declare custom visualization components
- [x] **GEO-02**: Global result_row_limit bumped from 100 to 10,000 to support track data (thousands of points per flight)
- [x] **GEO-03**: Get Flight Course cube queries research.normal_tracks by flight_ids; points mode outputs all track columns + GeoJSON Point geometry; lines mode outputs flight_id, callsign, GeoJSON LineString, start/end time, min/max altitude
- [x] **GEO-04**: Get Learned Paths cube queries public.learned_paths with optional origin, destination, path_id, polygon, min_member_count filters; centerline mode returns GeoJSON LineString; corridor mode returns Shapely-buffered GeoJSON Polygon
- [x] **GEO-05**: Geo-Temporal Playback cube (category: output, widget: geo_playback) accepts data with geometry/timestamp/id columns; passes data through (visualization-only)
- [x] **GEO-06**: ResultsDrawer widget dispatch: output cubes with widget field render custom visualization component in right panel instead of ResultsMap; table panel always shows; regular cubes keep existing behavior
- [x] **GEO-07**: GeoPlaybackWidget renders animated Leaflet map with CartoDB dark tiles, dual-handle timeline slider, density histogram, play/pause, speed selector (1x/2x/5x/10x), auto-colored objects by id/color column, no labels/trails/ghosts

## v2 Requirements

### Advanced Features

- **ADV-01**: Custom cube creation by end users via Python code editor
- **ADV-02**: Undo/redo for canvas operations
- **ADV-03**: Real-time collaboration on shared workflows
- **ADV-04**: Cube marketplace for sharing community cubes
- **ADV-05**: Scheduled/recurring workflow execution
- **ADV-06**: Export results to CSV/Excel

## Out of Scope

| Feature | Reason |
|---------|--------|
| Authentication/authorization | Tracer 42 handles this; 12 is an internal tool |
| Custom user-defined cubes | High complexity, defer to v2 |
| Real-time collaboration | Single-user per workflow sufficient for v1 |
| Undo/redo | Complexity not justified; users can delete and re-add |
| Mobile responsive design | Desktop-only tool for analysts |
| Writing to research schema | Read-only access to Tracer 42 data |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CUBE-01 | Phase 1 | Complete |
| CUBE-02 | Phase 1 | Complete |
| CUBE-03 | Phase 1 | Complete |
| BACK-01 | Phase 1 | Complete |
| BACK-02 | Phase 1 | Complete |
| BACK-03 | Phase 2 | Complete |
| BACK-04 | Phase 2 | Complete |
| BACK-05 | Phase 2 | Complete |
| BACK-06 | Phase 2 | Complete |
| BACK-07 | Phase 2 | Complete |
| BACK-08 | Phase 2 | Complete |
| BACK-09 | Phase 2 | Complete |
| BACK-10 | Phase 2 | Complete |
| BACK-11 | Phase 2 | Complete |
| BACK-12 | Phase 2 | Complete |
| BACK-13 | Phase 3 | Complete |
| FRONT-01 | Phase 1 | Complete |
| FRONT-02 | Phase 4 | Complete |
| FRONT-03 | Phase 4 | Complete |
| FRONT-04 | Phase 4 | Complete |
| FRONT-05 | Phase 4 | Complete |
| FRONT-06 | Phase 4 | Complete |
| FRONT-07 | Phase 4 | Complete |
| FRONT-08 | Phase 4 | Complete |
| FRONT-09 | Phase 4 | Complete |
| FRONT-10 | Phase 4 | Complete |
| FRONT-11 | Phase 4 | Complete |
| FRONT-12 | Phase 4 | Complete |
| WFLOW-01 | Phase 5 | Complete |
| WFLOW-02 | Phase 5 | Complete |
| WFLOW-03 | Phase 5 | Complete |
| WFLOW-04 | Phase 5 | Complete |
| WFLOW-05 | Phase 5 | Complete |
| WFLOW-06 | Phase 5 | Complete |
| WFLOW-07 | Phase 5 | Complete |
| WFLOW-08 | Phase 5 | Complete |
| RSLT-01 | Phase 6 | Complete |
| RSLT-02 | Phase 6 | Complete |
| RSLT-03 | Phase 6 | Complete |
| DATA-01 | Phase 7 | Complete |
| DATA-02 | Phase 9 | Complete |
| DATA-03 | Phase 7 | Complete |
| DATA-04 | Phase 7 | Complete |
| DATA-05 | Phase 9 | Complete |
| DEPL-01 | Phase 7 | Complete |
| DEPL-02 | Phase 7 | Complete |
| DEPL-03 | Phase 7 | Complete |
| GEO-01 | Phase 8 | Complete |
| GEO-02 | Phase 8 | Complete |
| GEO-03 | Phase 8 | Complete |
| GEO-04 | Phase 8 | Complete |
| GEO-05 | Phase 8 | Complete |
| GEO-06 | Phase 8 | Complete |
| GEO-07 | Phase 8 | Complete |

**Coverage:**
- v1 requirements: 48 + 7 Phase 8 = 55 total
- Complete: 53
- Pending: 2 (DATA-02, DATA-05 → Phase 9)
- Mapped to phases: 55
- Unmapped: 0

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-05 — Gap closure: DATA-02/DATA-05 reassigned to Phase 9, GEO-01–07 status corrected to Complete*
