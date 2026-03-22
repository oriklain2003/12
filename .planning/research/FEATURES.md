# Feature Research

**Domain:** AI workflow builder agents (conversational + wizard interfaces for visual dataflow pipelines)
**Researched:** 2026-03-22
**Confidence:** MEDIUM — core agent UX patterns verified via multiple sources; domain-specific nuances (flight analysis context) inferred from research

---

## Scope Note

This is a SUBSEQUENT MILESTONE feature document. The existing visual canvas, cube execution, and workflow CRUD are already built. This covers only new AI agent features: Build Agent, Canvas Agent, Cube Expert, Validation Agent, Results Interpreter.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that are assumed present in any AI-assisted workflow builder. Missing these makes the AI feel broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Intent preview before action | Users need to confirm what the agent will do before it rewrites their canvas; established best practice per Smashing Magazine agentic UX guide | MEDIUM | Show "I'll create X cubes connected as Y. Proceed?" before placing anything |
| Clarifying questions before generation | Generating a wrong workflow wastes user trust; a few targeted questions upfront prevents bad output | LOW | Maximum 3 questions in wizard; 1-2 for canvas chat modes |
| Actionable error messages | When AI can't proceed (ambiguous input, unknown cube, LLM error), must explain what to do next — not just fail silently | LOW | Applies to all 5 agents |
| Mode transparency | User must know which mode/agent is active (build vs. optimize vs. error-fix vs. general) | LOW | Visual badge or header label in chat panel; wizard has its own page |
| Partial results on failure | If workflow generation partially succeeds, show what was created rather than all-or-nothing | MEDIUM | Especially important for Canvas Agent |
| Cancellation / discard | User must be able to reject agent suggestions without consequence | LOW | "Discard" button on generated workflow; applies to wizard output and canvas edits |
| Confidence signaling | Agent should communicate uncertainty (e.g., "I couldn't find a cube for X — closest is Y") rather than false confidence | LOW | Gemini LLM output post-processing |
| Structural validation feedback | Before running, show which parameters are missing or unconnected — not just a generic error | MEDIUM | Validation Agent; extends existing type-mismatch pattern already in codebase |

### Differentiators (Competitive Advantage)

Features that distinguish this agent system from generic workflow AI copilots.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Mission-scoped result interpretation | Generic AI explains "what the data shows"; this agent explains "what this means for your flight analysis mission" — contextualizing anomalies, routes, patterns in Tracer 42 terms | HIGH | Requires mission context to be captured in Build Agent wizard and persisted to workflow metadata |
| Wizard with clickable option cards (not free text) | Free-text input for non-technical analysts creates cognitive load; structured option cards (e.g., "What type of analysis?" with 4 choices) guide users to valid cube combinations without knowing cube names | MEDIUM | Purpose-built for non-developer analysts in military/aviation ops context |
| Two-tier cube discovery (summary → full) | Sending all 14+ cube definitions to LLM on every query wastes tokens and degrades quality; summary-first lookup lets Cube Expert confirm relevance before loading full definition | MEDIUM | Token efficiency + accuracy improvement; unique to this architecture |
| Domain-aware cube suggestion | Generic workflow AI recommends generic nodes; this system knows about flight_metadata, normal_tracks, anomaly_reports and can say "for altitude deviation analysis, start with AllFlights + FilterFlights" | MEDIUM | Requires domain context in system prompt (system brief) |
| Mode-switching in single chat panel | Flowise/Langflow require separate flows per use case; this Canvas Agent handles optimize/error-fix/general in one panel with mode buttons | LOW | Differentiates from competitor pattern of separate tool per task |
| Pre-execution structural check summary | Fabric's copilot explains errors after failure; this Validation Agent explains structural issues before running — preventing wasted execution time on broken pipelines | MEDIUM | Proactive vs reactive; meaningful for pipelines that query 76M track rows |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Fully autonomous workflow execution | "Just run the best analysis automatically" sounds powerful | Analysts must own the query logic; auto-execution against 76M-row table with wrong filters is expensive and potentially misleading | Generate workflow, pause, show it to user, require explicit Run click |
| Streaming partial workflow as it's built node-by-node | Feels impressive, shows "thinking" | Partial canvas states confuse users, trigger validation errors mid-generation, and create complex rollback logic | Generate complete workflow in backend, apply atomically to canvas |
| Free-text intent capture for all wizard steps | Flexible for power users | Non-technical analysts produce ambiguous inputs that cause LLM hallucinations on cube selection; kills trust on first bad result | Structured option cards for known dimensions (time range, analysis type, output format); free text only for "describe what you want to find" field |
| Persistent agent memory across sessions | "Remember what I built last week" | Dramatically increases backend complexity; the workflow itself is the artifact — use it | Load existing workflow as context; no separate memory store |
| Undo/redo for agent-applied changes | Seems essential for safety | Workflow undo/redo is already out of scope for the whole app; adding it only for agent edits creates inconsistency | "Discard agent changes" reloads last saved state from DB |
| Multi-turn back-and-forth workflow refinement in wizard | Seems like a natural conversation | Wizard is a one-shot generator: ask questions, generate, done. Multi-turn wizard compounds state management complexity for marginal gain | For refinements, use Canvas Agent chat after generation |
| Inline cube documentation tooltips generated by AI | "Explain this cube to me" inline | Adding LLM calls to hover events creates latency on every hover; expensive and slow | Static cube description field in CubeDefinition; Cube Expert handles deep questions |

