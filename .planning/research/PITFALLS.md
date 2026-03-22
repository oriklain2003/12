# Pitfalls Research

**Domain:** AI agent system added to visual dataflow workflow builder (12-flow v3.0)
**Researched:** 2026-03-22
**Confidence:** MEDIUM-HIGH (combination of official docs, community research, and production reports)

---

## Critical Pitfalls

### Pitfall 1: Generating Workflow Graphs with Invalid Connections

**What goes wrong:**
The Build Agent generates a workflow JSON with connections that reference non-existent parameter names or use wrong parameter types. The LLM "knows" cube names but hallucinates parameter IDs, edge source/target handles, or confuses `output_params` with `input_params`. The generated workflow loads on the canvas but silently produces wrong results or crashes the executor.

**Why it happens:**
The LLM knows the cube API at training time but the catalog is custom-built — no training data for it. When prompted with "build a workflow," the model fills in parameter IDs from memory or inference rather than from the actual catalog definition. Parameter handle IDs in this system are like `__full_result__`, `flight_ids`, `flights` — easy to misremember or conflate. Even with function calling, the model may not bother to retrieve parameter definitions before generating edge connections.

**How to avoid:**
- The Build Agent must always call the catalog tool before generating any workflow. Make this non-optional via system prompt: "You MUST call get_cube_definition before referencing any cube's parameters."
- After generating the workflow graph JSON, run it through the existing WorkflowExecutor's validation logic before returning it to the frontend — never deliver an unvalidated graph.
- Add a dedicated post-generation validation pass: check that every edge's `sourceHandle` and `targetHandle` exist in the respective cube's output/input param lists. Return validation errors back to the agent for correction, not to the user.
- Consider a Pydantic model that validates the generated workflow against live catalog data at the API layer.

**Warning signs:**
- Agents call get_cubes_catalog (summary) but skip get_cube_definition (full params) before generating edges.
- Generated workflows have edges with handle names not in the catalog (check against `ParamDefinition.name`).
- "Works in demo" with hardcoded examples but fails with real catalog data.

**Phase to address:** Agent infrastructure phase (tool definitions and system prompts) — before any UI is built.

---

### Pitfall 2: Tool Catalog Overload Degrades Tool Selection Accuracy

**What goes wrong:**
If the agent is given all 14+ cube definitions as a single tool parameter upfront (or as part of the system prompt), the context fills with cube metadata the agent doesn't need for the current task, tool selection accuracy drops, and the model starts confusing or ignoring cubes. Research shows 5-7 tools is the practical upper bound for consistent accuracy; with 10+ tools, selection errors increase measurably.

**Why it happens:**
This is a fundamental LLM characteristic, not a prompt-writing failure. More tools = more context tokens = higher chance of "lost in the middle" degradation where relevant tools in the middle of a long list are ignored. The planned two-tier catalog design (summaries first, full definitions on demand) is the right instinct but must be enforced architecturally, not just hoped for.

**How to avoid:**
- Implement the two-tier lookup as two separate tools: `browse_catalog()` returns name+category+one-line description for all cubes (small); `get_cube_definition(cube_name)` returns full parameter schema for one cube.
- Never pass all cube definitions in the system prompt. The system brief should reference the catalog tool, not inline it.
- Cap the number of tools per agent at 8 or fewer. The Cube Expert sub-agent pattern is correct — it exists specifically to keep the Build Agent's tool count small.
- Add a planning step before workflow generation: "First call browse_catalog, then call get_cube_definition for each cube you plan to use, then generate the workflow." Make this explicit in the system prompt with numbered steps.

**Warning signs:**
- Agents return workflows using cubes they didn't call get_cube_definition for.
- Token counts for a single agent turn exceed 8,000 tokens.
- Agent selects wrong cube consistently when similar-sounding cubes exist (e.g., GetFlights vs. AllFlights vs. FilterFlights).

**Phase to address:** Agent infrastructure phase — tool definitions are foundational.

---

### Pitfall 3: Context Explosion in Multi-Turn Conversations

**What goes wrong:**
The Canvas Agent (chat panel) accumulates full conversation history including tool call results across multiple turns. Cube execution results from large datasets (10,000-row tables) are passed verbatim as tool results. After 5-6 turns, the context exceeds effective limits, the model starts ignoring earlier instructions, and response quality degrades. This isn't gradual — it collapses suddenly.

**Why it happens:**
Developers assume the 1M-token Gemini context window means "pass everything." Context Rot research (Hong et al., 2025) shows model performance degrades well before the technical limit — the effective high-quality context window is much smaller. Tool results are the worst offender: a single cube returning 10,000 rows of flight data as JSON could be 200,000+ tokens on its own.

