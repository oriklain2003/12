# Project 12 — Visual Dataflow Workflow Builder

## What This Is

A visual dataflow workflow builder ("12") — a subsystem of Tracer 42, a flight tracking and anomaly detection platform for Middle East airspace. Users drag analysis "cubes" onto a canvas, configure parameters, connect outputs to inputs, and run pipelines against a real PostgreSQL database containing 113K flights, 76M track points, and 114K anomaly reports. AI agents assist with building, editing, validating, and interpreting workflows. No coding required.

## Core Value

Users can build and run custom flight analysis pipelines visually — connecting data source cubes to transform/analysis cubes — and see real results from live Tracer 42 data in tables and on maps. AI agents make the growing cube ecosystem accessible through conversational and wizard-style interfaces.

## Requirements

### Validated

- ✓ Shared type definitions (Python Pydantic + TypeScript mirrors) — v1.0
- ✓ BaseCube abstract class with async execute() method — v1.0
- ✓ Workflow data model types (nodes, edges, graph) — v1.0
- ✓ FastAPI scaffold with CORS, config from .env — v1.0
- ✓ Async PostgreSQL layer (SQLAlchemy + asyncpg) — v1.0
- ✓ CubeRegistry with auto-discovery of Python cube classes — v1.0
- ✓ Workflow DB model + Alembic migration — v1.0
- ✓ Cube catalog API endpoint — v1.0
- ✓ Workflow CRUD API (create, list, get, update, delete) — v1.0
- ✓ WorkflowExecutor with topological sort, cycle detection, input resolution — v1.0
- ✓ Full Result port on every cube (__full_result__) — v1.0
- ✓ Result row limiting (10,000 rows per cube) — v1.0
- ✓ Connection value override (connection wins over manual param) — v1.0
- ✓ Type mismatch warning (not blocking) — v1.0
- ✓ SSE endpoint for real-time per-cube execution status — v1.0
- ✓ Vite + React + TypeScript frontend scaffold — v1.0
- ✓ Dark theme with liquid glass CSS effects — v1.0
- ✓ React Flow canvas with custom CubeNode components — v1.0
- ✓ Parameter handles (color-coded by type) — v1.0
- ✓ Inline parameter editors (hidden when connected) — v1.0
- ✓ Compact results preview panel on each cube — v1.0
- ✓ Cube catalog sidebar (grouped by category, draggable, searchable) — v1.0
- ✓ Zustand store with serialization — v1.0
- ✓ Toolbar (Run, Save, workflow name, dashboard link) — v1.0
- ✓ API client layer (fetch wrapper) — v1.0
- ✓ Client routing (dashboard / editor / new) — v1.0
- ✓ Dashboard page (list, open, rename, delete, create workflows) — v1.0
- ✓ Save/load serialization — v1.0
- ✓ Run integration with SSE progress — v1.0
- ✓ Per-cube status indicators (pending → running → done/error) — v1.0
- ✓ Error handling and display — v1.0
- ✓ Keyboard shortcuts (Delete, Ctrl+S, Ctrl+Enter) — v1.0
- ✓ JSON-to-table rendering with sortable columns — v1.0
- ✓ Leaflet map panel for geo data (CartoDB dark tiles) — v1.0
- ✓ Bidirectional map↔table interaction — v1.0
- ✓ Get Flights cube (real DB query with time/airport/region/polygon filters) — v1.0
- ✓ Filter Flights cube (behavioral criteria: altitude, speed, duration thresholds) — v1.0
- ✓ Get Anomalies cube (query anomaly_reports for flight_ids) — v1.0
- ✓ Count By Field cube (pure Python groupby aggregation) — v1.0
- ✓ Get Flight Course cube (GeoJSON points/lines from normal_tracks) — v1.0
- ✓ Get Learned Paths cube (centerline/corridor from learned_paths) — v1.0
- ✓ Geo-Temporal Playback output cube (widget=geo_playback) — v1.0
- ✓ End-to-end pipeline with real data — v1.0
- ✓ Docker Compose for local dev — v1.0
- ✓ Production Dockerfiles (multi-stage) — v1.0
- ✓ Widget field on CubeDefinition for custom visualization dispatch — v1.0
- ✓ GeoPlaybackWidget with animated map, timeline, histogram — v1.0
- ✓ Agent infrastructure — Gemini client, skill files, tool registry, SSE endpoint, sessions — v3.0
- ✓ Cube catalog tool — two-tier lookup (summary browse → full definition load) — v3.0
- ✓ AI Canvas Agent — chat panel in editor with 3 modes: optimize, error-fix, general — v3.0
- ✓ Cube Expert sub-agent — catalog tools for intelligent cube discovery and recommendation — v3.0
- ✓ Validation Agent — pre-execution structural checks (7 rules, pre-run blocking, issue highlighting) — v3.0
- ✓ AI Build Agent — wizard page with option cards, mission discovery, workflow generation — v3.0
- ✓ Results Interpreter Agent — post-execution analysis with mission-context explanation — v3.0
- ✓ Chat UI component — React chat panel for canvas agent with mode switching — v3.0
- ✓ Wizard UI component — React wizard page with option cards, mini graph preview — v3.0

