---
phase: 18
plan: 02
subsystem: backend/agents
tags: [agents, skills, system-prompt, persona, skill-loader]
dependency_graph:
  requires: [agents-package]
  provides: [skill-files, skills-loader, system-prompt-combiner]
  affects: [backend/app/agents/skills, backend/app/agents/skills_loader.py]
tech_stack:
  added: []
  patterns: [module-level-cache, glob-discovery, startup-load]
key_files:
  created:
    - backend/app/agents/skills_loader.py
    - backend/app/agents/skills/system_brief.md
    - backend/app/agents/skills/canvas_agent.md
    - backend/app/agents/skills/build_agent.md
    - backend/app/agents/skills/cube_expert.md
    - backend/app/agents/skills/validation_agent.md
    - backend/app/agents/skills/results_interpreter.md
  modified: []
key_decisions:
  - "Skill files are .md on disk, not hardcoded strings in Python — content can be edited without touching Python code"
  - "load_skill_files() uses Path.glob('*.md') for automatic discovery — new persona files just drop in"
  - "_skills is a module-level dict (process-lifetime cache) — cheap, thread-safe reads after startup load"
  - "get_system_prompt() always prepends system_brief — all agents share Tracer 42 domain context"
metrics:
  duration_minutes: 2
  completed_date: "2026-03-24"
  tasks_completed: 2
  files_created: 7
  files_modified: 0
---

# Phase 18 Plan 02: Agent Skill Files and Loader Summary

**One-liner:** Six markdown persona files (system_brief + 5 agents) with glob-discovery loader caching all prompts at startup into a module-level dict

## What Was Built

Two deliverables for the agent system prompt infrastructure:

1. **Skills loader** (`backend/app/agents/skills_loader.py`) — three public functions:
   - `load_skill_files()` — globs all `.md` files from the `skills/` directory into a module-level `_skills` dict; called once at FastAPI lifespan startup
   - `get_skill(name)` — returns cached skill content by filename stem, or empty string
   - `get_system_prompt(persona)` — concatenates `system_brief` + persona with `\n\n` separator; always injects Tracer 42 domain context at the top
   - `get_all_personas()` — returns all skill names excluding `system_brief`

2. **Skill files** (`backend/app/agents/skills/`) — six markdown files:
   - `system_brief.md` — 3,983-char Tracer 42 domain context: cube categories, data sources (all_flights, alison_flights, get_anomalies, get_flight_course, get_learned_paths), filters, analysis cubes, core connection/execution model
   - `canvas_agent.md` — Canvas Agent persona (placeholder for Phase 20): modes (Optimize/Fix/General), tool-call rules
   - `build_agent.md` — Build Wizard persona (placeholder for Phase 21): structured option card process, anti-hallucination rules
   - `cube_expert.md` — Cube Expert sub-agent persona (placeholder for Phase 19): catalog lookup flow, conciseness rule (called by other agents)
   - `validation_agent.md` — Validation Agent persona (placeholder for Phase 19): checks (missing params, dangling inputs, type mismatches, cycles)
   - `results_interpreter.md` — Results Interpreter persona (placeholder for Phase 22): summarize/interpret, 3-5 key findings rule

## Tasks

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Create skill loader module | 6ff1ee5 | backend/app/agents/skills_loader.py, backend/app/agents/__init__.py |
| 2 | Create system brief and five agent persona skill files | 532c03e | 6 .md files in backend/app/agents/skills/ |

## Verification

All plan verification commands passed:

- Import check: `from app.agents.skills_loader import load_skill_files, get_skill, get_system_prompt` — imports OK
- End-to-end: `load_skill_files()` loaded 5 personas + 1 system_brief
- `get_all_personas()` returned exactly 5 names
- `get_skill('system_brief')` returned 3,983 chars
- `get_system_prompt('canvas_agent')` contained both "Tracer 42" and "Canvas Agent"

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

All five persona files are intentional placeholders. Their content will be refined when each agent is implemented:

| File | Stub reason | Resolved in |
|------|-------------|-------------|
| canvas_agent.md | Placeholder — full tool list not defined yet | Phase 20 |
| build_agent.md | Placeholder — option card format not defined yet | Phase 21 |
| cube_expert.md | Placeholder — tool signatures not defined yet | Phase 19 |
| validation_agent.md | Placeholder — check implementations not defined yet | Phase 19 |
| results_interpreter.md | Placeholder — result schema not defined yet | Phase 22 |

These stubs do not block the plan's goal (skill loading infrastructure). The loader works end-to-end with the current content.

## Self-Check: PASSED

Files exist:
- FOUND: backend/app/agents/skills_loader.py
- FOUND: backend/app/agents/skills/system_brief.md
- FOUND: backend/app/agents/skills/canvas_agent.md
- FOUND: backend/app/agents/skills/build_agent.md
- FOUND: backend/app/agents/skills/cube_expert.md
- FOUND: backend/app/agents/skills/validation_agent.md
- FOUND: backend/app/agents/skills/results_interpreter.md

Commits exist:
- FOUND: 6ff1ee5 feat(18-02): create skills loader module
- FOUND: 532c03e feat(18-02): create system brief and five agent persona skill files
