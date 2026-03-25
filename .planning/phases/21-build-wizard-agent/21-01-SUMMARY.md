---
phase: 21-build-wizard-agent
plan: "01"
subsystem: backend-agents
tags: [agents, wizard, workflow-generation, gemini, tools]
dependency_graph:
  requires: []
  provides: [wizard-tools, build-agent-skill]
  affects: [agent-router, tool-registry]
tech_stack:
  added: []
  patterns: [agent_tool-decorator, pass-through-tools, validate-before-save]
key_files:
  created:
    - backend/app/agents/tools/wizard_tools.py
  modified:
    - backend/app/agents/tools/__init__.py
    - backend/app/agents/skills/build_agent.md
    - backend/app/agents/router.py
decisions:
  - "Wizard tools follow pass-through pattern for present_options and show_intent_preview — LLM constructs response; frontend renders structured data"
  - "generate_workflow validates via validate_graph() before DB insert; returns validation_failed dict (not exception) so LLM can self-correct and retry"
  - "pro_personas set pattern in router.py enables future personas to opt into pro model without changing conditional logic"
metrics:
  duration: "~10 minutes"
  completed: "2026-03-25"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 3
---

# Phase 21 Plan 01: Build Wizard Tools and Skill File Summary

Three backend wizard tools registered in the agent tool registry, Build Agent skill file expanded to 77-line comprehensive conversation guide, and model routing updated to use gemini-2.5-pro for the build_agent persona.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create wizard tools | 06e002b | wizard_tools.py (created), __init__.py (updated) |
| 2 | Expand skill file and update model routing | 78c48d0 | build_agent.md (replaced), router.py (updated) |

## What Was Built

### wizard_tools.py

Three `@agent_tool`-decorated async functions:

**present_options** — Pass-through tool. Accepts `question`, `options` (array of `{id, title, description}` objects), and `multi_select` bool. Returns the same data as a dict. Frontend renders as interactive card selectors.

**show_intent_preview** — Pass-through tool. Accepts `mission_name`, `mission_description`, `nodes` (planned cubes), and `connections`. Returns structured preview dict. Frontend renders as mini-graph with "Build This" / "Adjust Plan" buttons.

**generate_workflow** — Full DB-writing tool. Accepts `name`, `mission_description`, `analysis_intent`, `nodes`, and `edges`. Builds WorkflowGraph, validates via `validate_graph(graph, ctx.cube_registry)`, returns `{"status": "validation_failed", "errors": [...]}` if errors found. On success, creates Workflow ORM instance, embeds mission metadata in `graph_json.metadata.mission`, commits to DB, returns `{"status": "created", "workflow_id": str(wf.id), "workflow_name": wf.name}`.

### build_agent.md

Replaced 16-line placeholder with 77-line comprehensive skill:
- **Your Tools** section: lists all 6 tools with when to use each
- **Conversation Flow** with 5 steps: discover mission, recommend data source, suggest filters, show preview, generate workflow
- **Rules** section: hallucination prevention (always call get_cube_definition), multi_select guidance, validation_failed retry instructions (up to 2 retries before escalating to analyst)

### router.py

Changed model selection from `if persona == "canvas_agent"` to `pro_personas = {"canvas_agent", "build_agent"}` + `if persona in pro_personas`, routing build_agent to gemini-2.5-pro.

## Verification

```
Tools OK: ['read_workflow_graph', 'propose_graph_diff', 'read_execution_errors', 'read_execution_results', 'present_options', 'show_intent_preview', 'generate_workflow']
Skill file OK: 77 lines
Router OK: pro_personas with build_agent
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all three tools are fully wired. present_options and show_intent_preview are intentionally pass-through (no DB interaction needed — they return LLM-supplied data for frontend rendering). generate_workflow performs real DB writes.

## Self-Check: PASSED

- `backend/app/agents/tools/wizard_tools.py` — exists and imports cleanly
- `backend/app/agents/tools/__init__.py` — contains `import app.agents.tools.wizard_tools`
- `backend/app/agents/skills/build_agent.md` — 77 lines
- `backend/app/agents/router.py` — contains `pro_personas` and `build_agent`
- Commits 06e002b and 78c48d0 verified in git log