**How to avoid:**
- Never pass raw cube execution results as tool context. Summarize: `{"cube": "GetFlights", "result_count": 8432, "sample": [first 3 rows], "columns": [...]}`.
- Implement a context budget. When conversation history exceeds 50% of the target window (e.g., 50k tokens), summarize older turns to 2-3 sentences before the next call.
- The workflow graph itself should be passed as a reference ("current workflow has 4 nodes: ...") not as full JSON on every turn.
- For the Canvas Agent, maintain a separate "working memory" of what changes have been made in the session, distinct from raw conversation history.

**Warning signs:**
- First few turns work well, later turns in the same session become incoherent.
- Agent "forgets" constraints mentioned in the system prompt mid-conversation.
- Token usage per turn grows linearly with conversation length rather than staying roughly constant.

**Phase to address:** Agent infrastructure phase (context management design) and Canvas Agent phase (chat panel implementation).

---

### Pitfall 4: Gemini Function Calling Returns Text Instead of Tool Call

**What goes wrong:**
The agent is supposed to call a tool (e.g., get_cube_definition) but instead returns a text response explaining what it "would" do, or returns partial JSON embedded in markdown. The application parses the response expecting a function call object and throws an error or silently skips the tool call, causing the agent to proceed with hallucinated data.

**Why it happens:**
Gemini's function calling uses `tool_config` to control calling mode. The default mode (`AUTO`) allows the model to choose between text and function calls. If the system prompt or user message doesn't sufficiently establish that a tool call is required, the model may opt for text. Additionally, if the function schemas are unclear or descriptions are vague, the model may not recognize when to use them.

**How to avoid:**
- For tool calls that must happen (e.g., catalog lookup before generation), use `tool_config={"function_calling_config": {"mode": "ANY"}}` to force a function call on that turn.
- Write tool descriptions as imperatives with clear trigger conditions: "Call this function when you need to look up the parameters of a specific cube. Always call this before referencing a cube's parameter names in a workflow."
- Validate every response: check for `function_call` in the response parts before assuming text. Never treat a text response as equivalent to a tool call response.
- Test each tool definition in isolation before integrating into the full agent.

**Warning signs:**
- Agent returns markdown like "I would call get_cube_definition with..." instead of actually calling it.
- Response parsing code has to handle both text and function_call branches in the same place but the text branch is never hit in testing.
- Works in Gemini playground but fails in production code where tool_config isn't set.

**Phase to address:** Agent infrastructure phase — this is a foundational Gemini integration detail.

---

### Pitfall 5: Sub-Agent Context Explosion (Cube Expert Pattern)

**What goes wrong:**
The orchestrating Build Agent spawns the Cube Expert sub-agent and passes its entire conversation history as context. The Cube Expert then returns a verbose response. On the next orchestrator turn, the sub-agent's full response is in the history. After 3-4 sub-agent calls, the orchestrator's context is dominated by sub-agent outputs rather than task state.

**Why it happens:**
The natural implementation serializes the full agent response as a tool result. Multi-agent context explosion is a documented failure mode: each agent in the chain amplifies context size. The multi-agent trap is assuming sub-agents share context efficiently when they actually duplicate it.

**How to avoid:**
- Sub-agent responses must be summarized at the call site before being added to the orchestrator's history. The Cube Expert should return a short structured response: `{"recommended_cubes": [...], "rationale": "one sentence"}`, not a full explanation.
- Never pass the orchestrator's full conversation history to a sub-agent. Pass only the task description and any necessary immediate context.
- Define a strict response schema for the Cube Expert (Pydantic model + Gemini response_schema) to prevent verbose prose responses.
- Cap sub-agent turns at 3: if the Cube Expert can't find a suitable cube in 3 tool calls, return `{"status": "not_found", "suggestion": "..."}` rather than continuing to search.

**Warning signs:**
- Each Build Agent turn takes progressively longer.
- Cube Expert responses are multiple paragraphs rather than structured lists.
- Token counts spike after each sub-agent invocation.

**Phase to address:** Agent infrastructure phase (sub-agent design) and Build Agent implementation phase.

---

### Pitfall 6: Blocking the FastAPI Event Loop with Synchronous Gemini Calls

**What goes wrong:**
The agent endpoint makes a synchronous `google.generativeai` call inside an `async def` endpoint without wrapping it in `run_in_executor`. This blocks the entire event loop for the duration of the LLM call (often 3-15 seconds). While one user's agent request is pending, no other requests — including SSE workflow execution streams — can be served.

