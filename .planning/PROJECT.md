# Project 12 — Visual Dataflow Workflow Builder

## What This Is

A visual dataflow workflow builder ("12") — a subsystem of Tracer 42, a flight tracking and anomaly detection platform for Middle East airspace. Users drag analysis "cubes" onto a canvas, configure parameters, connect outputs to inputs, and run pipelines against a real PostgreSQL database containing 113K flights, 76M track points, and 114K anomaly reports. No coding required.

## Core Value

Users can build and run custom flight analysis pipelines visually — connecting data source cubes to transform/analysis cubes — and see real results from live Tracer 42 data in tables and on maps.

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

### Active

<!-- v3.0 — AI Workflow Agents -->

- [ ] AI Build Agent — wizard-style page with interactive options, discovers user mission, selects cubes, generates complete workflow
- [ ] AI Canvas Agent — chat panel in editor with 3 modes: optimize, error-fix, general editing
- [ ] Cube Expert sub-agent — two-tier catalog lookup (summaries → full definitions), suggests best cubes for use case
- [ ] Validation Agent — pre-execution structural checks (params filled, types compatible, no dangling inputs)
- [ ] Results Interpreter Agent — post-execution, explains findings in mission context
- [ ] Agent infrastructure — Gemini LLM integration via FastAPI, skill files (system prompts), system brief, internal function-call tools
- [ ] Cube catalog tool — two-tier lookup for agents (summary browse → full definition load)
- [ ] Chat UI component — React chat panel for canvas/error/general agents
- [ ] Wizard UI component — React step-by-step page for build agent with clickable options

### Out of Scope

- Authentication/authorization — Tracer 42 handles this, 12 is internal
- Custom cube creation by end users — future feature
- Real-time collaboration — single user per workflow
- Undo/redo — complexity not justified for v1
- Cube marketplace/sharing — v2 feature
- Mobile responsive design — desktop-only tool for analysts
- Writing to research schema — read-only access to Tracer 42 data
- Scheduled/recurring workflow execution — v2 feature
- Export results to CSV/Excel — v2 feature

## Context

- **Shipped:** v1.0 on 2026-03-06 (3 days, 111 commits, ~7,200 LOC)
- **Tech stack:** FastAPI + SQLAlchemy async (Python), React 18 + TypeScript + Vite (frontend), @xyflow/react v12, Zustand 5, Leaflet + react-leaflet, Docker + nginx
- **Tracer 42 integration:** 12 is a standalone service linked from Tracer 42's UI. It reads from Tracer 42's PostgreSQL database (research schema) but writes only to its own table (public.workflows).
- **Database:** PostgreSQL on AWS RDS with research.flight_metadata (113K rows), research.normal_tracks (76M rows), research.anomaly_reports (114K rows). Timestamps are bigint epoch format.
- **Package managers:** uv for Python (pyproject.toml), pnpm for Node
- **Cubes shipped:** 8 production cubes — AllFlights, FilterFlights, GetAnomalies, CountByField, GetFlightCourse, GetLearnedPaths, GeoTemporalPlayback + 2 stubs (Echo, AddNumbers)
- **Known tech debt:** See `.planning/milestones/v1.0-MILESTONE-AUDIT.md` — orphaned routes, SQL LIMIT inconsistency, missing VERIFICATION.md files

## Constraints

- **Database:** Read-only access to research schema; only public.workflows is writable
- **Tech stack:** React 18+ with TypeScript, FastAPI with async, SQLAlchemy async + asyncpg
- **Canvas library:** @xyflow/react (React Flow v12+) — parameter-level connections required
- **Maps:** Leaflet with CartoDB dark tiles (no API key needed)
- **State:** Zustand (not Redux)
- **Streaming:** SSE via sse-starlette (not WebSocket)
- **Performance:** 10,000-row result limit per cube (raised from 100 in Phase 8)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SSE over WebSocket | Simpler for one-way server→client push; native EventSource API | ✓ Good — works reliably, nginx-compatible with proxy_buffering off |
| Parameter-level connections | User requirement — drag from specific output param to specific input param | ✓ Good — enables precise dataflow wiring |
| Full Result port on every cube | Bundles all outputs into one JSON; enables connecting any output downstream | ✓ Good — essential for flexible pipelines |
| Connection values override manual | If both exist, connection wins at execution time; intuitive behavior | ✓ Good — no user confusion reported |
| Warn on type mismatch, don't block | Dashed orange edge for mismatches; flexibility > strictness | ✓ Good — users appreciate flexibility |
| Leaflet over MapLibre | Lighter weight, no API key, CartoDB dark tiles free | ✓ Good — sufficient for current needs |
| Alembic for migrations | Standards require it; clean separation from Tracer 42 schema | ✓ Good — single migration, clean workflow |
| Workflow table in public schema | Keeps 12's data separate from research schema | ✓ Good — no cross-schema conflicts |
| Row limit 100→10,000 | Track data needs thousands of points per flight | ✓ Good — AllFlights/GetAnomalies still cap at 5K via SQL LIMIT |
| Widget dispatch via CubeDefinition.widget | Output cubes declare custom visualization; ResultsDrawer dispatches | ✓ Good — extensible for future widgets |
| Two-tier FilterFlights | Tier 1 metadata (fast), Tier 2 track aggregation (slower but accurate) | ✓ Good — balances performance and accuracy |
| POST SSE (graph-in-body) over GET/{id} | Ad-hoc execution without saving; frontend serializes graph on each run | ⚠️ Revisit — orphaned GET/{id}/run/stream route exists |

## Current Milestone: v3.0 AI Workflow Agents

**Goal:** Build an AI agent system that helps users create, edit, optimize, and debug visual dataflow workflows — making the growing cube ecosystem accessible through conversational and wizard-style interfaces.

**Target features:**
- Build Agent — wizard page for creating workflows from scratch via guided questions
- Canvas Agent — chat panel with optimize/error-fix/general modes for live workflow editing
- Cube Expert — sub-agent for intelligent cube discovery and recommendation
- Validation Agent — structural pre-flight checks before execution
- Results Interpreter — post-execution analysis explaining findings in user's mission context
- Agent infrastructure — Gemini integration, skill files, system brief, internal tools

---
*Last updated: 2026-03-22 after v3.0 milestone start*
