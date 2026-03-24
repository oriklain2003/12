# Requirements: Project 12 — AI Workflow Agents

**Defined:** 2026-03-22
**Core Value:** Users can build and run custom flight analysis pipelines visually — now assisted by AI agents that help create, edit, optimize, and debug workflows.

## v3.0 Requirements

Requirements for AI Workflow Agents milestone. Each maps to roadmap phases.

### Agent Infrastructure

- [x] **INFRA-01**: Gemini client integration (`google-genai>=1.68.0`) with async execution via `run_in_executor`
- [x] **INFRA-02**: SSE streaming endpoint for agent chat responses
- [x] **INFRA-03**: Skill files (system prompts) for each agent persona
- [x] **INFRA-04**: System brief document with Tracer 42 domain context for all agents
- [x] **INFRA-05**: Agent tool dispatch system (internal function calls, not HTTP)
- [x] **INFRA-06**: Context management (client-carried history, result summarization to avoid context explosion)
- [x] **INFRA-07**: Mission context persistence in workflow metadata (JSONB)

### Cube Expert

- [x] **CUBE-01**: Two-tier catalog tool — summary endpoint (names + descriptions by category)
- [x] **CUBE-02**: Full cube definition loader (params, types, constraints on demand)
- [x] **CUBE-03**: Cube Expert sub-agent that reasons about which cube fits a use case

### Build Agent

- [ ] **BUILD-01**: Wizard page with clickable option cards (analysis type, data source, filters, output)
- [ ] **BUILD-02**: Mission discovery via 3-5 structured questions
- [ ] **BUILD-03**: Workflow graph generation from mission spec (complete graph JSON)
- [ ] **BUILD-04**: Intent preview — show summary of what will be built before applying
- [ ] **BUILD-05**: Generated workflow loaded onto canvas with validation check

### Canvas Agent

- [ ] **CANVAS-01**: Chat panel UI component integrated into editor page
- [ ] **CANVAS-02**: Mode switching (optimize / error-fix / general) with visual indicator
- [ ] **CANVAS-03**: Canvas context — agent reads current workflow graph state
- [ ] **CANVAS-04**: Optimize mode — suggest faster/simpler cube configurations
- [ ] **CANVAS-05**: Error-fix mode — read cube errors from last run, diagnose pipeline failures
- [ ] **CANVAS-06**: General mode — find cubes, suggest edits, answer questions
- [ ] **CANVAS-07**: `applyAgentDiff()` Zustand action for atomic canvas updates with snapshot

### Validation Agent

- [ ] **VALID-01**: Rule-based structural checks (missing params, dangling inputs, type mismatches, cycles)
- [ ] **VALID-02**: Human-readable explanation of issues via LLM
- [x] **VALID-03**: Pre-run trigger — validation runs before workflow execution

### Results Interpreter

- [ ] **RESULT-01**: Post-execution analysis triggered from results panel
- [ ] **RESULT-02**: Mission-context explanation (uses mission metadata from Build Agent)
- [ ] **RESULT-03**: Fallback generic flight-analysis framing when no mission context exists

## Future Requirements

### Post-v3.0 Enhancements

- **FUTURE-01**: Wizard history / suggested re-runs based on past mission types
- **FUTURE-02**: Canvas Agent proactive inline suggestions (unprompted performance tips)
- **FUTURE-03**: Natural language to cube parameter values ("flights last Tuesday" → auto-fill time range)
- **FUTURE-04**: Cross-workflow insights ("you ran similar analysis 3 times — here's what changed")

## Out of Scope

| Feature | Reason |
|---------|--------|
| Fully autonomous workflow execution (no user confirmation) | Analysts must own query logic; auto-execution against 76M rows is risky |
| Streaming partial workflow node-by-node during generation | Partial canvas states confuse users, trigger validation errors mid-build |
| Persistent agent memory across sessions | Workflow itself is the artifact; no separate memory store needed |
| Undo/redo for agent edits | Out of scope for entire app; "discard changes" reloads last saved state |
| Multi-turn wizard refinement | Wizard is one-shot; use Canvas Agent for refinements after generation |
| AI-generated hover tooltips on cubes | LLM calls on hover events create latency; use static cube descriptions |
| Agent-generated custom cube stubs | Custom cube creation explicitly deferred from project scope |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 18 | Complete |
| INFRA-02 | Phase 18 | Complete |
| INFRA-03 | Phase 18 | Complete |
| INFRA-04 | Phase 18 | Complete |
| INFRA-05 | Phase 18 | Complete |
| INFRA-06 | Phase 18 | Complete |
| INFRA-07 | Phase 18 | Complete |
| CUBE-01 | Phase 19 | Complete |
| CUBE-02 | Phase 19 | Complete |
| CUBE-03 | Phase 19 | Complete |
| VALID-01 | Phase 19 | Pending |
| VALID-02 | Phase 19 | Pending |
| VALID-03 | Phase 19 | Complete |
| CANVAS-01 | Phase 20 | Pending |
| CANVAS-02 | Phase 20 | Pending |
| CANVAS-03 | Phase 20 | Pending |
| CANVAS-04 | Phase 20 | Pending |
| CANVAS-05 | Phase 20 | Pending |
| CANVAS-06 | Phase 20 | Pending |
| CANVAS-07 | Phase 20 | Pending |
| BUILD-01 | Phase 21 | Pending |
| BUILD-02 | Phase 21 | Pending |
| BUILD-03 | Phase 21 | Pending |
| BUILD-04 | Phase 21 | Pending |
| BUILD-05 | Phase 21 | Pending |
| RESULT-01 | Phase 22 | Pending |
| RESULT-02 | Phase 22 | Pending |
| RESULT-03 | Phase 22 | Pending |

**Coverage:**
- v3.0 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-03-22*
*Last updated: 2026-03-22 after v3.0 roadmap creation*
