# Phase 18: Agent Infrastructure - Research

**Researched:** 2026-03-24
**Domain:** Gemini LLM integration, FastAPI SSE streaming, tool dispatch, server-side session management
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Skill File Design**
- D-01: One markdown file per agent persona in `backend/app/agents/skills/` — e.g., `canvas_agent.md`, `build_agent.md`, `cube_expert.md`, `validation_agent.md`, `results_interpreter.md`
- D-02: System brief is a separate hand-written `system_brief.md` file describing Tracer 42 domain context (database schema, cube ecosystem, analyst workflow). Injected at the top of every agent prompt. Updated manually when cubes change.
- D-03: Skill files loaded once at FastAPI lifespan startup and cached in memory. Requires server restart to pick up prompt changes (acceptable; uvicorn --reload handles dev).

**Tool Dispatch API**
- D-04: Decorator-based tool registration — `@agent_tool(name='...', description='...')` on plain async functions. A registry collects them at import time, similar to FastAPI route discovery.
- D-05: Tool input schemas defined as Pydantic models. Auto-converted to Gemini's JSON schema format. Validates input before execution.
- D-06: On tool failure: retry once for transient errors, then return the error message to the LLM as the tool result so Gemini can reason about it.
- D-07: Tool functions receive an injected `ToolContext` dataclass containing `db_session`, `cube_registry`, `workflow_id`, etc. Passed by the dispatcher, not imported globally.

**Context & History Management**
- D-08: Server-side sessions stored in an in-memory dict keyed by session_id. Frontend sends session_id + new message each turn (NOT full message array). This departs from the research assumption of client-carried history.
- D-09: 30-minute TTL on sessions with periodic background cleanup to prevent memory leaks from abandoned conversations.
- D-10: Token counting uses approximate char-based estimation (~4 chars per token). Good enough for the 50k threshold.
- D-11: History pruning: drop oldest user/assistant turn pairs first, always keep system prompt + recent turns. Tool results from old turns are the first to go (biggest token consumers).

**SSE Streaming**
- D-12: Real-time streaming of agent thinking and tool execution to the client. The SSE stream uses typed events: `text` (streaming tokens), `tool_call` (tool name + args being invoked), `tool_result` (output from tool), `thinking` (model reasoning if available), `done` (turn complete). Frontend renders each event type differently.
- D-13: SSE disconnect detection: check `await request.is_disconnected()` before each yield.

**Config & API Key**
- D-14: `GEMINI_API_KEY` added to the existing `Settings` class in `config.py`, loaded from `.env` alongside `DATABASE_URL`.
- D-15: Model names configurable via Settings with defaults: `gemini_flash_model='gemini-2.5-flash'`, `gemini_pro_model='gemini-2.5-pro'`.
- D-16: Simple retry with exponential backoff (up to 2 retries) on transient Gemini errors (429, 503). No client-side rate limiting.

### Claude's Discretion
- Tool dispatch implementation details (decorator internals, registry data structures)
- Pydantic-to-Gemini schema conversion approach
- Session cleanup background task implementation
- SSE event serialization format (JSON structure within each event type)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Gemini client integration (`google-genai>=1.68.0`) with async execution via `client.aio` | SDK confirmed at 1.68.0 (released Mar 18 2026); async pattern via `client.aio.models.generate_content_stream()` |
| INFRA-02 | SSE streaming endpoint for agent chat responses | `sse_starlette` already installed; typed-event SSE pattern follows existing `stream_graph` pattern |
| INFRA-03 | Skill files (system prompts) for each agent persona | Load at lifespan startup, cache in module-level dict; one `.md` file per agent in `backend/app/agents/skills/` |
| INFRA-04 | System brief document with Tracer 42 domain context for all agents | Separate `system_brief.md` prepended to every agent prompt; loaded same way as persona files |
| INFRA-05 | Agent tool dispatch system (internal function calls, not HTTP) | Decorator registry pattern confirmed; manual dispatch loop: generate → detect tool_call → execute → inject result → re-generate |
| INFRA-06 | Context management (server-side history, pruning to avoid context explosion) | Server-side in-memory dict; char-based token estimation; drop oldest pairs first |
| INFRA-07 | Mission context persistence in workflow metadata (JSONB) | Workflow ORM model already has `graph_json` JSONB; add `metadata` JSONB column or embed in `graph_json.metadata` |
</phase_requirements>

---

## Summary

Phase 18 builds the Gemini LLM infrastructure layer that all downstream agent phases (19-22) consume. The core challenge is integrating `google-genai` 1.68.0 into a FastAPI async application cleanly — specifically: never blocking the event loop with synchronous Gemini calls, streaming tool execution events alongside text tokens, and managing server-side conversation history without memory leaks.