---

## Feature Dependencies

```
[Build Agent Wizard UI]
    └──requires──> [Agent Infrastructure (Gemini, skill files, system brief)]
    └──requires──> [Cube Expert sub-agent]
                       └──requires──> [Two-tier catalog tool (summaries + full defs)]
                                          └──depends on──> [Existing: CubeRegistry auto-discovery]

[Canvas Agent Chat Panel]
    └──requires──> [Agent Infrastructure]
    └──requires──> [Cube Expert sub-agent]
    └──enhances──> [Existing: React Flow canvas + Zustand store]

[Validation Agent]
    └──requires──> [Agent Infrastructure (minimal — may be rule-based, not LLM)]
    └──enhances──> [Existing: WorkflowExecutor type-mismatch warnings]
    └──must precede──> [Run button trigger]

[Results Interpreter]
    └──requires──> [Agent Infrastructure]
    └──requires──> [Mission context captured by Build Agent]
    └──enhances──> [Existing: SSE execution results + per-cube result panels]

[Mission context]
    └──captured by──> [Build Agent Wizard]
    └──persisted in──> [Workflow metadata (DB)]
    └──consumed by──> [Results Interpreter]
    └──consumed by──> [Canvas Agent optimize mode]
```

### Dependency Notes

- **Cube Expert requires two-tier catalog tool:** The LLM must not receive all full cube definitions on every request — that's 14+ verbose JSON blobs. Summaries browse, full definitions load on demand. This is a backend tool, not a UI feature.
- **Results Interpreter requires mission context from Build Agent:** If a user builds manually (not via wizard), Results Interpreter falls back to generic flight-analysis framing. The wizard is the preferred path for full agent capability.
- **Validation Agent is mostly rule-based:** Unlike the other agents, pre-flight validation (missing params, unconnected required inputs, cycles) is deterministic. LLM only adds value for the explanation layer, not the detection layer. Keep detection in Python, use LLM only for human-readable explanation.
- **Canvas Agent depends on Zustand store serialization:** Canvas Agent must read current workflow state to give context-aware suggestions. Already solved — Zustand store serializes to WorkflowGraph format.

---

## MVP Definition

### Launch With (v1 = this milestone)

- [ ] **Agent infrastructure** — Gemini integration, skill files, system brief with Tracer 42 domain context. Everything else depends on this.
- [ ] **Cube Expert sub-agent + two-tier catalog tool** — Foundation for cube recommendations in Build and Canvas agents.
- [ ] **Build Agent wizard UI** — Clickable option cards (not free text), 3-5 targeted questions, generates complete workflow. Most impactful for new users.
- [ ] **Validation Agent** — Pre-run structural checks with human-readable explanations. Low complexity, high value, prevents wasted queries against large DB.
- [ ] **Canvas Agent chat panel** — 3 modes (optimize, error-fix, general). Panel UI + backend routing.
- [ ] **Results Interpreter** — Post-execution explanation in mission context. Triggered from results panel.

### Add After Validation (v1.x)

- [ ] **Wizard history / suggested re-runs** — After analyst uses wizard once, suggest "run similar analysis" based on past mission types. Trigger: analyst re-visits wizard page frequently.
- [ ] **Canvas Agent inline suggestions** — Proactive suggestions ("This AllFlights cube has no time filter — add one to improve performance?") without user prompting. Add when chat panel usage data shows passive users.

### Future Consideration (v2+)

