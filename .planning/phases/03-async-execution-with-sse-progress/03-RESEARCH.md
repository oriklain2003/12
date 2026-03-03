# Phase 3: Async Execution with SSE Progress - Research

**Researched:** 2026-03-03
**Domain:** Server-Sent Events (SSE) with sse-starlette, async generator refactor, asyncio cancellation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- SSE events include cube outputs inline — user wants to see data as it arrives
- "pending" events fire upfront for all nodes so frontend knows the full execution plan
- "running" event when a cube starts executing
- "done" event includes full outputs (row-limited per Phase 2's 100-row cap)
- "error" event includes error message
- Keep existing `POST /api/workflows/{id}/run` as-is — fallback for simple cases
- New `GET /api/workflows/{id}/run/stream` is the SSE endpoint
- Both coexist; sync endpoint is not deprecated
- Explicit cancellation support needed — primarily for killing long-running DB queries
- If user navigates away without cancelling: abort on disconnect (no background continuation) unless trivial
- Cancellation should actually interrupt DB queries, not just stop sending events
- No summary event — just individual per-cube status events (pending, running, done, error)
- Each cube's "done" event carries its outputs

### Claude's Discretion
- CubeStatusEvent schema field names and structure
- SSE event naming convention (event type field vs data-only)
- How cancellation propagates to async DB operations internally
- Whether to use asyncio.TaskGroup or manual task management

### Deferred Ideas (OUT OF SCOPE)
- Dashboard with panels from cube outputs — user's "end game" vision, future phase
- Execution history / run logs — not discussed, potential future capability
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BACK-13 | SSE endpoint (GET /api/workflows/{id}/run/stream) streams per-cube status events (pending, running, done, error) via sse-starlette EventSourceResponse | sse-starlette 3.3.2 API confirmed; async generator refactor pattern documented; cancellation via request.is_disconnected() + CancelledError; JSONServerSentEvent for structured payloads |
</phase_requirements>

## Summary

Phase 3 converts `execute_graph()` from a bulk-return coroutine into an async generator that yields `CubeStatusEvent` objects, then wraps it with `sse-starlette`'s `EventSourceResponse` in a new `GET /api/workflows/{id}/run/stream` endpoint. The existing sync `POST .../run` endpoint stays untouched.

The `sse-starlette` library (v2.0+ already in `pyproject.toml`, current release 3.3.2) handles the SSE wire protocol. The refactor is a clean layered change: new `schemas/execution.py` Pydantic model, refactored `engine/executor.py` (the existing pure functions `topological_sort`, `resolve_inputs`, `apply_row_limit` are reused verbatim), and a new route handler in `routers/workflows.py`.

Cancellation is the primary technical risk. When a client disconnects, `sse-starlette` raises `asyncio.CancelledError` inside the generator. SQLAlchemy/asyncpg has a known issue where cancellation can leak connections unless cleanup is done inside a cancel-shielded finally block. The AllFlights cube pattern (using `engine.connect()` directly) is already inside cube `execute()` calls, so the generator needs a `try/finally` that explicitly closes any held resources. Pragmatically: because cubes manage their own connections via context managers, CancelledError propagation into `async with engine.connect()` will naturally trigger `__aexit__`, which attempts ROLLBACK + close. Connection leak risk is low for read-only queries but worth noting.

**Primary recommendation:** Refactor `execute_graph` into `stream_graph` async generator, yielding `CubeStatusEvent` dicts; wrap with `EventSourceResponse(stream_graph(graph, request), ping=15)`; check `request.is_disconnected()` between nodes.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sse-starlette | >=2.0.0 (already in pyproject; latest 3.3.2) | EventSourceResponse wrapper for FastAPI SSE | The canonical SSE library for Starlette/FastAPI; maintained, W3C-compliant |
| pydantic v2 | >=2.0.0 (already in pyproject) | CubeStatusEvent schema model | Already in use throughout the project |
| FastAPI | >=0.115.0 (already in pyproject) | Route handler, Request injection | Already the web framework |

### Supporting (for tests only)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx-sse | 0.4.3 | Consuming SSE in pytest tests via aconnect_sse / aiter_sse | Testing the stream endpoint |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sse-starlette | StreamingResponse with manual SSE formatting | sse-starlette is already in deps; manual formatting adds complexity with no benefit |
| JSONServerSentEvent | Plain dict yield with json.dumps | JSONServerSentEvent auto-serializes; simpler, less error-prone |

**Installation (tests only — httpx-sse not yet in pyproject):**
```bash
cd backend && uv add --dev httpx-sse
```

## Architecture Patterns

### Recommended Project Structure (changes only)
```
backend/app/
├── schemas/
│   ├── cube.py           # unchanged
│   ├── workflow.py       # unchanged
│   └── execution.py      # NEW: CubeStatusEvent Pydantic model
├── engine/
│   └── executor.py       # REFACTOR: add stream_graph() async generator alongside execute_graph()
└── routers/
    └── workflows.py      # ADD: GET /{workflow_id}/run/stream route
```

### Pattern 1: Async Generator with Upfront Pending Events
**What:** `stream_graph()` first emits a `pending` event for every node in topological order, then iterates again emitting `running` → `done`/`error`/`skipped` per node.
**When to use:** Always — locked decision from CONTEXT.md.
**Example:**
```python
# Source: sse-starlette official docs + project pattern
from sse_starlette import EventSourceResponse, JSONServerSentEvent
from fastapi import Request

async def stream_graph(
    graph: WorkflowGraph,
    request: Request,
) -> AsyncGenerator[JSONServerSentEvent, None]:
    try:
        order = topological_sort(graph.nodes, graph.edges)
    except ValueError as exc:
        yield JSONServerSentEvent(data={"error": str(exc)}, event="fatal")
        return

    node_map = {node.id: node for node in graph.nodes}
    results: dict[str, dict[str, Any]] = {}
    failed_or_skipped: set[str] = set()

    # Upfront: emit pending for all nodes
    for node_id in order:
        yield JSONServerSentEvent(
            data=CubeStatusEvent(node_id=node_id, status="pending").model_dump(),
            event="cube_status",
        )

    # Execute in order
    for node_id in order:
        if await request.is_disconnected():
            break

        # emit running
        yield JSONServerSentEvent(
            data=CubeStatusEvent(node_id=node_id, status="running").model_dump(),
            event="cube_status",
        )

        # ... execute, emit done/error/skipped ...
```

### Pattern 2: CubeStatusEvent Pydantic Model
**What:** A single Pydantic model covering all status variants via Optional fields.
**When to use:** Always — used as the `data` payload in every SSE event.
**Example:**
```python
# Source: Pydantic v2 docs + project schema conventions
from pydantic import BaseModel
from typing import Any, Literal

class CubeStatusEvent(BaseModel):
    node_id: str
    status: Literal["pending", "running", "done", "error", "skipped"]
    outputs: dict[str, Any] | None = None
    truncated: bool | None = None
    error: str | None = None
    reason: str | None = None  # for skipped: "upstream cube failed or was skipped"
```

### Pattern 3: SSE Route Handler
**What:** GET endpoint injecting `Request` and returning `EventSourceResponse`.
**When to use:** Always — required by sse-starlette for disconnect detection.
**Example:**
```python
# Source: sse-starlette official docs
@router.get("/{workflow_id}/run/stream")
async def stream_workflow(
    workflow_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    graph = WorkflowGraph.model_validate(wf.graph_json)

    return EventSourceResponse(
        stream_graph(graph, request),
        ping=15,
        headers={"X-Accel-Buffering": "no"},  # prevent nginx buffering
    )
```

### Pattern 4: Disconnect-safe Generator with CancelledError Handling
**What:** Wrap generator body in `try/finally` to handle `CancelledError` on disconnect.
**When to use:** Always when sse-starlette may cancel the generator.
**Example:**
```python
# Source: sse-starlette disconnect docs
async def stream_graph(graph, request):
    try:
        # ... yield events ...
        for node_id in order:
            if await request.is_disconnected():
                break
            # ... execute ...
    except asyncio.CancelledError:
        # cleanup if needed
        raise  # CRITICAL: must re-raise
    finally:
        pass  # cube connections manage themselves via context managers
```

### Anti-Patterns to Avoid
- **Buffering all results then yielding:** Defeats SSE purpose; events must yield as each cube finishes.
- **Swallowing CancelledError:** Prevents sse-starlette from completing task group cancellation; causes hangs.
- **Opening DB session outside generator:** Session shared across tasks causes issues; the workflow lookup uses the request-scoped `db` session before the generator starts, which is correct — the generator itself does not need a session (cubes manage their own connections).
- **Using `POST` for SSE endpoint:** SSE requires `GET` (browsers' EventSource API only supports GET); the locked decision correctly specifies GET.
- **Yielding two separate pending loops vs inline pending-then-execute:** Emitting all pendings upfront (loop 1), then executing (loop 2) matches the locked decision. Do not interleave pending with execution start.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE wire protocol | Custom `text/event-stream` response with manual `data:` lines | `sse-starlette EventSourceResponse` | SSE spec has edge cases (retry, keep-alive pings, proper headers, buffering); already in deps |
| Client disconnect detection | Manual ASGI `http.disconnect` listener | `request.is_disconnected()` + sse-starlette's built-in task group cancellation | sse-starlette handles the three-layer detection; `request.is_disconnected()` is sufficient for polling between nodes |
| JSON serialization of event payloads | `json.dumps(model.model_dump())` in yield | `JSONServerSentEvent(data=model.model_dump(), event="...")` | Auto-serializes, avoids manual encoding bugs |

**Key insight:** The SSE wire format is deceptively simple to look at but has important edge cases around buffering (Nginx), keep-alive (connection drops silently without pings), and proper event field ordering. sse-starlette handles all of this correctly.

## Common Pitfalls

### Pitfall 1: Connection Leak on CancelledError with asyncpg
**What goes wrong:** When `asyncio.CancelledError` propagates into `async with engine.connect()`, SQLAlchemy's `__aexit__` tries to rollback/close but the await itself may be cancelled, leaving the connection checked out of the pool permanently.
**Why it happens:** asyncio cancellation interrupts any `await` including cleanup awaits; this is a known SQLAlchemy/asyncpg issue tracked in multiple issues.
**How to avoid:** Cubes using `async with engine.connect()` already get RAII-style cleanup. For read-only queries (all cubes in this project), the risk is low because there's no transaction to roll back — but the connection may not return to pool. Acceptable pragmatic risk given read-only context; document and monitor.
**Warning signs:** Pool exhaustion after repeated cancellations; "QueuePool limit of size X overflow Y reached" errors.

### Pitfall 2: Nginx Buffering Kills Real-Time Delivery
**What goes wrong:** SSE events accumulate in Nginx's proxy buffer and are delivered in batch, not in real-time.
**Why it happens:** Nginx buffers upstream responses by default.
**How to avoid:** Set `X-Accel-Buffering: no` response header in `EventSourceResponse`. Already handled by the pattern above.
**Warning signs:** Events arrive all at once after execution completes instead of streaming.

### Pitfall 3: Yielding Before Topological Sort Error
**What goes wrong:** If cycle detection raises, you've already sent HTTP 200 (SSE headers committed) and can't send 400.
**Why it happens:** SSE starts with HTTP 200; error status codes can't be sent after headers are committed.
**How to avoid:** Run `topological_sort` BEFORE starting the generator (in the route handler) or handle it inside the generator by yielding a `fatal` error event and returning. The cleanest approach: validate the graph in the route handler before constructing `EventSourceResponse`; raise `HTTPException(400)` there if cycle detected.
**Warning signs:** Client receives 200 but then immediately gets an error event — confusing for clients that expected a non-200 for bad input.

### Pitfall 4: Missing `request` Parameter in Generator
**What goes wrong:** `request.is_disconnected()` can't be called without the `Request` object; disconnect detection doesn't work.
**Why it happens:** Forgetting to pass `request` into the generator function.
**How to avoid:** Generator signature is `stream_graph(graph: WorkflowGraph, request: Request)`. Route handler passes `request` explicitly.
**Warning signs:** No compile-time error; disconnect detection silently broken.

### Pitfall 5: pytest TestClient (sync) Can't Consume SSE
**What goes wrong:** Starlette's sync `TestClient` may buffer SSE responses; events are not iterable individually.
**Why it happens:** TestClient uses `requests` library which reads the full response body.
**How to avoid:** Use `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))` + `httpx-sse`'s `aconnect_sse` / `aiter_sse` for SSE tests.
**Warning signs:** Test hangs waiting for response to complete, or receives all events as one blob.

## Code Examples

Verified patterns from official sources:

### Yielding a JSONServerSentEvent
```python
# Source: sse-starlette GitHub README
from sse_starlette import JSONServerSentEvent

yield JSONServerSentEvent(
    data={"node_id": "node-1", "status": "done", "outputs": {"rows": [...]}},
    event="cube_status",
)
```

### Polling for Disconnect Between Nodes
```python
# Source: sse-starlette disconnect detection docs
for node_id in order:
    if await request.is_disconnected():
        break
    # ... proceed with cube execution
```

### Testing SSE with httpx-sse
```python
# Source: httpx-sse GitHub README
import pytest
import httpx
from httpx_sse import aconnect_sse

@pytest.mark.asyncio
async def test_stream_workflow(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app)
    ) as client:
        async with aconnect_sse(
            client, "GET",
            f"http://test/api/workflows/{workflow_id}/run/stream"
        ) as event_source:
            events = [sse async for sse in event_source.aiter_sse()]

    node_ids = [e.json()["node_id"] for e in events]
    statuses = [e.json()["status"] for e in events]
    assert statuses.count("pending") == len(graph.nodes)
    assert "done" in statuses or "error" in statuses
```

### Handling Cycle Validation Before SSE Starts
```python
# Source: project pattern — validate before yielding
@router.get("/{workflow_id}/run/stream")
async def stream_workflow(
    workflow_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    wf = ...  # fetch or 404
    graph = WorkflowGraph.model_validate(wf.graph_json)

    # Validate cycle BEFORE starting SSE (while we can still send 400)
    try:
        topological_sort(graph.nodes, graph.edges)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return EventSourceResponse(stream_graph(graph, request), ping=15)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| sse-starlette required pytest fixture to reset state | No fixture needed since v3.0.0 | v3.0.0 | Tests are simpler |
| Yielding raw dicts `{"data": str}` | JSONServerSentEvent for structured payloads | v2.x+ | Auto JSON serialization |
| Manual disconnect check only | Three-layer: passive ASGI + active polling + CancelledError | v2.x+ | More reliable cancellation |

**Current:** sse-starlette 3.3.2 (released 2026-02-28) — project already pins `>=2.0.0`.

## Open Questions

1. **`stream_graph` naming — new function vs in-place refactor of `execute_graph`**
   - What we know: `execute_graph` is used by `POST .../run` which must stay; they share identical logic up to the yield points
   - What's unclear: Whether to keep both functions (small code duplication) or refactor execute_graph to call stream_graph internally
   - Recommendation: Implement `stream_graph` as a new async generator; refactor `execute_graph` to call `stream_graph` and collect results. This eliminates duplication.

2. **asyncpg connection leak on cancellation severity**
   - What we know: Known issue; affects read-only operations less catastrophically; connections not returned to pool
   - What's unclear: Whether pool exhaustion is observable in practice with the workload expected
   - Recommendation: Accept the risk for now (read-only, small pool); add a comment documenting the known limitation.

3. **`skipped` status — should it be included in the upfront pending events?**
   - What we know: `pending` events fire upfront for all nodes; `skipped` only becomes known during execution
   - What's unclear: Whether frontend needs to handle `skipped` as a terminal state (yes, it is — no further events for that node)
   - Recommendation: Emit `pending` for all nodes upfront, then emit `skipped` (not `done`) when a node is skipped during execution. No separate treatment needed.

## Sources

### Primary (HIGH confidence)
- sse-starlette GitHub (sysid/sse-starlette) — EventSourceResponse API, JSONServerSentEvent, disconnect detection, CancelledError handling
- sse-starlette PyPI — version 3.3.2 confirmed (released 2026-02-28)
- httpx-sse GitHub (florimondmanca/httpx-sse) — aconnect_sse, aiter_sse, version 0.4.3
- DeepWiki sse-starlette usage guide — three-layer disconnect detection, async generator patterns
- DeepWiki sse-starlette client disconnection — CancelledError re-raise requirement, DB cleanup pattern

### Secondary (MEDIUM confidence)
- SQLAlchemy GitHub issues #8145, #6652, #12099 — asyncpg connection leak on CancelledError, confirmed known issue
- FastAPI discussions/testing docs — httpx.AsyncClient + ASGITransport for SSE testing

### Tertiary (LOW confidence)
- Medium articles on FastAPI SSE — general patterns, not authoritative

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — sse-starlette already in deps, version confirmed, API verified from official sources
- Architecture: HIGH — refactor pattern is straightforward; existing execute_graph code is the template
- Pitfalls: HIGH for SSE (nginx buffering, CancelledError re-raise); MEDIUM for asyncpg leak (known issue, read-only mitigates)
- Testing: HIGH — httpx-sse pattern confirmed from official GitHub

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (sse-starlette is stable; asyncpg cancellation behavior unlikely to change)