The existing codebase provides strong patterns to follow. `sse_starlette.EventSourceResponse` is already a dependency and used for workflow execution streaming. `CubeRegistry` provides the decorator/auto-discovery model for the tool registry. `Settings` (pydantic-settings) is the established pattern for API keys and model config. The lifespan hook is where skill files load and background cleanup tasks start.

The most critical technical choice is the **manual tool dispatch pattern** — Gemini is called with `automatic_function_calling={'disable': True}`, the application detects `response.function_calls`, executes locally, feeds results back, then calls Gemini again for text output. This means the SSE stream for a single turn involves: stream tokens → pause at tool_call → yield `tool_call` event → execute → yield `tool_result` event → stream tokens again. The architecture mirrors what exists for cube execution streaming but adds an inner function-call resolution loop.

**Primary recommendation:** Build `backend/app/agents/` as a self-contained package that imports from existing `app.engine`, `app.schemas`, and `app.config` — but is never imported by those packages. Follow the `CubeRegistry` pattern for tool registration, the `stream_graph` pattern for SSE, and the `Settings` pattern for config.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `google-genai` | `>=1.68.0` | Gemini API client (async streaming, function calling) | New unified SDK; v1.67.0 has typing-extensions bug; `google-generativeai` is deprecated |
| `sse-starlette` | `>=2.0.0` (already installed) | SSE streaming from FastAPI | Already a project dependency; established pattern in `routers/workflows.py` |
| `pydantic-settings` | `>=2.0.0` (already installed) | Config for `GEMINI_API_KEY`, model names | Consistent with existing `Settings` class |
| `pydantic` | `>=2.0.0` (already installed) | Tool input schema definition and validation | Project standard; auto-conversion to Gemini JSON schema |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asyncio` (stdlib) | N/A | Background cleanup task for session TTL | `asyncio.create_task()` in lifespan for periodic cleanup loop |
| `dataclasses` (stdlib) | N/A | `ToolContext` dataclass for injecting db_session, cube_registry | Lightweight injection container, no new dependencies |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual tool dispatch | Automatic function calling (AFC) | AFC is simpler but doesn't allow streaming tool events to the client or custom error handling; manual dispatch is required for the SSE tool_call/tool_result event stream |
| In-memory session dict | Redis / database sessions | In-memory is simpler, avoids new dependencies; acceptable since workflow is the durable artifact and agents are stateless between workflows |
| Char-based token estimation | `tiktoken` or Gemini's `count_tokens` API | `count_tokens` requires an API call per turn (latency + cost); char estimation (~4 chars/token) is sufficient for a 50k threshold guard |

**Installation (new dependency only):**
```bash
cd backend
uv add "google-genai>=1.68.0"
```

**Version verification (confirmed 2026-03-24):**
```bash
# Confirmed: 1.68.0 released Mar 18 2026
# pip index: https://pypi.org/project/google-genai/
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/app/agents/
├── __init__.py           # Package marker
├── client.py             # Gemini client singleton (initialized in lifespan)
├── registry.py           # Tool registry (decorator + collection, mirrors engine/registry.py)
├── dispatcher.py         # Tool dispatch loop: detect call → execute → inject result
├── sessions.py           # Server-side session store (in-memory dict + TTL cleanup)
├── context.py            # ToolContext dataclass, history pruning logic
├── router.py             # FastAPI router: POST /api/agent/chat (SSE)
├── skills/
│   ├── system_brief.md       # Tracer 42 domain context, injected first in every prompt
│   ├── canvas_agent.md       # Canvas Agent persona
│   ├── build_agent.md        # Build Wizard Agent persona
│   ├── cube_expert.md        # Cube Expert persona
│   ├── validation_agent.md   # Validation Agent persona
│   └── results_interpreter.md
└── tools/
    ├── __init__.py
    └── catalog_tools.py      # list_cubes_summary, get_cube_detail (Phase 19 populates)
```

### Pattern 1: Gemini Client Initialization (Lifespan)

**What:** Singleton `genai.Client` initialized once at startup, stored in app state or module-level variable. Async cleanup via `await client.aclose()` on shutdown.

**When to use:** All agent endpoints share one client instance.

```python
# backend/app/agents/client.py
# Source: https://googleapis.github.io/python-genai/
from google import genai
from app.config import settings

_client: genai.Client | None = None

def get_gemini_client() -> genai.Client:
    if _client is None:
        raise RuntimeError("Gemini client not initialized — call init_client() in lifespan")
    return _client

