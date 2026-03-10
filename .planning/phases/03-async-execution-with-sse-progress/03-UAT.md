---
status: testing
phase: 03-async-execution-with-sse-progress
source: 03-01-SUMMARY.md
started: 2026-03-03T22:00:00Z
updated: 2026-03-03T22:00:00Z
---

## Current Test

number: 1
name: All Tests Pass
expected: |
  Run `cd backend && uv run pytest` — all 23 tests pass (7 stream_graph + 5 SSE + 11 executor).
awaiting: user response

## Tests

### 1. All Tests Pass
expected: Run `cd backend && uv run pytest` — all 23 tests pass (7 stream_graph + 5 SSE + 11 executor).
result: [pending]

### 2. SSE Endpoint Streams Cube Status Events
expected: Start server (`cd backend && uv run uvicorn app.main:app --reload`), create or use an existing workflow, then `curl -N http://localhost:8000/api/workflows/{id}/run/stream`. You should see SSE events with `event: cube_status` and JSON data showing status progression (pending → running → done) for each cube in the workflow.
result: [pending]

### 3. POST Run Backward Compatibility
expected: POST to `http://localhost:8000/api/workflows/{id}/run` still returns a JSON result dict keyed by cube node_id, same as before Phase 3. Existing sync execution path is unbroken.
result: [pending]

### 4. SSE Cycle Detection Returns HTTP 400
expected: Create or use a workflow with a cycle in its graph, then hit GET `/api/workflows/{id}/run/stream`. The endpoint returns HTTP 400 (not a stream) with an error message about the cycle.
result: [pending]

### 5. SSE Missing Workflow Returns HTTP 404
expected: Hit GET `/api/workflows/99999/run/stream` (nonexistent ID). The endpoint returns HTTP 404 with a "not found" error.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0

## Gaps

[none yet]
