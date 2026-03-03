# Phase 3: Async Execution with SSE Progress - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Refactor workflow execution to stream per-cube status events in real-time via SSE. The frontend (Phase 5) will consume these events to show live progress — this phase delivers the backend streaming infrastructure only.

Single requirement: BACK-13.

</domain>

<decisions>
## Implementation Decisions

### Event payload shape
- SSE events include cube outputs inline — user wants to see data as it arrives
- "pending" events fire upfront for all nodes so frontend knows the full execution plan
- "running" event when a cube starts executing
- "done" event includes full outputs (row-limited per Phase 2's 100-row cap)
- "error" event includes error message

### Sync endpoint fate
- Keep existing `POST /api/workflows/{id}/run` as-is — fallback for simple cases
- New `GET /api/workflows/{id}/run/stream` is the SSE endpoint
- Both coexist; sync endpoint is not deprecated

### Connection lifecycle & cancellation
- Explicit cancellation support needed — primarily for killing long-running DB queries
- If user navigates away without cancelling: execution continues in background IF simple to implement; otherwise abort on disconnect
- Pragmatic approach: don't over-engineer background continuation if it adds significant complexity
- Cancellation should actually interrupt DB queries, not just stop sending events

### Final event shape
- No summary event — just individual per-cube status events (pending, running, done, error)
- Each cube's "done" event carries its outputs, which is sufficient for now

### Claude's Discretion
- CubeStatusEvent schema field names and structure
- SSE event naming convention (event type field vs data-only)
- How cancellation propagates to async DB operations internally
- Whether to use asyncio.TaskGroup or manual task management

</decisions>

<specifics>
## Specific Ideas

- "In the end game we will give the user the option to create dashboards with panels from the cubes outputs" — future capability, not this phase
- Cancellation matters most for the DB query parts (long-running SQL against Tracer 42 RDS)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `execute_graph()` in `engine/executor.py`: topological sort, input resolution, failure isolation — refactor to async generator
- `topological_sort()`, `resolve_inputs()`, `apply_row_limit()` — pure functions, reuse as-is
- `sse-starlette` already in `pyproject.toml` dependencies

### Established Patterns
- `execute_graph()` returns `dict[str, dict[str, Any]]` keyed by node_id with `status`, `outputs`, `truncated` — SSE events should mirror this shape
- Failure isolation: downstream cubes marked "skipped" when upstream fails — SSE events should emit "skipped" status too
- Cubes use `engine.connect()` directly for DB access (AllFlights pattern) — cancellation needs to reach this level

### Integration Points
- `POST /api/workflows/{id}/run` in `routers/workflows.py` — stays as-is
- New SSE endpoint added to same router
- `schemas/execution.py` — new file for CubeStatusEvent model
- Frontend (Phase 5) will consume SSE via `useWorkflowSSE.ts` hook

</code_context>

<deferred>
## Deferred Ideas

- Dashboard with panels from cube outputs — user's "end game" vision, future phase
- Execution history / run logs — not discussed, potential future capability

</deferred>

---

*Phase: 03-async-execution-with-sse-progress*
*Context gathered: 2026-03-03*