async def init_client() -> None:
    global _client
    _client = genai.Client(api_key=settings.gemini_api_key)

async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aio.aclose()
        _client = None
```

```python
# backend/app/main.py lifespan addition
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing DB warmup ...

    # Agent infrastructure
    from app.agents.client import init_client, close_client
    from app.agents.sessions import start_cleanup_task, stop_cleanup_task
    from app.agents.skills_loader import load_skill_files
    load_skill_files()
    await init_client()
    cleanup_task = asyncio.create_task(start_cleanup_task())

    yield

    cleanup_task.cancel()
    await close_client()
```

### Pattern 2: Async Streaming with Tool Dispatch Loop

**What:** The agent SSE endpoint alternates between streaming text tokens and pausing to execute tool calls. AFC is disabled; tool calls are detected manually.

**When to use:** `POST /api/agent/chat` — single agent turn.

```python
# Source: https://ai.google.dev/gemini-api/docs/function-calling
# Source: https://googleapis.github.io/python-genai/

from google import genai
from google.genai import types

async def agent_turn_stream(
    client: genai.Client,
    history: list[types.Content],
    new_message: str,
    tools: list[types.Tool],
    config: types.GenerateContentConfig,
    tool_context: ToolContext,
) -> AsyncGenerator[AgentSSEEvent, None]:
    """One agent turn: stream text, handle tool calls, resume streaming."""

    contents = history + [
        types.Content(role="user", parts=[types.Part(text=new_message)])
    ]

    # Outer loop: keep going until Gemini returns text (no more tool calls)
    while True:
        # Call Gemini with streaming; AFC disabled so we detect calls manually
        tool_call_detected = False
        accumulated_parts = []

        async for chunk in await client.aio.models.generate_content_stream(
            model=config.model,
            contents=contents,
            config=config,
        ):
            # Stream text tokens to client
            if chunk.text:
                yield AgentSSEEvent(type="text", data=chunk.text)

            # Detect tool call in chunk
            if chunk.function_calls:
                tool_call_detected = True
                for fc in chunk.function_calls:
                    yield AgentSSEEvent(type="tool_call", data={
                        "name": fc.name, "args": dict(fc.args)
                    })
                    result = await dispatch_tool(fc, tool_context)
                    yield AgentSSEEvent(type="tool_result", data={
                        "name": fc.name, "result": result
                    })
                    # Append tool result to contents for next Gemini call
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(
                            name=fc.name,
                            response=result,
                            id=fc.id,
                        )]
                    ))
                break  # End chunk iteration; restart Gemini call with tool results

        if not tool_call_detected:
            break  # No tool call → final text response complete

    yield AgentSSEEvent(type="done", data={})
```

### Pattern 3: Tool Registry (Decorator-Based)

**What:** `@agent_tool` decorator registers async functions into a global registry at import time. Mirrors `CubeRegistry` auto-discovery approach.

```python
# backend/app/agents/registry.py
from dataclasses import dataclass, field
from typing import Callable, Any
from google.genai import types
import functools

@dataclass
class RegisteredTool:
    name: str
    description: str
    fn: Callable
    gemini_declaration: types.FunctionDeclaration

_tools: dict[str, RegisteredTool] = {}

def agent_tool(name: str, description: str, parameters_schema: dict):
    """Decorator: register an async function as an agent tool."""
    def decorator(fn: Callable) -> Callable:
        decl = types.FunctionDeclaration(
            name=name,
            description=description,
            parameters_json_schema=parameters_schema,
        )
        _tools[name] = RegisteredTool(
            name=name, description=description, fn=fn,
            gemini_declaration=decl,
        )
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await fn(*args, **kwargs)
        return wrapper
    return decorator

def get_all_tool_declarations() -> list[types.FunctionDeclaration]:
    return [t.gemini_declaration for t in _tools.values()]

def get_tool(name: str) -> RegisteredTool | None:
    return _tools.get(name)
```

### Pattern 4: Server-Side Session Management

**What:** In-memory dict keyed by `session_id` (UUID string), each entry holds `history: list[types.Content]` and `last_accessed: float`. Background asyncio task sweeps stale entries every 5 minutes.

```python
# backend/app/agents/sessions.py
import asyncio
import time
from google.genai import types

_sessions: dict[str, dict] = {}
SESSION_TTL_SECONDS = 30 * 60  # 30 minutes

def get_or_create_session(session_id: str) -> list[types.Content]:
    if session_id not in _sessions:
        _sessions[session_id] = {"history": [], "last_accessed": time.time()}
    _sessions[session_id]["last_accessed"] = time.time()
    return _sessions[session_id]["history"]

