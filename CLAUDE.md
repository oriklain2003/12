# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important

The AskUserQuestion tool doesn't work in this environment. Always ask questions directly in the chat conversation instead.

## Project Overview

**Project 12 (12-flow)** is a visual dataflow workflow builder for flight analysis, part of Tracer 42. Users build analysis pipelines by dragging "cubes" (processing nodes) onto a canvas, configuring parameters, connecting outputs to inputs, and executing against the Tracer 42 PostgreSQL database — no code required.

## Commands

### Backend
```bash
cd backend
uv sync                                    # Install/sync Python dependencies
uv run uvicorn app.main:app --reload        # Start FastAPI dev server (port 8000)
uv run alembic upgrade head                 # Run database migrations
uv run alembic revision --autogenerate -m "description"  # Create migration
uv run pytest                               # Run tests
uv run pytest tests/test_foo.py::test_bar   # Run single test
```

### Frontend (when created)
```bash
cd frontend
pnpm install    # Install dependencies
pnpm dev        # Start Vite dev server (port 5173)
```

## Package Managers

- **Python**: `uv` only (no pip, poetry, or pipenv)
- **Node.js**: `pnpm` only (no npm or yarn)

## Architecture

Three-layer system: React frontend → FastAPI backend → PostgreSQL (Tracer 42 RDS, read-only)

### Core Concepts

- **Cube**: Self-contained processing unit with typed input/output parameters and an async `execute` method. Categories: data_source, filter, analysis, aggregation, output.
- **Connections**: Parameter-level (not cube-level) — users wire specific output params to specific input params. Type mismatches show warnings but are allowed.
- **Full Result**: Every cube has a special output bundling all params into one JSON object, connectable to inputs marked `accepts_full_result: true`.
- **Execution**: Topological sort determines order. Manual input values are overridden by connection values. Results capped at 100 rows per cube.

### Backend Structure (`backend/app/`)

| Directory | Purpose |
|-----------|---------|
| `config.py` | Pydantic Settings (DATABASE_URL from .env, CORS, result_row_limit) |
| `database.py` | SQLAlchemy async engine + session dependency |
| `schemas/` | Pydantic models: `cube.py` (ParamType, CubeCategory, ParamDefinition, CubeDefinition), `workflow.py` (WorkflowNode, WorkflowEdge, WorkflowGraph) |
| `models/` | SQLAlchemy ORM models (Workflow with JSONB graph) |
| `routers/` | FastAPI route handlers |
| `engine/` | CubeRegistry (auto-discovery) and WorkflowExecutor (topological sort + SSE progress) |
| `cubes/` | BaseCube subclasses with auto-discovery loader |

### API Endpoints

- `GET /api/cubes/catalog` — list registered cubes
- `POST|GET|PUT|DELETE /api/workflows[/{id}]` — workflow CRUD
- `POST /api/workflows/{id}/run` — execute workflow
- `GET /api/workflows/{id}/run/stream` — SSE progress stream

### Frontend (planned)

React 18 + TypeScript + Vite, React Flow v12+ for canvas, Zustand for state. Dark theme. Routes: `/` (dashboard), `/workflow/new`, `/workflow/:id`.

## Environment

- `.env` at project root contains `DATABASE_URL` pointing to Tracer 42 AWS RDS PostgreSQL
- Database is read-only from this project's perspective
- Config loads `.env` via pydantic-settings (`backend/app/config.py`)

## Planning Files

- `PROJECT.md` — Full specification (cubes, parameters, connections, execution model, UI layout)
- `PLAN.md` — 7-phase implementation roadmap with detailed deliverables
- `.planning/REQUIREMENTS.md` — 48 v1 requirements mapped to phases
- `.planning/ROADMAP.md` — Phase breakdown
- `.planning/STATE.md` — Current project status
