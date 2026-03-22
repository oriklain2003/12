# Stack Research — AI Workflow Agents (v3.0 Milestone)

**Domain:** AI agent system added to existing visual dataflow builder
**Researched:** 2026-03-22
**Confidence:** HIGH

> Scope: NEW additions only. Existing stack (FastAPI, SQLAlchemy, SSE, React 18, @xyflow/react, Zustand 5, Leaflet) is validated and unchanged.

---

## New Stack Additions

### Backend — AI Layer

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| google-genai | `>=1.68.0` | Gemini LLM client | Official Google SDK, GA since May 2025. Replaces deprecated `google-generativeai`. Already used in tracer-api with `genai.Client`. Supports async via `.aio`, chat sessions, tool/function calling. |
| google-genai | — | Function calling (tools) | Built-in tool declarations, automatic Python function invocation, multi-turn conversation history via `client.chats.create()`. Manual turn management also available for full control. |

**No new backend framework additions needed.** SSE via sse-starlette already works and is the right transport for streaming LLM tokens to the frontend. The agent router is just another FastAPI router.

### Frontend — Chat and Wizard UI

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| No new library | — | Chat panel component | Build with React state + fetch streaming. EventSource/fetch + ReadableStream is native, no library needed. The project already handles SSE from the backend (workflow execution); same pattern applies here. |
| No new library | — | Wizard page component | Build with React useState (step index). The wizard is 3-5 steps of clickable cards — a `<WizardPage>` component with Zustand or local state is 80 lines. No library adds more than it costs. |

---

## Integration Points

### Backend Agent Infrastructure

```
backend/app/
  agents/
    base_agent.py          # BaseAgent: system prompt loading, chat session, tool dispatch
    canvas_agent.py        # 3 modes: optimize, error-fix, general
    build_agent.py         # Wizard conversation manager
    cube_expert.py         # Sub-agent: two-tier catalog lookup
    validation_agent.py    # Pre-execution structural checks
    results_agent.py       # Post-execution interpreter
    tools/
      workflow_tools.py    # create_workflow, update_workflow, validate_graph
      catalog_tools.py     # browse_cube_summaries, get_cube_definition
  routers/
    agent_routes.py        # POST /api/agents/{agent_type}/chat (SSE stream)
  skills/                  # System prompts as .md files loaded at startup
    system_brief.md
    canvas_agent.md
    build_agent.md
    cube_expert.md
```

### Frontend Agent Components

```
frontend/src/
  components/
    AgentChat/
      AgentChatPanel.tsx   # Slide-in panel on editor page
      ChatMessage.tsx      # Single message (user/assistant/tool-call)
      ChatInput.tsx        # Textarea + mode selector (optimize/error-fix/general)
  pages/
    BuildWizard/
      BuildWizardPage.tsx  # Full-page wizard
      WizardStep.tsx       # Reusable step with clickable option cards
  hooks/
    useAgentStream.ts      # fetch + ReadableStream → token accumulation
  store/
    agentStore.ts          # Zustand slice: conversation history, active mode, loading state
```

---

## Recommended Stack Additions — Install Commands

```bash
# Backend (uv)
uv add "google-genai>=1.68.0"
```

```bash
# Frontend — no new packages needed
```

---

## Gemini SDK — Critical Patterns

### Async streaming (use this pattern for SSE routes)

```python
# client.aio for async context (FastAPI async route)
async def stream_agent_response(prompt: str, history: list):
    async for chunk in await client.aio.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=history + [{"role": "user", "parts": [{"text": prompt}]}],
        config=types.GenerateContentConfig(system_instruction=system_prompt)
    ):
        if chunk.text:
            yield chunk.text
```

### Function calling — manual (use for sub-agent tools)

Streaming + automatic function calling is NOT reliable. Use manual tool dispatch:
1. Send turn to model with tool declarations
2. Check response for `function_call` parts
3. Execute the tool
4. Append `function_response` to history and send again
5. Stream the final text response

This is the only production-safe pattern when tools are involved.

### Chat history — manual management (required for SSE streaming)

`client.chats.create()` maintains state server-side, which creates per-connection coupling that breaks across SSE reconnects and stateless deployments. Manage history explicitly as a list of `types.Content` passed on each call. Store history in the request body (for short conversations) or in Redis/PostgreSQL (for persistent sessions).