def update_session(session_id: str, history: list[types.Content]) -> None:
    _sessions[session_id]["history"] = history
    _sessions[session_id]["last_accessed"] = time.time()

async def start_cleanup_task() -> None:
    """Periodic background task: remove sessions idle > TTL."""
    while True:
        try:
            await asyncio.sleep(300)  # check every 5 minutes
            now = time.time()
            expired = [
                sid for sid, s in _sessions.items()
                if now - s["last_accessed"] > SESSION_TTL_SECONDS
            ]
            for sid in expired:
                del _sessions[sid]
        except asyncio.CancelledError:
            break  # Clean shutdown
```

### Pattern 5: History Pruning

**What:** Approximate token count (~4 chars/token). When history exceeds 50k tokens, drop oldest user/assistant turn pairs. Tool result content parts from old turns are dropped first (largest token consumers).

```python
# backend/app/agents/context.py

PRUNE_THRESHOLD_CHARS = 50_000 * 4  # ~50k tokens

def estimate_chars(history: list) -> int:
    total = 0
    for content in history:
        for part in content.parts:
            if hasattr(part, "text") and part.text:
                total += len(part.text)
    return total

def prune_history(history: list, system_prompt_turns: int = 1) -> list:
    """Drop oldest non-system turn pairs until under threshold."""
    while estimate_chars(history) > PRUNE_THRESHOLD_CHARS:
        # Keep system prompt (first N turns) + always at least 2 recent turns
        safe_prefix = system_prompt_turns
        if len(history) <= safe_prefix + 2:
            break  # Cannot prune further
        history.pop(safe_prefix)  # Remove oldest non-system turn
    return history
```

### Pattern 6: Skill File Loading

**What:** Load all `.md` files from `backend/app/agents/skills/` at lifespan startup, cache in a module-level dict.

```python
# backend/app/agents/skills_loader.py
from pathlib import Path

_skills: dict[str, str] = {}
SKILLS_DIR = Path(__file__).parent / "skills"

def load_skill_files() -> None:
    """Load all skill markdown files into memory at startup."""
    for md_file in SKILLS_DIR.glob("*.md"):
        _skills[md_file.stem] = md_file.read_text(encoding="utf-8")

def get_skill(name: str) -> str:
    """Return skill content or empty string if not found."""
    return _skills.get(name, "")

def get_system_prompt(persona: str) -> str:
    """Combine system_brief + persona skill into one system prompt."""
    brief = _skills.get("system_brief", "")
    persona_text = _skills.get(persona, "")
    return f"{brief}\n\n{persona_text}".strip()
```

### Pattern 7: Mission Context Persistence

**What:** Store mission context (analysis intent, parameters) in the Workflow ORM model's `graph_json` under a `metadata` key (no schema migration required — JSONB is flexible).

```python
# Storing mission context on workflow update
workflow.graph_json = {
    **workflow.graph_json,
    "metadata": {
        "mission": {
            "intent": "analyze dark flights over EU",
            "parameters": {...},
            "created_by": "build_agent",
            "created_at": "2026-03-24T10:00:00Z",
        }
    }
}
```

### Pattern 8: Config Extension

**What:** Add three new fields to the existing `Settings` class. Follows established convention exactly.

```python
# backend/app/config.py additions
class Settings(BaseSettings):
    # ... existing fields ...
    gemini_api_key: str = ""
    gemini_flash_model: str = "gemini-2.5-flash"
    gemini_pro_model: str = "gemini-2.5-pro"
    agent_session_ttl_minutes: int = 30
```

### Pattern 9: SSE Router (Agent Chat Endpoint)

**What:** `POST /api/agent/chat` returns `EventSourceResponse`. Follows `workflows.py` pattern exactly.

```python
# backend/app/agents/router.py
from fastapi import APIRouter, Depends
from sse_starlette import EventSourceResponse, ServerSentEvent
from starlette.requests import Request
import json

router = APIRouter(prefix="/api/agent", tags=["agent"])