**Why it happens:**
The `google.generativeai` Python SDK's `generate_content()` is synchronous by default. Many examples and tutorials use it in synchronous code. Developers copy the examples directly into async FastAPI handlers without realizing the blocking behavior. The existing codebase already uses `run_in_executor` correctly for Kalman filter CPU work (Phase 16 decision) — but a new developer on the agent feature may not connect the pattern.

**How to avoid:**
- Use the async client (`google.generativeai.GenerativeModel` with `await model.generate_content_async(...)`) or wrap sync calls in `asyncio.get_event_loop().run_in_executor(None, sync_fn)`.
- Add a linting comment or architectural note in the agent module: "All LLM calls must be async or wrapped in run_in_executor."
- The existing streaming SSE infrastructure already serves as a model — agent streaming endpoints should follow the same pattern as workflow execution SSE.

**Warning signs:**
- Workflow execution SSE streams freeze or timeout during concurrent agent requests.
- Event loop warning messages in Uvicorn logs about blocked coroutines.
- Agent responses work fine in sequential testing but fail under concurrent load.

**Phase to address:** Agent infrastructure phase (FastAPI endpoint design).

---

### Pitfall 7: Agent Edits Break Existing Canvas State

**What goes wrong:**
The Canvas Agent modifies the workflow by adding/removing nodes or edges. The Zustand store's React Flow state gets out of sync with what the agent sent to the backend. On the next render, React Flow shows stale edge handles, orphaned nodes, or broken connections. Or: the agent's edit applies cleanly in the backend but the frontend doesn't re-render because the store update was partial.

**Why it happens:**
The existing Zustand store is designed for user-driven edits via React Flow's `onNodesChange`/`onEdgesChange` callbacks. An agent-driven edit bypasses this path — it patches the workflow directly. If the frontend re-fetches the workflow and attempts to merge it with local state, conflicts arise. React Flow's internal edge validity depends on the handle IDs being present on mounted nodes — if a node is added by the agent before its incoming edge is rendered, the edge appears broken.

**How to avoid:**
- Define a single "agent edit" operation in the Zustand store: `applyAgentWorkflow(newGraph)` that replaces the entire canvas state atomically rather than patching it. This avoids partial-state bugs.
- After any agent-driven change, the frontend should treat the result as a full workflow replacement (same as loading a saved workflow), not an incremental update.
- Debounce re-renders: if the agent generates a multi-step edit, batch all changes and apply them in one React state update, not node-by-node.
- Test agent edits with the same save/load serialization tests that exist for manual edits.