For 12-flow's use case: pass history in the POST request body. No session state on the server. Simple, stateless, SSE-compatible.

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| google-genai direct | LangChain | +1MB dep, adds abstraction over the SDK already used in tracer-api. Overhead not justified for 5 agents. |
| google-genai direct | LlamaIndex | Same: heavy framework for a task the SDK handles natively. |
| Manual history management | `client.chats.create()` session | Server-side state breaks SSE reconnects and doesn't survive process restarts. |
| SSE (existing pattern) | WebSocket | Already proven for workflow execution. WebSocket adds ws:// protocol complexity for no gain on one-way streams. |
| Custom React chat component | Vercel AI SDK `useChat` | Ties frontend to a Vercel-specific protocol. The project streams SSE natively. |
| Custom React chat component | `react-chatbotify` / `stream-chat` | Heavy UI opinions incompatible with the project's dark tactical ONYX theme. |
| Custom wizard (useState) | `react-use-wizard` | The wizard is 3-5 steps with clickable cards — a 50-line component. Adding a dependency for this is unjustified. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `google-generativeai` (old SDK) | Deprecated. Google deprecated it when `google-genai` GA'd in May 2025. | `google-genai>=1.68.0` |
| `google-genai<1.67.0` | Version 1.67.0 has a `typing-extensions` lower-bound bug; 1.66.0 is safe but outdated. | `>=1.68.0` which fixes the bug |
| LangChain / LlamaIndex agent frameworks | Adds 100k+ LOC of abstraction over a direct SDK call. The agents here have simple, well-defined tools — no agent orchestration framework is needed. | `google-genai` SDK directly |
| Server-side chat sessions (`client.chats.create()`) | Creates stateful coupling that breaks SSE reconnects, parallel requests, and horizontal scaling. | Pass `history: list[Content]` in request body |
| `EventSource` (browser API) for agent streaming | EventSource only supports GET requests with no body. Agent requests need POST (to send workflow graph, history). | `fetch` + `ReadableStream` in `useAgentStream.ts` hook |
| Streaming `generate_content_stream` with automatic function calling | Behavior is undefined/unreliable as of SDK 1.x for streaming + tools combined. | Non-streaming tool-call turn, then stream the final response separately |

---

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| google-genai | `>=1.68.0` | Python `>=3.11` | Avoid 1.67.0 (typing-extensions bug). Project is on 3.11+. |
| google-genai | `>=1.68.0` | FastAPI `>=0.115.0` | Uses `client.aio` (asyncio-native). No conflicts. |
| google-genai | `>=1.68.0` | sse-starlette `>=2.0.0` | SDK streaming yields async chunks that feed directly into `EventSourceResponse` generator. |

---

## Model Recommendation

Use **`gemini-2.5-flash`** (not `gemini-3-flash-preview` used in tracer-api):
- `gemini-2.5-flash` is GA, production-stable, fast, cost-effective
- `gemini-3-flash-preview` is a preview model — unsuitable for a feature users interact with in real-time
- `gemini-2.5-pro` is available for the Build Agent where reasoning depth matters more than latency

Verify available model IDs via `client.models.list()` against the configured API key before coding.

---

## Sources

- [googleapis/python-genai releases](https://github.com/googleapis/python-genai/releases) — v1.68.0 confirmed current stable (March 18, 2026) — HIGH confidence
- [Google Gen AI SDK docs](https://googleapis.github.io/python-genai/) — chat sessions, async streaming, function calling patterns — HIGH confidence
- [Gemini API function calling guide](https://ai.google.dev/gemini-api/docs/function-calling) — tool declarations, multi-turn pattern, model support matrix — HIGH confidence
- tracer-api/ai_classify.py — existing `genai.Client` usage pattern in this codebase — HIGH confidence (direct observation)
- tracer-api/pyproject.toml — existing constraint `google-genai>=0.2.0,<1.0.0` (outdated, needs upgrade) — HIGH confidence
- [FastAPI SSE LLM streaming patterns](https://medium.com/@2nick2patel2/fastapi-server-sent-events-for-llm-streaming-smooth-tokens-low-latency-1b211c94cff5) — streaming agent pattern with SSE — MEDIUM confidence

---

*Stack research for: AI Workflow Agents (v3.0 milestone), Project 12-flow*
*Researched: 2026-03-22*