@router.post("/chat")
async def agent_chat(
    body: AgentChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    async def event_publisher():
        async for event in agent_turn_stream(...):
            if await request.is_disconnected():
                break
            yield ServerSentEvent(
                data=json.dumps(event.model_dump()),
                event=event.type,
            )

    return EventSourceResponse(
        event_publisher(),
        ping=15,
        headers={"X-Accel-Buffering": "no"},
    )
```

### Anti-Patterns to Avoid

- **`google-generativeai` import:** This package is deprecated and must not be used. Always `from google import genai` (the new `google-genai` package).
- **Synchronous Gemini calls in async handlers:** `client.models.generate_content()` (sync) blocks the event loop. Always use `client.aio.models.generate_content_stream()` or `client.aio.models.generate_content()`.
- **Automatic function calling (AFC):** AFC is the SDK default (`disable=False`). It executes tools silently without yielding SSE events. Must be explicitly disabled: `automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)`.
- **Passing full cube execution results to agents:** Never pass raw cube result rows to agents. Summarize to `{cube_id, result_count, sample: row[0:3], columns: [...]}` to prevent context explosion.
- **Sub-agents receiving orchestrator history:** Cube Expert and Validation Agent receive task description only — not the full orchestrator conversation history.
- **`run_in_executor` for Gemini:** REQUIREMENTS.md says `run_in_executor` but the CONTEXT.md and STATE.md clarify `client.aio` is the correct approach — `client.aio` provides native async, not thread-pool wrapping. Use `client.aio` exclusively.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema generation from Pydantic | Custom schema serializer | `model.model_json_schema()` + manual strip of `$defs` | Pydantic already generates JSON Schema; Gemini needs `$defs` removed and nested refs inlined |
| SSE event transport | Custom HTTP chunked response | `sse_starlette.EventSourceResponse` + `ServerSentEvent` | Already installed; handles keep-alive pings, disconnect, correct headers |
| Periodic cleanup loops | Custom timer/threading | `asyncio.create_task()` + `asyncio.sleep()` in lifespan | Standard asyncio pattern; integrates cleanly with FastAPI lifespan cancellation |
| Retry logic on Gemini 429/503 | Complex circuit breaker | Simple `for attempt in range(3): try/except with await asyncio.sleep(2**attempt)` | 2 retries is sufficient; no external library needed |
| HTTP calls from tools | `httpx` requests to `/api/cubes/catalog` | Import `registry.catalog()` directly | Tools run in-process; HTTP would add latency, serialization overhead, and circular dependency |

**Key insight:** Tools call Python functions directly — never HTTP. This is the critical architectural boundary. The agent layer imports from `app.engine.registry` and `app.schemas`; the inverse is never true.

---

## Common Pitfalls

### Pitfall 1: Blocking Event Loop with Gemini Calls
**What goes wrong:** Calling `client.models.generate_content()` (sync version) inside an async handler blocks the entire event loop, freezing all concurrent workflow SSE streams.
**Why it happens:** `google-genai` exposes both sync (`client.models`) and async (`client.aio.models`) interfaces. The sync interface looks natural in Python but is fatal in an async context.
**How to avoid:** Always use `client.aio.models.generate_content_stream()`. Add a linter rule or code review check for any import of the non-`aio` path inside async functions.
**Warning signs:** All SSE endpoints (workflow execution) appear frozen while agent endpoint is processing.

### Pitfall 2: Automatic Function Calling Fires Silently
**What goes wrong:** AFC (enabled by default in `google-genai`) executes tool functions automatically without yielding SSE events to the client. Users see no progress indicators during long tool calls.
**Why it happens:** SDK default is `automatic_function_calling=True`. Developers often don't realize AFC is on.
**How to avoid:** Always pass `automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)` in `GenerateContentConfig`. Test with a tool that logs its invocations.
**Warning signs:** Tool SSE events (`tool_call`, `tool_result`) never appear in the stream even though tools are registered.

### Pitfall 3: `$defs` in Pydantic Schema Rejected by Gemini
**What goes wrong:** Pydantic's `model.model_json_schema()` on models with nested models generates `$defs` and `$ref` entries. Gemini's function calling API rejects schemas with `$defs`.
**Why it happens:** JSON Schema draft-2019-09 uses `$defs` for shared definitions. Gemini supports a subset of OpenAPI v3.0.3 that doesn't support `$defs`.
**How to avoid:** After calling `model.model_json_schema()`, inline all `$ref` references and remove the `$defs` key before constructing `FunctionDeclaration`. For tool schemas in this phase, keep them simple (no nested Pydantic models) to avoid the issue entirely.
**Warning signs:** Gemini API returns 400 with "invalid schema" or "unsupported field: $defs".

### Pitfall 4: Session Memory Leak from Abandoned Conversations
**What goes wrong:** Frontend opens sessions and closes the browser tab without a clean disconnect. Sessions accumulate indefinitely in the in-memory dict.
**Why it happens:** SSE is fire-and-forget from the client perspective. No "close session" signal is sent.
**How to avoid:** Implement the background cleanup task in lifespan (D-09). Ensure cleanup task is cancelled on shutdown to avoid `CancelledError` propagation.
**Warning signs:** Server memory grows monotonically over time in production.

### Pitfall 5: Tool Function ID Mismatch
**What goes wrong:** Gemini 2.5 always returns a unique `id` with each `functionCall`. If `FunctionResponse` is sent back without the matching `id`, the API may return an error or misattribute results.
**Why it happens:** Developers copying older examples (pre-2.5) that didn't require `id`.
**How to avoid:** Always capture `fc.id` from the function call and pass it to `types.Part.from_function_response(name=..., response=..., id=fc.id)`.
**Warning signs:** Gemini API error: "function response id does not match any pending function call".

### Pitfall 6: `google-genai` Unclosed aiohttp Session Warnings
**What goes wrong:** Even with proper `await client.aio.aclose()`, the internal aiohttp session may emit "Unclosed client session" warnings in the log.
**Why it happens:** Known SDK issue (#834 on googleapis/python-genai cookbook). The `AsyncClient.__del__` creates an unawaited asyncio task during GC.
**How to avoid:** Suppress the warning in test environments. In production, this is cosmetic — the session is functionally closed. Alternatively install `google-genai[aiohttp]` for potentially better resource cleanup.
**Warning signs:** `ResourceWarning: Unclosed client session` in test output.

---

## Code Examples

Verified patterns from official sources:

### Async Streaming (text only, no tools)
```python
# Source: https://googleapis.github.io/python-genai/
from google import genai