### Active

(No active requirements — planning next milestone)

### Out of Scope

- Authentication/authorization — Tracer 42 handles this, 12 is internal
- Custom cube creation by end users — future feature
- Real-time collaboration — single user per workflow
- Undo/redo — complexity not justified for v1
- Cube marketplace/sharing — future feature
- Mobile responsive design — desktop-only tool for analysts
- Writing to research schema — read-only access to Tracer 42 data
- Scheduled/recurring workflow execution — future feature
- Export results to CSV/Excel — future feature
- Fully autonomous workflow execution (no user confirmation) — analysts must own query logic
- Persistent agent memory across sessions — workflow itself is the artifact
- Multi-turn wizard refinement — wizard is one-shot; use Canvas Agent for refinements

## Context

- **Shipped:** v1.0 on 2026-03-06 (3 days, 111 commits, ~7,200 LOC); v3.0 on 2026-03-27 (4 days, 89 commits, +8,249 LOC)
- **Tech stack:** FastAPI + SQLAlchemy async (Python), React 18 + TypeScript + Vite (frontend), @xyflow/react v12, Zustand 5, Leaflet + react-leaflet, Docker + nginx, google-genai (Gemini LLM)
- **Tracer 42 integration:** 12 is a standalone service linked from Tracer 42's UI. It reads from Tracer 42's PostgreSQL database (research schema) but writes only to its own table (public.workflows).
- **Database:** PostgreSQL on AWS RDS with research.flight_metadata (113K rows), research.normal_tracks (76M rows), research.anomaly_reports (114K rows). Timestamps are bigint epoch format.
- **Package managers:** uv for Python (pyproject.toml), pnpm for Node
- **Cubes shipped:** 14+ production cubes across data_source, filter, analysis, aggregation, output categories
- **AI agents:** 5 personas (canvas_agent, build_agent, results_interpreter, results_followup, validation_agent) powered by Gemini 2.5/3 Flash/Pro with tool calling
- **Known tech debt:** See `.planning/milestones/v3.0-MILESTONE-AUDIT.md` — dead CubeExpert class, unused validation_agent persona, missing VERIFICATION.md files, orphaned mission endpoint

## Constraints

- **Database:** Read-only access to research schema; only public.workflows is writable
- **Tech stack:** React 18+ with TypeScript, FastAPI with async, SQLAlchemy async + asyncpg
- **Canvas library:** @xyflow/react (React Flow v12+) — parameter-level connections required
- **Maps:** Leaflet with CartoDB dark tiles (no API key needed)
- **State:** Zustand (not Redux)
- **Streaming:** SSE via sse-starlette (not WebSocket) — for both workflow execution and agent responses
- **Performance:** 10,000-row result limit per cube
- **LLM:** google-genai >= 1.68.0 (Gemini); async-only calls in handlers; manual tool dispatch pattern

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SSE over WebSocket | Simpler for one-way server→client push; native EventSource API | ✓ Good — works reliably, nginx-compatible with proxy_buffering off |
| Parameter-level connections | User requirement — drag from specific output param to specific input param | ✓ Good — enables precise dataflow wiring |
| Full Result port on every cube | Bundles all outputs into one JSON; enables connecting any output downstream | ✓ Good — essential for flexible pipelines |
| Connection values override manual | If both exist, connection wins at execution time; intuitive behavior | ✓ Good — no user confusion reported |
| Warn on type mismatch, don't block | Dashed orange edge for mismatches; flexibility > strictness | ✓ Good — users appreciate flexibility |
| Leaflet over MapLibre | Lighter weight, no API key, CartoDB dark tiles free | ✓ Good — sufficient for current needs |
| Row limit 100→10,000 | Track data needs thousands of points per flight | ✓ Good — AllFlights/GetAnomalies still cap at 5K via SQL LIMIT |
| Widget dispatch via CubeDefinition.widget | Output cubes declare custom visualization; ResultsDrawer dispatches | ✓ Good — extensible for future widgets |
| POST SSE (graph-in-body) over GET/{id} | Ad-hoc execution without saving; frontend serializes graph on each run | ⚠️ Revisit — orphaned GET/{id}/run/stream route exists |
| Stateless agents (client-carried history) | No server-side session store; conversation state in POST body | ✓ Good — simple, scalable, no DB for chat |
| Manual tool dispatch (not auto function calling) | Gemini tool_config: ANY for tool turns, then stream final text | ✓ Good — reliable control over tool→response flow |
| Two-tier catalog (summaries → full def) | Never inline all cube definitions in system prompt; load on demand | ✓ Good — keeps context manageable |
| applyAgentDiff for atomic canvas updates | pushSnapshot first, then batch node+edge insertion in single Zustand update | ✓ Good — no partial broken canvas states |
| Wizard uses option cards only (no free text for cube selection) | Prevents LLM hallucination on analyst input | ✓ Good — reliable cube selection |
| Results interpreter is one-shot SSE | No session management; follow-up uses results_followup persona via /api/agent/chat | ✓ Good — simple, clean separation |

---
*Last updated: 2026-03-27 after v3.0 milestone*