- [ ] **Natural language to cube parameter values** — "Show flights last Tuesday" → auto-fills time range params. Requires parameter-level LLM integration, significant complexity.
- [ ] **Agent-generated cube stubs** — AI writes a new cube class when no existing cube matches. Out of scope (custom cube creation is explicitly deferred).
- [ ] **Cross-workflow insights** — "You ran similar analysis 3 times — here's what changed." Requires workflow history analysis beyond current scope.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Agent infrastructure (Gemini, skill files) | HIGH | MEDIUM | P1 |
| Cube Expert + two-tier catalog tool | HIGH | MEDIUM | P1 |
| Build Agent wizard UI | HIGH | MEDIUM | P1 |
| Validation Agent (rule-based + explanation) | HIGH | LOW | P1 |
| Canvas Agent chat panel (3 modes) | HIGH | MEDIUM | P1 |
| Results Interpreter | MEDIUM | MEDIUM | P1 |
| Intent preview before canvas modification | HIGH | LOW | P1 |
| Mission context persistence in workflow | MEDIUM | LOW | P1 |
| Confidence signaling in agent output | MEDIUM | LOW | P2 |
| Wizard history / suggested re-runs | LOW | MEDIUM | P3 |
| Natural language to param values | HIGH | HIGH | P3 |

**Priority key:**
- P1: Must have for this milestone
- P2: Should have, add when possible
- P3: Defer to v2+

---

## Competitor Feature Analysis

| Feature | Microsoft Fabric Copilot | Flowise/Langflow | 12-flow AI Agents |
|---------|--------------------------|------------------|--------------------|
| Build from natural language | Yes — pipeline generation from plain text | Yes — graph generation from prompt | Wizard with option cards (structured, not free text) |
| Error fixing | Yes — error insights copilot, per-activity and aggregate | Fallback nodes, basic error display | Canvas Agent error-fix mode with cube-level context |
| Optimization suggestions | Yes — /optimize in-cell command | Limited | Canvas Agent optimize mode with domain awareness |
| Result explanation | No | No | Results Interpreter with mission context (differentiator) |
| Pre-flight validation | No — errors surface post-run | No | Validation Agent (proactive, before execution) |
| Domain-specific cube catalog | No — generic components | No — generic nodes | Cube Expert with Tracer 42 flight/track/anomaly context |
| Two-tier catalog lookup | No | No | Yes — token-efficient summary-first pattern |
| Structured wizard (not free text) | No | No | Yes — option cards for non-technical analysts |

---

## Sources

- [Designing For Agentic AI: Practical UX Patterns — Smashing Magazine](https://www.smashingmagazine.com/2026/02/designing-agentic-ai-practical-ux-patterns/) — HIGH confidence; detailed agentic UX patterns
- [AI-Powered Troubleshooting for Fabric Pipeline Errors — Microsoft Fabric Blog](https://blog.fabric.microsoft.com/en-us/blog/ai-powered-troubleshooting-for-fabric-data-pipeline-error-messages/) — HIGH confidence; production copilot for pipeline error analysis
- [Natural Language to Generate and Explain Pipeline Expressions — Microsoft Fabric](https://blog.fabric.microsoft.com/en-US/blog/preview-natural-language-to-generate-and-explain-pipeline-expressions-with-copilot) — HIGH confidence; pipeline generation patterns
- [Building Effective Agents — Anthropic](https://www.anthropic.com/research/building-effective-agents) — HIGH confidence; orchestration patterns, tool design, human-in-the-loop
- [Top AI Agent Platforms for Enterprises 2026 — StackAI](https://www.stackai.com/blog/the-best-ai-agent-and-workflow-builder-platforms-2026-guide) — MEDIUM confidence; platform comparison
- [Agentic Workflows in 2026 — Vellum AI](https://vellum.ai/blog/agentic-workflows-emerging-architectures-and-design-patterns) — MEDIUM confidence; architecture patterns
- [LangFlow vs Flowise Comparison — Leanware](https://www.leanware.co/insights/compare-langflow-vs-flowise) — MEDIUM confidence; feature comparison
- [Chatbot UX Anti-Patterns — Certainly.io](https://www.certainly.io/blog/top-ux-mistakes-chatbot) — MEDIUM confidence; over-questioning anti-pattern
- [AI UX Patterns — aiuxpatterns.com](https://www.aiuxpatterns.com/) — MEDIUM confidence; pattern catalog

---

*Feature research for: AI workflow builder agents (12-flow v3.0)*
*Researched: 2026-03-22*