client = genai.Client(api_key="YOUR_API_KEY")

async for chunk in await client.aio.models.generate_content_stream(
    model="gemini-2.5-flash",
    contents="Tell me about flight analysis.",
):
    print(chunk.text, end="")
```

### Manual Tool Dispatch (full loop)
```python
# Source: https://ai.google.dev/gemini-api/docs/function-calling
from google import genai
from google.genai import types

client = genai.Client(api_key="YOUR_API_KEY")

# Step 1: Configure tools with AFC disabled
config = types.GenerateContentConfig(
    tools=[types.Tool(function_declarations=[my_function_decl])],
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)

contents = [types.Content(role="user", parts=[types.Part(text="User message")])]

while True:
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=config,
    )

    if not response.function_calls:
        # Final text response
        print(response.text)
        break

    # Execute each tool call
    for fc in response.function_calls:
        result = await dispatch_tool(fc.name, fc.args)
        contents.append(response.candidates[0].content)  # Model's function call
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_function_response(
                name=fc.name,
                response=result,
                id=fc.id,  # Always include matching ID
            )]
        ))
```

### Building Multi-Turn History (contents list with roles)
```python
# Source: https://ai.google.dev/gemini-api/docs/function-calling
history = [
    types.Content(role="user", parts=[types.Part(text="Hello")]),
    types.Content(role="model", parts=[types.Part(text="Hi there!")]),
    types.Content(role="user", parts=[types.Part(text="Next message")]),
]
```

### Typed SSE Events (following existing project pattern)
```python
# Source: project pattern from backend/app/routers/workflows.py
from pydantic import BaseModel
from sse_starlette import EventSourceResponse, ServerSentEvent
import json

class AgentSSEEvent(BaseModel):
    type: str  # "text" | "tool_call" | "tool_result" | "thinking" | "done"
    data: str | dict | None = None

async def event_publisher():
    async for event in agent_turn_stream(...):
        if await request.is_disconnected():
            break
        yield ServerSentEvent(
            data=event.model_dump_json(),
            event=event.type,
        )

return EventSourceResponse(
    event_publisher(),
    ping=15,
    headers={"X-Accel-Buffering": "no"},
)
```

### Pydantic Schema to Gemini (simple, avoiding $defs)
```python
# Keep tool schemas flat (no nested models) to avoid $defs issues.
# Source: https://github.com/pydantic/pydantic-ai (schema compatibility notes)

# SAFE: flat schema
parameters_schema = {
    "type": "object",
    "properties": {
        "cube_name": {"type": "string", "description": "The cube ID to look up"},
    },
    "required": ["cube_name"],
}

# AVOID: nested Pydantic model.model_json_schema() without post-processing
# It generates $defs that Gemini rejects.
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `google-generativeai` (deprecated) | `google-genai` unified SDK | Late 2024 GA | Completely different API; `genai.Client` entry point, `client.aio` for async |
| `model.generate_content_async()` | `client.aio.models.generate_content_stream()` | Late 2024 | New async interface under `.aio` namespace |
| `model.start_chat()` | `client.chats.create()` or manual history list | Late 2024 | Chat sessions now through unified client |
| Implicit auth via env vars | Explicit `genai.Client(api_key=...)` | Late 2024 | Must pass key at client construction or via env `GEMINI_API_KEY` |

