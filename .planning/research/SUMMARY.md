# Project Research Summary

**Project:** 12-flow — Visual Dataflow Workflow Builder (AI Agents v3.0 Milestone)
**Domain:** AI agent system integrated into existing FastAPI + React visual dataflow builder
**Researched:** 2026-03-22
**Confidence:** HIGH

## Executive Summary

12-flow is adding a five-agent AI layer on top of an already-built visual canvas, cube execution engine, and workflow CRUD system. The research covers only the new v3.0 additions: a Build Wizard Agent, Canvas Agent (optimize/fix/general modes), Cube Expert sub-agent, Validation Agent, and Results Interpreter. The existing stack (FastAPI, SQLAlchemy, SSE via sse-starlette, React 18, @xyflow/react, Zustand 5) is proven and unchanged. The only new dependency is `google-genai>=1.68.0` (the GA successor to the deprecated `google-generativeai` SDK). No new backend framework, no LangChain, no frontend chat library — all complexity is in the agent business logic itself.

The recommended architecture is a stateless, SSE-streaming agent layer that slots in alongside existing routers with zero modification to existing code. Agents are plain Python classes backed by Gemini 2.5 Flash; conversation history is client-carried in the POST body; tool dispatch uses Gemini's native function calling in manual (non-streaming) mode for tool turns, then streams the final text response. The Build Agent wizard uses clickable option cards (not free text) — a deliberate UX choice to prevent LLM hallucinations from ambiguous analyst input in the flight-analysis domain. Canvas mutations from agents flow through a single new `applyAgentDiff()` Zustand action to preserve undo history.

The critical risk is context explosion across all five agents: the LLM context window degrades well before its technical limit, and tool results from the flight database (76M rows) can be enormous. Every agent must summarize data before injecting it into context. The second major risk is workflow graph validity — the LLM will hallucinate parameter handle IDs if not forced to call `get_cube_definition` before generating edges. Both risks are addressed at the infrastructure layer before any agent-specific features are built.

## Key Findings

### Recommended Stack

The existing stack requires exactly one new addition: `google-genai>=1.68.0`. This is Google's GA SDK (released May 2025), replacing the deprecated `google-generativeai`. Version 1.67.0 has a known `typing-extensions` bug; 1.68.0 is the minimum safe version. Use `gemini-2.5-flash` for Canvas Agent and Cube Expert (low latency), `gemini-2.5-pro` for Build Agent where reasoning depth matters more. The async client (`client.aio`) is required — synchronous Gemini calls inside async FastAPI handlers will block the event loop and freeze concurrent SSE streams.

Frontend requires zero new packages. The wizard is a `useState`-managed step component (~80 lines); the chat panel streams SSE via `fetch + ReadableStream` using the same pattern already proven for workflow execution. Adding Vercel AI SDK, react-chatbotify, or any chat library would impose UI opinions incompatible with the dark tactical ONYX theme.

**Core technologies:**
- `google-genai>=1.68.0`: Gemini LLM client — GA SDK, async-native, native function calling, already used in tracer-api
- `sse-starlette` (existing): Agent token streaming — same transport as workflow execution, no new dependencies
- `@xyflow/react` (existing): Canvas mutations from agents via new `applyAgentDiff()` action
- `zustand` (existing): New `chatStore` and `wizardStore` slices for agent conversation and wizard state

### Expected Features

All P1 features must ship in this milestone. Six feature groups are all table stakes for any AI-assisted workflow builder.

**Must have (table stakes):**
- Intent preview before canvas modification — confirm before agent rewrites the canvas
- Clarifying questions before generation — 3 questions max in wizard, 1-2 in chat modes
- Validation Agent pre-run checks — structural issues explained before execution, not after
- Actionable error messages — all 5 agents must explain failure paths
- Mode transparency — visual badge showing which agent mode is active
- Cancellation / discard — reject agent suggestions without consequence

**Should have (competitive differentiators):**
- Build Wizard with clickable option cards — structured choices for non-technical analysts; no free text for cube selection
- Two-tier cube discovery (browse summary → full definition) — token efficiency + accuracy; prevents catalog overload
- Mission-scoped result interpretation — Results Interpreter contextualizes findings in Tracer 42 flight-analysis terms
- Pre-execution validation — Validation Agent is proactive vs. competitors' reactive post-failure errors
- Domain-aware cube suggestion — system prompt carries Tracer 42 flight/track/anomaly context

**Defer (v2+):**
- Natural language to parameter values ("show flights last Tuesday" → auto-fill time range)
- Wizard history / suggested re-runs (add after usage data confirms analyst re-visit pattern)
- Agent-generated cube stubs (out of scope — custom cube creation deferred)
- Cross-workflow insights

