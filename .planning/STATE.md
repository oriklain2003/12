---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-03-05T12:19:41.854Z"
progress:
  total_phases: 8
  completed_phases: 8
  total_plans: 20
  completed_plans: 20
---

# Project State: Project 12

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-03)

**Core value:** Users can build and run custom flight analysis pipelines visually
**Current focus:** Phase 1 — Types, Schemas & Project Scaffolding

## Current Milestone

**Milestone 1:** v1 — Full visual dataflow workflow builder

### Phase Status

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Types, Schemas & Project Scaffolding | In Progress | 1/2+ |
| 2 | Backend Core — Registry, DB, CRUD, Executor | Not Started | 0/0 |
| 3 | Async Execution with SSE Progress | Not Started | 0/0 |
| 4 | Frontend Canvas, Nodes, Sidebar & Dark Theme | Not Started | 0/0 |
| 5 | Workflow Management & Execution Integration | Not Started | 0/0 |
| 6 | Results Display — Tables, Map, Bidirectional | Not Started | 0/0 |
| 7 | Real DB Cubes, End-to-End & Docker | Not Started | 0/0 |

### Active Phase

**Phase 1: Types, Schemas & Project Scaffolding**
- Status: In Progress
- Requirements: CUBE-01, CUBE-02, CUBE-03, BACK-01, BACK-02, FRONT-01
- Completed Plans: 01-01 (Python cube schemas + BaseCube), 01-02 (frontend scaffold + TypeScript types)

## Decisions

- ParamType uses list_of_strings/list_of_numbers/json_object per spec (old STRING_ARRAY/NUMBER_ARRAY/FLIGHT_IDS/JSON values replaced)
- CubeDefinition uses `cube_id` field (not `id`) per spec — old implementation corrected
- BaseCube.definition is an instance property that auto-appends __full_result__ output (ParamType.JSON_OBJECT)
- hatch wheel packages config added to pyproject.toml to resolve editable install discovery
- httpx added as dev dependency for FastAPI TestClient support
- WorkflowResponse.id typed as `string` in TypeScript (UUID serializes as string over JSON)
- [Phase 02]: Route paths use empty string '' not '/' in FastAPI routers to avoid 307 redirect when callers omit trailing slash
- [Phase 02]: graph_json JSONB round-trips via model_dump() on write and WorkflowGraph.model_validate() on read — from_attributes=True alone does not handle dict-to-model coercion for JSONB
- [Phase 02]: Alembic migration written manually (not autogenerate) to avoid asyncpg reflection complexity
- [Phase 02]: CubeRegistry uses BaseCube.__subclasses__() after pkgutil.iter_modules import — zero-registration auto-discovery pattern
- [Phase 02]: pytest-asyncio asyncio_mode=auto set in pyproject.toml to avoid per-test decorator
- [Phase 02]: execute_graph uses patch('app.engine.executor.registry') mock pattern in tests for isolation
- [Phase 02]: AllFlights cube uses engine.connect() directly (not FastAPI DI) to keep BaseCube.execute(**inputs) signature clean
- [Phase 02]: Polygon geofence filter uses Python ray-casting against research.normal_tracks (PostGIS not on Tracer 42 RDS)
- [Phase 03-01]: stream_graph assumes pre-validated graph — callers validate and raise HTTPException before streaming
- [Phase 03-01]: execute_graph delegates to stream_graph internally to eliminate sync/streaming code duplication
- [Phase 03-01]: SSE cycle validation happens pre-stream so HTTP 400 can be returned before SSE headers are committed
- [Phase 04-01]: ParamType enum corrected: list_of_strings/list_of_numbers/json_object; FLIGHT_IDS removed to match backend exactly
- [Phase 04-01]: API client uses /api base path matching Vite proxy — apiFetch<T> generic wrapper with ApiError for typed error handling
- [Phase 04-02]: CubeNodeData/CubeFlowNode types collocated in flowStore.ts to avoid circular dependency
- [Phase 04-02]: Full Result handle uses id='__full_result__' and ParamType.JSON_OBJECT color — rendered separately from outputs loop
- [Phase 04-02]: ParamField reads current value via Zustand selector — no prop drilling from CubeNode
- [Phase 04-03]: Full Result rejection blocks connection entirely and shows toast.error (isValidConnection returns false)
- [Phase 04-03]: Type mismatches allowed — custom onConnect assigns edge.type='mismatch' for dashed orange MismatchEdge rendering
- [Phase 04-03]: cube.ts enums converted to const+type alias pattern (erasableSyntaxOnly tsconfig compliance)
- [Phase 04-03]: nodeTypes and edgeTypes defined at module level (React Flow v12 requirement — prevents re-registration)
- [Phase 05]: EditorPage owns ReactFlowProvider (not root) to keep React Flow scoped to canvas routes
- [Phase 05]: createBrowserRouter + RouterProvider pattern adopted (React Router v7); DashboardPlaceholder inline in main.tsx until Plan 02
- [Phase 05]: loadWorkflow fetches catalog first if empty to avoid race condition with CubeCatalog mount
- [Phase 05]: DashboardPage is a single-file component (no separate WorkflowCard) — card JSX is inline since only used on this page
- [Phase 05]: Delete confirmation is inline (replaces action row) per user decision — no modal or overlay needed
- [Phase 05-03]: useRef for EventSource lifecycle — avoids re-renders, imperatively managed
- [Phase 05-03]: EventSource must be explicitly closed on terminal state — auto-reconnects on server close
- [Phase 05-03]: Error banner inside .cube-node (position:relative) at bottom:calc(100%+6px) floats above node
- [Phase 06-01]: detectGeoColumns validates first-row numeric values to avoid false positives on string columns named lat
- [Phase 06-01]: Selected row uses border-left: 2px solid accent — not background fill — preserves readability
- [Phase 06-01]: Sort state resets on rows reference change to prevent stale sort key from prior cube column names
- [Phase 06-02]: GeoJSON layer uses key={JSON.stringify} for forced re-mount on cube switch, not MapContainer key
- [Phase 06-02]: ResizeDivider uses pointer capture API for clean drag outside element bounds, clamped 15-85%
- [Phase 06-02]: selectedRowIndex is local useState (not Zustand) — ephemeral view state per RESEARCH.md anti-pattern guidance
- [Phase 07-02]: PolygonField and PolygonMapWidget colocated in one file for simplicity
- [Phase 07-02]: ClickCapture child component pattern for useMapEvents (must be inside MapContainer)
- [Phase 07-02]: position:fixed overlay z-index 9999 escapes React Flow stacking context for polygon widget
- [Phase 07]: GetAnomalies guards empty flight_ids early (before SQL) to avoid PostgreSQL ANY() type error with empty array
- [Phase 07]: CountByField extracts first list value from full_result dict via next() comprehension to enable direct wiring from any cube
- [Phase 07]: uv:0.9 minor version pin for resilient Docker builds; python urllib for healthcheck in slim images; proxy_buffering off for SSE in nginx
- [Phase 08]: Centerline points stored as {lat, lon, alt} JSONB dicts — parsed at query time
- [Phase 08]: Corridor buffer approximation: 1 NM = 1/60 degree (flat-cap Shapely buffer)
- [Phase 08]: GeoJSON coordinates follow spec order [lon, lat], not display order [lat, lon]
- [Phase 08]: widget field on CubeDefinition defaults to None via getattr — existing cubes unaffected
- [Phase 08]: result_row_limit raised from 100 to 10000 for full track data support
- [Phase 08]: GeoPlaybackPlaceholder is inline in ResultsDrawer until Plan 04 replaces it with real widget
- [Phase 08]: Widget dispatch uses (cubeWidget || geoInfo) as single right-panel condition for extensible layout
- [Phase 08-04]: GeoPlaybackWidget splits into outer guard + GeoPlaybackInner to avoid conditional hook violations
- [Phase 08-04]: speedRef useRef pattern mirrors speed into ref to avoid animation effect re-trigger on speed change
- [Phase 08-04]: GeoJSON keyed by windowStart-windowEnd forces re-mount on each time window change