**Deprecated/outdated:**
- `google-generativeai`: Deprecated. Install `google-genai` instead. The import looks similar (`from google import genai`) but the package is different.
- `run_in_executor` for Gemini: The REQUIREMENTS.md mentions this pattern but it is superseded by `client.aio` which provides native async. `run_in_executor` wraps synchronous calls in a thread pool — correct behavior but unnecessary overhead when the native async interface exists.

---

## Open Questions

1. **Gemini 2.5 Flash thinking tokens in streaming**
   - What we know: Gemini 2.5 models may expose "thinking" tokens in streaming responses
   - What's unclear: Whether `chunk.thinking` or similar is available on `generate_content_stream` responses (vs. only on Vertex AI or specific config)
   - Recommendation: Implement `thinking` SSE event as optional — emit if `chunk.text` arrives with a thinking role marker, otherwise skip. Don't block implementation on this.

2. **`graph_json` vs separate `metadata` column for mission context**
   - What we know: `graph_json` is JSONB and allows arbitrary keys; adding a `metadata` top-level key requires no migration
   - What's unclear: Whether downstream phases will want to query/filter workflows by mission metadata (would benefit from a separate indexed column)
   - Recommendation: Embed `metadata` inside `graph_json` for Phase 18 (no migration). Create a separate `metadata` JSONB column in a future phase if query patterns emerge.

3. **Session ID generation and client contract**
   - What we know: D-08 says frontend sends `session_id + new_message`. Session created server-side if not found.
   - What's unclear: Who generates the first `session_id` — frontend or backend? If frontend, it needs a UUID generator. If backend, there's an initial handshake call.
   - Recommendation: Backend generates `session_id` on first call when none is provided (return it in response headers or first SSE event). Frontend reuses it for subsequent turns.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | Yes | 3.9.6 (system) / 3.11+ (uv) | uv manages project Python |
| uv | Package management | Yes | 0.9.26 | — |
| `google-genai` | INFRA-01 | Not installed | — (1.68.0 on PyPI) | Install: `uv add "google-genai>=1.68.0"` |
| `sse-starlette` | INFRA-02 | Yes (installed) | >=2.0.0 | — |
| `pydantic-settings` | INFRA-01 (config) | Yes (installed) | >=2.0.0 | — |
| `GEMINI_API_KEY` env var | INFRA-01 | Unknown | — | Must be added to `.env` by developer; tests use mock |
| PostgreSQL (Tracer 42 RDS) | INFRA-07 (mission persistence) | Yes (existing) | AWS RDS | — |

**Missing dependencies with no fallback:**
- `GEMINI_API_KEY` in `.env` — required for integration testing; unit tests mock the client

**Missing dependencies with fallback:**
- `google-genai` package — one `uv add` command; Wave 0 install step

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]` with `asyncio_mode = "auto"`) |
| Quick run command | `cd backend && uv run pytest tests/test_agent_*.py -x` |
| Full suite command | `cd backend && uv run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | Gemini client initializes with API key from settings | unit | `uv run pytest tests/test_agent_client.py -x` | No (Wave 0) |
| INFRA-01 | `client.aio` path used (not sync) | unit | `uv run pytest tests/test_agent_client.py::test_async_interface -x` | No (Wave 0) |
| INFRA-02 | `POST /api/agent/chat` returns `text/event-stream` | integration | `uv run pytest tests/test_agent_sse.py::test_content_type -x` | No (Wave 0) |
| INFRA-02 | SSE yields typed events: `text`, `tool_call`, `tool_result`, `done` | integration | `uv run pytest tests/test_agent_sse.py::test_event_types -x` | No (Wave 0) |
| INFRA-03 | Skill file for each agent persona loads at startup | unit | `uv run pytest tests/test_agent_skills.py::test_all_personas_loaded -x` | No (Wave 0) |
| INFRA-04 | System brief injected at top of every agent prompt | unit | `uv run pytest tests/test_agent_skills.py::test_system_brief_prepended -x` | No (Wave 0) |
| INFRA-05 | `@agent_tool` decorator registers tool in registry | unit | `uv run pytest tests/test_agent_registry.py -x` | No (Wave 0) |
| INFRA-05 | Tool dispatch executes correct function and returns result | unit | `uv run pytest tests/test_agent_dispatcher.py -x` | No (Wave 0) |
| INFRA-05 | Tool failure returns error as tool result (not exception) | unit | `uv run pytest tests/test_agent_dispatcher.py::test_tool_failure -x` | No (Wave 0) |
| INFRA-06 | History pruning triggers at ~50k token threshold | unit | `uv run pytest tests/test_agent_context.py::test_prune_threshold -x` | No (Wave 0) |
| INFRA-06 | Oldest turns dropped first; system prompt preserved | unit | `uv run pytest tests/test_agent_context.py::test_prune_order -x` | No (Wave 0) |
| INFRA-07 | Mission context stored in workflow `graph_json.metadata` | integration | `uv run pytest tests/test_agent_mission.py -x` | No (Wave 0) |