### Architecture Approach

The agent layer is a one-way addition: new code imports from existing packages (CubeRegistry, WorkflowGraph schema, existing SSE infrastructure) but existing packages never import from agents. The `app/agents/` package is the isolation boundary. Three HTTP endpoints are added to a new `app/routers/agent.py`: `POST /api/agent/chat` (SSE stream for Canvas and Build agents), `POST /api/agent/validate` (synchronous, no streaming), and `POST /api/agent/interpret` (Results Interpreter). All agents are stateless — history is client-carried. The Cube Expert sub-agent is a plain Python object instantiated inside Canvas and Build agents, never exposed as an HTTP endpoint.

**Major components:**
1. `app/agents/base_agent.py` — Abstract base: Gemini client init, skill file loading, streaming loop, manual tool dispatch
2. `app/agents/tools.py` — Pure Python tool functions (list_cubes_summary, get_cube_detail, build_workflow_graph, etc.); testable without LLM
3. `app/agents/cube_expert.py` — Sub-agent for two-tier catalog lookup; called by Canvas and Build agents as a Python object
4. `app/agents/canvas_agent.py` — Three modes (optimize/fix/general); receives serialized graph; streams diffs back
5. `app/agents/build_agent.py` — Wizard mode; accepts step context; generates complete workflow on final step
6. `app/agents/validation_agent.py` — Structural checks in pure Python; LLM only for human-readable explanations
7. `app/agents/interpreter_agent.py` — Post-execution result interpretation with mission context from workflow metadata
8. `src/store/chatStore.ts` + `wizardStore.ts` — New Zustand slices; chatStore owns conversation history
9. `src/components/Agent/ChatPanel.tsx` — Collapsible sidebar in EditorPage; sibling to canvas, not nested inside ReactFlowProvider
10. `src/pages/BuildWizardPage.tsx` — New route `/workflow/build`; option card steps

### Critical Pitfalls

1. **Invalid workflow graph connections from LLM hallucination** — Force `get_cube_definition` calls before any edge generation via system prompt and Gemini `tool_config: ANY`. Validate every generated graph against live catalog data (Pydantic + WorkflowExecutor validation) before delivering to frontend. Never skip validation.

2. **Context explosion in multi-turn conversations** — Never pass raw cube execution results as tool context. Summarize to `{cube, result_count, sample[3 rows], columns}`. Prune conversation history at 50k tokens. Pass the workflow graph as a structured reference, not full JSON, on each turn.

3. **Tool catalog overload degrades cube selection accuracy** — Enforce two-tier catalog access architecturally: `browse_catalog()` returns summaries only; `get_cube_definition(cube_name)` loads one cube on demand. Never inline all cube definitions in the system prompt. Cap tools per agent at 8 or fewer.

4. **Gemini returning text instead of tool call** — Use `tool_config: ANY` when tool calls are mandatory (catalog lookup before generation). Validate every response for `function_call` parts before treating it as text. Test each tool definition in isolation.

5. **Blocking event loop with synchronous Gemini calls** — Use `client.aio.models.generate_content_stream()` exclusively in async FastAPI handlers. This breaks concurrent workflow SSE streams if violated — the failure mode is non-obvious and affects all users, not just the agent requester.

6. **Agent edits breaking canvas state** — Agent-driven canvas mutations must go through atomic `applyAgentDiff()` on flowStore, which calls `pushSnapshot()` first. Never patch nodes incrementally or replace entire canvas state without snapshot.

7. **SSE connection leaks when user disconnects** — Add `await request.is_disconnected()` check before each `yield` in agent SSE generators. The existing workflow SSE pattern does not include this — agent conversations are longer and user-interruptible.

8. **Sub-agent context explosion** — Pass only the task description to Cube Expert, not the orchestrator's full history. Enforce a structured response schema (Pydantic) to prevent verbose prose. Cap sub-agent turns at 3.

## Implications for Roadmap

Based on research, all pitfalls resolve to a single prerequisite: the agent infrastructure must be built correctly before any agent-specific features. The build order is dependency-driven.

