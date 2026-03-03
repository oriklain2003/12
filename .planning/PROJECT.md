# Project 12 — Visual Dataflow Workflow Builder

## What This Is

A visual dataflow workflow builder ("12") — a subsystem of Tracer 42, a flight tracking and anomaly detection platform for Middle East airspace. Users drag analysis "cubes" onto a canvas, configure parameters, connect outputs to inputs, and run pipelines against a real PostgreSQL database containing 113K flights, 76M track points, and 114K anomaly reports. No coding required.

## Core Value

Users can build and run custom flight analysis pipelines visually — connecting data source cubes to transform/analysis cubes — and see real results from live Tracer 42 data in tables and on maps.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Shared type definitions (Python Pydantic + TypeScript mirrors) for cubes and workflows
- [ ] BaseCube abstract class with async execute() method
- [ ] Workflow data model types (nodes, edges, graph)
- [ ] FastAPI scaffold with CORS, config from .env
- [ ] Async PostgreSQL layer (SQLAlchemy + asyncpg)
- [ ] CubeRegistry with auto-discovery of Python cube classes
- [ ] Workflow DB model + Alembic migration (public.workflows table)
- [ ] Cube catalog API endpoint
- [ ] Workflow CRUD API (create, list, get, update, delete)
- [ ] Workflow run API
- [ ] WorkflowExecutor with topological sort, cycle detection, input resolution
- [ ] Full Result port on every cube (__full_result__)
- [ ] Result row limiting (100 rows per cube)
- [ ] Connection value override (connection wins over manual param)
- [ ] Type mismatch warning (not blocking)
- [ ] SSE endpoint for real-time per-cube execution status
- [ ] Vite + React + TypeScript frontend scaffold
- [ ] Dark theme with liquid glass CSS effects
- [ ] React Flow canvas with custom CubeNode components
- [ ] Parameter handles (color-coded by type)
- [ ] Inline parameter editors (hidden when connected)
- [ ] Compact results preview panel on each cube
- [ ] Cube catalog sidebar (grouped by category, draggable, searchable)
- [ ] Zustand store with serialization
- [ ] Toolbar (Run, Save, workflow name, dashboard link)
- [ ] API client layer (fetch wrapper)
- [ ] Client routing (dashboard / editor / new)
- [ ] Dashboard page (list, open, rename, delete, create workflows)
- [ ] Save/load serialization
- [ ] Run integration with SSE progress
- [ ] Per-cube status indicators (pending → running → done/error)
- [ ] Error handling and display
- [ ] Keyboard shortcuts (Delete, Ctrl+S, Ctrl+Enter)
- [ ] JSON-to-table rendering with sortable columns
- [ ] Leaflet map panel for geo data (CartoDB dark tiles)
- [ ] Bidirectional map↔table interaction
- [ ] Get Flights cube (real DB query with time/airport/region filters)
- [ ] Filter Flights cube (by country, days_back, altitude)
- [ ] Get Anomalies cube (query anomaly_reports for flight_ids)
- [ ] Count By Field cube (pure Python groupby aggregation)
- [ ] End-to-end pipeline with real data
- [ ] Docker Compose for local dev
- [ ] Production Dockerfiles (multi-stage)

### Out of Scope

- Authentication/authorization — Tracer 42 handles this, 12 is internal
- Custom cube creation by end users — v2 feature
- Real-time collaboration — single user per workflow
- Undo/redo — complexity not justified for v1
- Cube marketplace/sharing — v2 feature

## Context

- **Tracer 42 integration:** 12 is a standalone service linked from Tracer 42's UI. It reads from Tracer 42's PostgreSQL database (research schema) but writes only to its own table (public.workflows).
- **Database:** Existing PostgreSQL on AWS RDS with research.flight_metadata (113K rows), research.normal_tracks (76M rows), research.anomaly_reports (114K rows). Timestamps are bigint epoch format.
- **Package managers:** uv for Python (pyproject.toml), pnpm for Node
- **Prior art:** The scaffold files (backend/app structure, pyproject.toml, schemas) were started in this session

## Constraints

- **Database:** Read-only access to research schema; only public.workflows is writable
- **Tech stack:** React 18+ with TypeScript, FastAPI with async, SQLAlchemy async + asyncpg
- **Canvas library:** @xyflow/react (React Flow v12+) — parameter-level connections required
- **Maps:** Leaflet with CartoDB dark tiles (no API key needed)
- **State:** Zustand (not Redux)
- **Streaming:** SSE via sse-starlette (not WebSocket)
- **Performance:** 100-row result limit per cube to prevent UI overload

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SSE over WebSocket | Simpler for one-way server→client push; native EventSource API | — Pending |
| Parameter-level connections | User requirement — drag from specific output param to specific input param | — Pending |
| Full Result port on every cube | Bundles all outputs into one JSON; enables connecting any output downstream | — Pending |
| Connection values override manual | If both exist, connection wins at execution time; intuitive behavior | — Pending |
| Warn on type mismatch, don't block | Dashed orange edge for mismatches; flexibility > strictness | — Pending |
| Leaflet over MapLibre | Lighter weight, no API key, CartoDB dark tiles free | — Pending |
| Alembic for migrations | Standards require it; clean separation from Tracer 42 schema | — Pending |
| Workflow table in public schema | Keeps 12's data separate from research schema | — Pending |

---
*Last updated: 2026-03-03 after initialization*