## Notes

- Backend scaffold files already exist from initial session (pyproject.toml, schemas, config, database)
- DATABASE_URL configured in .env pointing to Tracer 42 PostgreSQL on AWS RDS
- uv and pnpm both available on the system
- Frontend scaffold completed: `cd frontend && pnpm dev` starts on port 5173
- TypeScript type contracts established for cube and workflow data models
- Plan 01-01 re-executed to align implementation with plan spec (corrected enum values and field names)

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 01 | 01 | 12 min | 2 | 4 |
| 01 | 02 | 2 min | 2 | 18 |
| Phase 07 P02 | 2 | 2 tasks | 3 files |
| Phase 07-real-db-cubes-end-to-end-docker P01 | 8 | 1 tasks | 4 files |
| Phase 07 P03 | 1 | 2 tasks | 6 files |
| Phase 08 P02 | 2 min | 2 tasks | 3 files |
| Phase 08 P01 | 8min | 2 tasks | 5 files |
| Phase 08 P03 | 2min | 2 tasks | 2 files |
| Phase 08 P04 | 2min | 2 tasks | 3 files |

## Accumulated Context

### Roadmap Evolution
- Phase 8 added: Geo-temporal playback, learned paths, and flight course cubes

---
*Last session: 2026-03-03 — Completed 01-01-PLAN.md (cube type system + BaseCube + FastAPI app)*
| Phase 02 P01 | 2 | 2 tasks | 11 files |
| Phase 02 P02 | 6min | 2 tasks | 6 files |
| Phase 03 P01 | 3min | 2 tasks | 5 files |
| Phase 04 P01 | 2min | 2 tasks | 8 files |
| Phase 04 P02 | 3min | 2 tasks | 8 files |
| Phase 04 P03 | 10min | 2 tasks | 11 files |
| Phase 05 P01 | 2min | 2 tasks | 5 files |
| Phase 05 P02 | 3min | 2 tasks | 3 files |
| Phase 05 P03 | 3min | 2 tasks | 6 files |
| Phase 06 P01 | 2min | 2 tasks | 4 files |
| Phase 06 P02 | 2min | 2 tasks | 8 files |