### Sampling Rate
- **Per task commit:** `cd backend && uv run pytest tests/test_agent_*.py -x`
- **Per wave merge:** `cd backend && uv run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

All agent test files need creation:
- [ ] `backend/tests/test_agent_client.py` — covers INFRA-01 (client init, async interface)
- [ ] `backend/tests/test_agent_sse.py` — covers INFRA-02 (SSE endpoint, typed events)
- [ ] `backend/tests/test_agent_skills.py` — covers INFRA-03, INFRA-04 (skill loading, system brief)
- [ ] `backend/tests/test_agent_registry.py` — covers INFRA-05 (decorator registration)
- [ ] `backend/tests/test_agent_dispatcher.py` — covers INFRA-05 (dispatch loop, failure handling)
- [ ] `backend/tests/test_agent_context.py` — covers INFRA-06 (pruning logic)
- [ ] `backend/tests/test_agent_mission.py` — covers INFRA-07 (mission persistence)

Framework already installed; conftest.py already provides `make_mock_db_conn` helper and `asyncio_mode = "auto"` is active. All new tests follow the `AsyncMock` + `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))` pattern established in `test_sse_stream.py`.

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 18 |
|-----------|-------------------|
| Python: `uv` only (no pip, poetry) | All installs via `uv add "google-genai>=1.68.0"` |
| Node.js: `pnpm` only | N/A (backend-only phase) |
| All async with `asyncpg` — Gemini calls must use `client.aio` | Confirmed critical; no sync Gemini calls |
| SSE via `sse_starlette` with `ServerSentEvent` | Agent SSE endpoint follows identical pattern to `workflows.py` |
| Router-based organization | New `backend/app/routers/agent.py` or `backend/app/agents/router.py` |
| Pydantic models for all API contracts | Tool schemas, SSE event models, request/response bodies all Pydantic |
| `backend/app/config.py` — Settings class for new config fields | `gemini_api_key`, model names, session TTL added to `Settings` |
| `backend/app/main.py` lifespan — skill loading, cleanup task, client init | Follow existing `asynccontextmanager` lifespan pattern |

---

## Sources

### Primary (HIGH confidence)
- `https://googleapis.github.io/python-genai/` — official SDK docs, async API, tool calling patterns
- `https://pypi.org/project/google-genai/` — confirmed version 1.68.0 released Mar 18 2026
- `https://ai.google.dev/gemini-api/docs/function-calling` — complete manual tool dispatch loop with code
- `https://ai.google.dev/gemini-api/docs/migrate` — migration from deprecated `google-generativeai`
- Project codebase — `routers/workflows.py`, `engine/registry.py`, `main.py`, `config.py` (existing patterns)

### Secondary (MEDIUM confidence)
- `https://deepwiki.com/googleapis/python-genai/4-function-calling-and-tool-integration` — AFC disable, mode=ANY patterns (verified against official docs)
- `https://github.com/googleapis/python-genai` — README patterns for client init and async context managers
- `https://github.com/sysid/sse-starlette` — `EventSourceResponse` usage (verified against installed version in project)

### Tertiary (LOW confidence)
- `https://github.com/googleapis/python-genai/issues/834` — unclosed aiohttp session warnings (single GitHub issue, not official doc)
- Medium articles on FastAPI SSE streaming patterns (cross-referenced against official sse-starlette README)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `google-genai` 1.68.0 confirmed on PyPI; all other dependencies already installed in project
- Architecture: HIGH — existing project patterns (registry, SSE, lifespan, settings) directly inform agent layer structure
- Tool dispatch loop: HIGH — verified against official Gemini function calling docs with full code examples
- Session management: MEDIUM — in-memory TTL pattern is standard asyncio; specific `google-genai` aiohttp cleanup issue is LOW confidence (known bug, cosmetic only)
- Pitfalls: HIGH for blocking-event-loop and AFC-disable (critical, verified); MEDIUM for `$defs` schema issue (observed in community but not official doc)

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (30 days; `google-genai` is fast-moving but version is pinned at >=1.68.0)