### Phase 1: Agent Infrastructure
**Rationale:** All 5 agents depend on this. Getting Gemini integration, tool dispatch, context management, and streaming right here prevents every critical pitfall. Building agents on a broken foundation means rework across all subsequent phases.
**Delivers:** Gemini client (`base_agent.py`), skill file loading, SSE streaming endpoint (`agent.py` router), two-tier catalog tools (`tools.py`), client-carried history pattern, disconnect handling, async-only LLM call enforcement
**Addresses:** Intent preview, mode transparency, actionable error messages (all table-stakes UX features depend on working infrastructure)
**Avoids:** Pitfalls 1, 2, 3, 4, 5, 6, 7, 8 — all are infrastructure-layer problems; this phase is where prevention happens
**Research flag:** Standard patterns — Gemini SDK docs are complete; SSE pattern is proven in codebase. Skip `/gsd:research-phase`.

### Phase 2: Cube Expert Sub-Agent + Validation Agent
**Rationale:** Cube Expert is a dependency of both Canvas Agent and Build Agent. Validation Agent is lowest complexity, highest value, and pure Python — fast win that blocks no user on broken pipelines. Both can be built and tested before any frontend work.
**Delivers:** `cube_expert.py` with two-tier catalog tool dispatch; `validation_agent.py` structural checks; `POST /api/agent/validate` endpoint; inline validation warnings on CubeNode
**Uses:** `tools.py` from Phase 1; existing CubeRegistry; Pydantic validation against live catalog
**Implements:** Two-tier catalog pattern; sub-agent boundary (task-only context handoff)
**Avoids:** Pitfalls 1 (catalog validation), 2 (tool overload), 5 (sub-agent context explosion)
**Research flag:** Standard patterns. Skip `/gsd:research-phase`.

### Phase 3: Canvas Agent Chat Panel
**Rationale:** Canvas Agent is the primary ongoing interaction surface for users who already know how to build workflows. Requires Phase 1 (infrastructure) and Phase 2 (Cube Expert). The frontend chat panel and `applyAgentDiff()` Zustand action both land here.
**Delivers:** `canvas_agent.py` (3 modes: optimize/fix/general); `chatStore.ts`; `ChatPanel.tsx` component in EditorPage; `flowStore.applyAgentDiff()` action; `src/api/agent.ts` streaming client
**Implements:** Canvas Agent Chat Flow data path; AgentDiff atomic application; mode-switching UI
**Avoids:** Pitfalls 3 (context history pruning in chatStore), 6 (atomic canvas mutations), 7 (disconnect handling)
**Research flag:** The `applyAgentDiff` / React Flow interaction is worth verifying against React Flow v12+ docs during planning.

### Phase 4: Build Wizard Agent + UI
**Rationale:** Build Wizard is highest user-facing value for new analysts but has the most moving parts (multi-step UI, Cube Expert integration, workflow generation). Comes after Canvas Agent because the wizard agent reuses the same infrastructure and the canvas it generates will be edited with the Canvas Agent.
**Delivers:** `build_agent.py`; `wizardStore.ts`; `BuildWizardPage.tsx` at `/workflow/build`; option card components; mission context persistence in workflow metadata; graph generation with full validation pass
**Addresses:** Build wizard with option cards (differentiator); domain-aware cube suggestion; mission context captured for Results Interpreter
**Avoids:** Pitfall 1 (mandatory catalog lookup before edge generation); anti-feature of free-text intent capture
**Research flag:** Multi-step wizard state management with Zustand is standard. Skip `/gsd:research-phase`.

### Phase 5: Results Interpreter
**Rationale:** Depends on mission context from Build Wizard (Phase 4) and real execution results. Comes last because it requires all prior phases to be exercised to generate meaningful test data.
**Delivers:** `interpreter_agent.py`; `POST /api/agent/interpret` endpoint; trigger button in results drawer; mission-contextual explanation of execution output
**Addresses:** Mission-scoped result interpretation (primary differentiator vs. Fabric Copilot and Flowise — neither has post-execution domain-aware explanation)
**Avoids:** Pitfall 3 (result summarization — pass row counts and samples, not raw result JSON)
**Research flag:** Standard LLM summarization pattern. Skip `/gsd:research-phase`.

### Phase Ordering Rationale

- Infrastructure-first is mandatory: every pitfall in PITFALLS.md maps to the infrastructure phase. Building Canvas Agent or Build Agent without validated infrastructure leads to rework.
- Cube Expert and Validation Agent are bundled in Phase 2 because they share the same tool layer and can both be tested independently without frontend.
- Canvas Agent before Build Wizard reflects architectural dependency (Cube Expert must exist) and practical user impact (existing users benefit from chat before new users benefit from wizard).
- Results Interpreter is last because it cannot be properly tested without real execution results flowing through a mission-context workflow, which requires the wizard.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Canvas Agent):** Verify `applyAgentDiff` interaction with React Flow v12+ handle validation — specifically that adding nodes atomically before edges does not produce broken edge renders.

