# Plan: Persist Workflow Execution Results Across Page Refresh

## Context

The workflow execution system streams results via SSE and stores them only in the frontend Zustand store (in-memory). When the user refreshes the page, all execution state and results are lost. The intended behavior is that users can run a workflow, refresh the page (or even close and reopen), and still see the latest execution results.

Currently:
- Backend streams execution events via SSE but persists nothing
- Frontend stores results in Zustand memory only
- `loadWorkflow()` explicitly clears `results: {}` and `executionStatus: {}`
- No API endpoint exists to retrieve past execution results

## Approach

Store the latest execution results on the `Workflow` model itself (a new `last_run` JSONB column). The backend saves results as each cube completes during streaming. The frontend fetches them on load.

This avoids a separate `executions` table since the requirement is just "see results after refresh" — not a full execution history.

## Changes

### 1. Backend: Add `last_run` column to Workflow model

**File:** `backend/app/models/workflow.py`

Add a nullable JSONB column `last_run` with shape:
```python
last_run: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
```

The stored JSON structure:
```json
{
  "started_at": "2026-03-11T10:00:00Z",
  "finished_at": "2026-03-11T10:00:05Z",
  "status": "completed",
  "node_results": {
    "node-1": { "status": "done", "outputs": {...}, "truncated": false, "execution_ms": 123 },
    "node-2": { "status": "error", "error": "...", "outputs": {} }
  }
}
```

### 2. Backend: Create Alembic migration

**File:** `backend/alembic/versions/002_add_last_run_to_workflows.py`

Add `last_run` JSONB column (nullable) to `workflows` table.

### 3. Backend: Add execution schema for persisted results

**File:** `backend/app/schemas/execution.py`

Add a `WorkflowRunResult` schema for the `last_run` structure, and a `NodeResult` schema for per-node results.

### 4. Backend: Update executor to persist results during streaming

**File:** `backend/app/engine/executor.py`

- Add a new function `stream_graph_persisted(workflow_id, graph, request, db)` that wraps `stream_graph`:
  - Before streaming: write `last_run = { status: "running", started_at, node_results: {} }` to DB
  - After each terminal event (done/error/skipped): update `last_run.node_results[node_id]` in DB
  - After completion: set `last_run.status = "completed"` and `finished_at`
  - Yields the same SSE events as before (transparent to frontend)

To avoid excessive DB writes, batch-update after each node completes (not on pending/running events). Since execution is sequential (topological order), this means one DB write per node + 1 at start + 1 at end.

### 5. Backend: Update workflow router

**File:** `backend/app/routers/workflows.py`

- Modify `stream_workflow` (GET `/{workflow_id}/run/stream`) to use `stream_graph_persisted` so results are saved
- Add `POST /{workflow_id}/run/stream` endpoint that takes just the workflow_id, loads the graph from DB, and persists results. The frontend will call this instead of the ad-hoc endpoint when a workflow is saved. Keep the ad-hoc endpoint for unsaved workflows (no persistence).
- Add `GET /{workflow_id}/last-run` endpoint that returns the `last_run` data
- Ensure `WorkflowResponse` includes `last_run` so it comes back with `GET /{workflow_id}`

### 6. Frontend: Update the SSE hook to use workflow-specific endpoint

**File:** `frontend/src/hooks/useWorkflowSSE.ts`

- Accept optional `workflowId` parameter
- If `workflowId` is provided, POST to `/api/workflows/{workflowId}/run/stream` (persisted)
- If not, POST to `/api/workflows/run/stream` (ad-hoc, no persistence)

### 7. Frontend: Restore results on workflow load

**File:** `frontend/src/store/flowStore.ts`

- In `loadWorkflow()`: after loading the workflow, check if `last_run` exists in the response
- If `last_run` exists and has `node_results`, populate `executionStatus` and `results` from it
- This makes results appear immediately on page load/refresh

### 8. Frontend: Pass workflowId to SSE hook

**File:** `frontend/src/components/Toolbar/Toolbar.tsx`

- Pass the current `workflowId` to `startStream()` so it uses the persisted endpoint

## Key Files

| File | Action |
|------|--------|
| `backend/app/models/workflow.py` | Add `last_run` column |
| `backend/alembic/versions/002_add_last_run_to_workflows.py` | Migration |
| `backend/app/schemas/execution.py` | Add persistence schemas |
| `backend/app/engine/executor.py` | Add `stream_graph_persisted()` |
| `backend/app/routers/workflows.py` | New endpoint + include last_run |
| `backend/app/schemas/workflow.py` | Add `last_run` to WorkflowResponse |
| `frontend/src/hooks/useWorkflowSSE.ts` | Use workflow-specific endpoint |
| `frontend/src/store/flowStore.ts` | Restore results from last_run on load |
| `frontend/src/components/Toolbar/Toolbar.tsx` | Pass workflowId |

## Verification

1. Run backend migration: `cd backend && uv run alembic upgrade head`
2. Start backend: `uv run uvicorn app.main:app --reload`
3. Start frontend: `cd frontend && pnpm dev`
4. Open a saved workflow, run it, verify results appear
5. Refresh the page — results should still be visible
6. Run again — new results should replace old ones
7. Check that unsaved workflows (ad-hoc) still work without persistence