**Warning signs:**
- "Broken" looking edges after agent edits (dashed where they shouldn't be, or missing entirely).
- Console errors about missing handles from React Flow after agent operations.
- Workflow runs correctly after saving/reloading even though it looks broken on canvas.

**Phase to address:** Canvas Agent implementation phase (frontend integration).

---

### Pitfall 8: Streaming Agent Responses Without Client Disconnect Handling

**What goes wrong:**
The agent endpoint streams tokens back via SSE. The user closes the chat panel or navigates away mid-response. The Gemini generation continues, consuming tokens and holding a server connection open. With multiple concurrent users, leaked connections accumulate and memory grows unboundedly.

**Why it happens:**
The project already uses SSE for workflow execution (sse-starlette). The existing workflow SSE does not need disconnect handling because runs complete quickly and automatically. Agent conversations are longer and user-interruptible. A developer naturally copies the workflow SSE pattern without adding disconnect detection.

**How to avoid:**
- Inject the FastAPI `Request` object into SSE generator functions and check `await request.is_disconnected()` before each `yield`.
- Wrap the Gemini streaming call in a try/finally block: on generator close (client disconnect), cancel any pending Gemini call if the async client supports it.
- Set a maximum token budget per agent response (e.g., 2,000 tokens for Build Agent suggestions) and stop generation early if exceeded.
- Test disconnect handling explicitly: load test with clients that disconnect after 1 second.

**Warning signs:**
- Server memory grows over time with agent usage.
- Long-running agent SSE connections visible in `ss -s` or nginx access logs with no corresponding user.
- Build Agent uses same pattern as workflow SSE but with no disconnect check.

**Phase to address:** Agent infrastructure phase (streaming endpoint design).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Inlining all cube definitions in system prompt | Fast to implement | 10k+ token overhead per request, context pollution, hard to update | Never — use two-tier tool instead |
| Passing raw cube results as tool context | Simple code | Context explosion after 3-4 turns | Never for large result sets |
| Synchronous Gemini calls in async handlers | Familiar SDK usage | Blocks event loop, breaks concurrent SSE | Never in FastAPI async context |
| Hard-coding workflow structure examples in system prompt | Reliable output format | Brittle when catalog evolves, must be kept in sync | Only for initial scaffolding, replace with tool-driven approach |
| Single monolithic agent for all 5 agent types | Less infrastructure | Token waste, poor performance, harder to tune | Never — the planned separation is correct |
| Passing full conversation history to sub-agents | Easier to implement | Context explosion, sub-agent confusion | Never — always summarize before handoff |
| Skipping validation after workflow generation | Faster MVP | Silent broken workflows delivered to users | Never — validation is cheap, debugging broken workflows is expensive |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Gemini function calling | Using `AUTO` mode for required tool calls | Set `tool_config` to `ANY` when tool call is mandatory; `AUTO` only for optional enrichment |
| Gemini streaming | Mixing sync and async SDK usage | Use `generate_content_async()` exclusively in async FastAPI handlers |
| Gemini response schema | Relying on `response_mime_type: "application/json"` alone | Always combine with `response_schema` (Pydantic model or dict schema) for structured output |
| React Flow + agent edits | Patching store node-by-node from agent diffs | Use atomic `applyAgentWorkflow(newGraph)` to replace full canvas state |
| Zustand + agent state | Storing agent conversation history in the same store as canvas state | Separate concerns — agent chat state in its own slice or React state |
| SSE for agent streaming | Copying workflow SSE pattern without disconnect handling | Add `request.is_disconnected()` check in every agent SSE generator |
| Cube Expert sub-agent | Passing orchestrator history to sub-agent | Pass only the task; sub-agent has no memory of the broader session |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Cube catalog loaded on every agent call | Slow first token, 500ms+ overhead per turn | Cache catalog in memory at startup (already done via CubeRegistry) | Immediate |
| Tool schemas regenerated per request | CPU overhead on every call | Build tool definition list once at app startup, not per request | With 10+ concurrent users |
| Agent conversation history grows unbounded | Each turn slower than the last | Implement context pruning at 50k tokens | After 10-15 turns |
| Sub-agent spawned synchronously in orchestrator | Blocks orchestrator turn until sub-agent completes | If sub-agents run in parallel, make them concurrent (asyncio.gather) | With 2+ parallel sub-agents |
| Gemini call per each cube definition fetch | N calls to get N cube details | Batch cube detail fetches where possible; encourage agent to plan all needed cubes upfront | When agent needs 5+ cubes |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Passing user-supplied text directly into SQL via agent tool | SQL injection via LLM-interpreted user input | All cube parameters flow through existing Pydantic validation + parameterized queries; agent tools must use cube API not raw SQL |
| Agent system prompt contains database schema or internal architecture details | Prompt leakage if Gemini API is compromised or user extracts via prompt injection | Keep system prompts generic; cube tool provides schema on demand; no DB credentials in prompt |
| Trusting agent-generated workflow graph without validation | Malformed graph crashes executor or causes unexpected DB queries | Always validate generated graph against catalog schema before execution |
| No rate limiting on agent endpoints | Cost explosion from runaway agent loops or malicious users | Add per-session token budget; the project is internal (no auth) so rate limit by IP or session ID |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Agent makes silent edits to canvas without notification | User doesn't know what changed, can't review before running | Show a diff summary ("Added 2 cubes, modified 1 connection") before applying agent changes; require user confirmation |
| Build wizard has too many free-form questions | Analysts get frustrated with blank text fields | Use clickable option cards for common choices; free text only as an escape hatch |
| Canvas Agent responds with verbose explanations | Users want action, not essays | Cap prose to 2-3 sentences; use structured diff format for workflow changes |
| Agent fails silently when it can't find suitable cubes | User stuck with no feedback | Always return a "best effort" response with what was found and what's missing |
| Wizard agent starts over if user goes back a step | Frustrating if early choices were wrong | Persist wizard state; allow backwards navigation without resetting all selections |
| Agent edits trigger immediate re-render with no loading state | Canvas flickers; user sees broken intermediate state | Show "Applying changes..." overlay during canvas state replacement |

---

## "Looks Done But Isn't" Checklist

- [ ] **Build Agent generates workflow:** Verify it called get_cube_definition for every cube referenced before generating edges, not just browse_catalog.
- [ ] **Canvas Agent chat panel:** Verify the conversation history is pruned at a token limit, not just passed raw each turn.
- [ ] **Cube Expert sub-agent:** Verify it receives only the task description, not the full orchestrator conversation history.
- [ ] **Agent SSE streaming:** Verify client disconnect handling is in place — kill the Gemini call when the client disconnects.
- [ ] **Gemini tool_config:** Verify `tool_config` is set to `ANY` for turns where a tool call is required, not left as default `AUTO`.
- [ ] **Generated workflow validation:** Verify every agent-generated workflow is validated against live catalog data before being sent to the frontend.
- [ ] **React Flow canvas update:** Verify agent-driven workflow changes go through `applyAgentWorkflow()` (atomic replace) not incremental node patches.
- [ ] **Async Gemini calls:** Verify all `generate_content` calls in FastAPI handlers are `generate_content_async` or wrapped in `run_in_executor`.
- [ ] **Results Interpreter:** Verify it receives a result summary (row counts, samples) not raw 10k-row result JSON.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Invalid connections generated by agent | LOW | Validation layer catches it before frontend; agent retries with corrected schema; no user impact |
| Context explosion mid-session | MEDIUM | Clear conversation history and restart agent session; user loses context but workflow is preserved |
| Event loop blocked by sync Gemini call | HIGH | Requires code change + redeploy; all concurrent requests affected until fixed |
| Agent edits break canvas state | MEDIUM | User can reload workflow from DB (save is preserved); canvas state regenerates from saved graph |
| Sub-agent context explosion | MEDIUM | Cap sub-agent turns hard at 3; return best-effort response; agent infrastructure refactor needed for full fix |
| Streaming connection leak | MEDIUM | Restart server process; add disconnect handling in next deploy |
| Tool overload degrading cube selection | MEDIUM | Refactor tool definitions to strictly enforce two-tier pattern; system prompt update + redeploy |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Invalid workflow graph connections | Agent infrastructure (tool design + system prompts) | Test: run Build Agent output through WorkflowExecutor validation; expect 0 invalid connections |
| Tool catalog overload | Agent infrastructure (two-tier catalog tool definition) | Check: count tool call tokens per agent turn; verify get_cube_definition is called before edge generation |
| Multi-turn context explosion | Agent infrastructure (context management) + Canvas Agent implementation | Test: simulate 20-turn conversation; verify token count stays under 50k per turn |
| Gemini returning text instead of tool call | Agent infrastructure (tool_config + descriptions) | Test: every agent turn that should call a tool does call a tool in 10/10 test runs |
| Sub-agent context explosion | Agent infrastructure (sub-agent design) | Test: Cube Expert invocation adds <500 tokens to orchestrator history |
| Blocking event loop with sync Gemini calls | Agent infrastructure (FastAPI endpoint design) | Test: concurrent workflow SSE + agent request; SSE must not freeze |
| Canvas state broken by agent edits | Canvas Agent implementation | Test: apply agent-generated workflow; verify React Flow renders all edges without errors |
| Missing client disconnect handling | Agent infrastructure (streaming endpoints) | Test: disconnect after 500ms; verify server-side Gemini call terminates within 2 seconds |

---

## Sources

- Google AI for Developers — Function Calling: https://ai.google.dev/gemini-api/docs/function-calling
- Context Engineering for AI Agents (2025): https://promptbuilder.cc/blog/context-engineering-agents-guide-2025
- The Multi-Agent Trap (Towards Data Science): https://towardsdatascience.com/the-multi-agent-trap/
- Architecting efficient context-aware multi-agent framework (Google Developers Blog): https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production/
- AI Tool Overload: Why More Tools Mean Worse Performance (Jenova.ai): https://www.jenova.ai/en/resources/mcp-tool-scalability-problem
- Why LLM agents break when you give them tools (DEV Community): https://dev.to/terzioglub/why-llm-agents-break-when-you-give-them-tools-and-what-to-do-about-it-f5
- Streaming AI Agent with FastAPI (DEV Community, 2025-26 Guide): https://dev.to/kasi_viswanath/streaming-ai-agent-with-fastapi-langgraph-2025-26-guide-1nkn
- Async Streaming Responses in FastAPI (dasroot.net, 2026): https://dasroot.net/posts/2026/03/async-streaming-responses-fastapi-comprehensive-guide/
- Context Window: What It Is and Why It Matters (Comet.ml): https://www.comet.com/site/blog/context-window/
- Gemini API Troubleshooting Guide: https://ai.google.dev/gemini-api/docs/troubleshooting
- Project 12 internal context: .planning/PROJECT.md, .planning/STATE.md

---
*Pitfalls research for: AI agents added to visual dataflow workflow builder (12-flow v3.0)*
*Researched: 2026-03-22*
