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
| 1 | Types, Schemas & Project Scaffolding | In Progress | 2/? |
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

- Python cube.py uses STRING_ARRAY/NUMBER_ARRAY/FLIGHT_IDS/JSON enum values (not list_of_strings etc as in plan spec) — TypeScript mirrors actual implementation
- CubeDefinition uses `id` field (not `cube_id`) — matches actual backend/app/schemas/cube.py
- WorkflowResponse.id typed as `string` in TypeScript (UUID serializes as string over JSON)

## Notes

- Backend scaffold files already exist from initial session (pyproject.toml, schemas, config, database)
- DATABASE_URL configured in .env pointing to Tracer 42 PostgreSQL on AWS RDS
- uv and pnpm both available on the system
- Frontend scaffold completed: `cd frontend && pnpm dev` starts on port 5173
- TypeScript type contracts established for cube and workflow data models

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 01 | 01 | ~5 min | 3 | 5 |
| 01 | 02 | 2 min | 2 | 18 |

---
*Last session: 2026-03-03T19:52:56Z — Completed 01-02-PLAN.md (frontend scaffold + TypeScript types)*