Phases with standard patterns (skip `/gsd:research-phase`):
- **Phase 1:** Gemini SDK patterns fully documented; SSE pattern proven in codebase.
- **Phase 2:** Pydantic validation patterns standard; Cube Expert is a bounded Python component.
- **Phase 4:** Wizard state machine with Zustand is straightforward; Build Agent uses same base as Canvas Agent.
- **Phase 5:** LLM result summarization is well-documented.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Official SDK docs verified; existing codebase inspected directly; version constraints confirmed from GitHub releases |
| Features | MEDIUM | Core agent UX patterns verified via Smashing Magazine and Anthropic guides; domain-specific flight analysis nuances are inferred |
| Architecture | HIGH | Built on direct inspection of existing codebase (registry, executor, schemas, flowStore, EditorPage); Gemini patterns from official SDK |
| Pitfalls | MEDIUM-HIGH | SDK behavior pitfalls from official docs; context explosion from peer-reviewed research (Hong et al., 2025); React Flow integration from community reports |

**Overall confidence:** HIGH

### Gaps to Address

- **Gemini `tool_config: ANY` behavior with streaming:** The research confirms that automatic function calling combined with streaming is unreliable. The manual tool dispatch pattern is the safe choice, but the exact token cost of the non-streaming tool turn vs. streaming final turn should be measured in Phase 1 spike testing.
- **React Flow v12+ handle validation on atomic node+edge insertion:** The `applyAgentDiff` implementation needs to confirm that batch-inserting nodes and edges in a single Zustand update renders correctly. Verify during Phase 3 planning.
- **Gemini API key in existing tracer-api vs. 12-flow:** `tracer-api/pyproject.toml` has `google-genai>=0.2.0,<1.0.0` (outdated). The 12-flow backend is a separate process — no conflict — but if the two are ever merged, the version constraint needs updating.
- **Concurrent Gemini rate limits:** The project is internal with expected 1-10 concurrent users. Gemini Flash rate limits are generous at this scale. No action needed for v3.0 but document the threshold (~50 concurrent users) where per-IP queuing becomes necessary.

## Sources

### Primary (HIGH confidence)
- [googleapis/python-genai GitHub releases](https://github.com/googleapis/python-genai/releases) — v1.68.0 confirmed stable March 18, 2026
- [Google Gen AI SDK documentation](https://googleapis.github.io/python-genai/) — async streaming, function calling, chat session patterns
- [Gemini API function calling guide](https://ai.google.dev/gemini-api/docs/function-calling) — tool_config modes, multi-turn pattern
- [google-generativeai deprecation notice](https://github.com/google-gemini/deprecated-generative-ai-python) — confirms EOL November 30, 2025
- Existing 12-flow codebase (direct inspection) — engine/registry.py, engine/executor.py, routers/workflows.py, store/flowStore.ts, pages/EditorPage.tsx, schemas/cube.py, pyproject.toml

### Secondary (MEDIUM confidence)
- [Designing For Agentic AI — Smashing Magazine](https://www.smashingmagazine.com/2026/02/designing-agentic-ai-practical-ux-patterns/) — intent preview, confirmation patterns, clarifying questions UX
- [Building Effective Agents — Anthropic](https://www.anthropic.com/research/building-effective-agents) — orchestration patterns, tool design, human-in-the-loop
- [AI-Powered Troubleshooting for Fabric Pipeline Errors — Microsoft Fabric Blog](https://blog.fabric.microsoft.com/en-us/blog/ai-powered-troubleshooting-for-fabric-data-pipeline-error-messages/) — competitor feature comparison
- [Context Engineering for AI Agents 2025](https://promptbuilder.cc/blog/context-engineering-agents-guide-2025) — context budget management
- [The Multi-Agent Trap — Towards Data Science](https://towardsdatascience.com/the-multi-agent-trap/) — sub-agent context explosion patterns
- [Architecting efficient context-aware multi-agent framework — Google Developers Blog](https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production/) — context management in production

### Tertiary (LOW confidence)
- [Multi-agent orchestration patterns — DEV Community](https://dev.to/nebulagg/multi-agent-orchestration-a-guide-to-patterns-that-work-1h81) — pattern validation only
- [AI Tool Overload — Jenova.ai](https://www.jenova.ai/en/resources/mcp-tool-scalability-problem) — tool count degradation data
- [LangFlow vs Flowise Comparison — Leanware](https://www.leanware.co/insights/compare-langflow-vs-flowise) — competitor feature comparison

---
*Research completed: 2026-03-22*
*Ready for roadmap: yes*
