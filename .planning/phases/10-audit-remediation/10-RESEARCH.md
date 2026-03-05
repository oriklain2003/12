# Phase 10: Audit Remediation (Gap Closure) - Research

**Researched:** 2026-03-05
**Domain:** Documentation accuracy, tech debt cleanup, dead code removal
**Confidence:** HIGH

## Summary

Phase 10 is a pure remediation phase with no new features. All work targets discrepancies identified in the v1.0 milestone audit (`v1.0-MILESTONE-AUDIT.md`): three SUMMARY frontmatter files have empty `requirements_completed` fields despite the underlying code being fully implemented; one frontend display string hardcodes a stale row limit; one backend docstring references a stale row limit; the BACK-13 requirement text describes the wrong HTTP method and endpoint path; and the original synchronous `POST /api/workflows/{id}/run` endpoint is dead code (the frontend uses only the SSE stream path).

Every gap is a documentation or cosmetic code discrepancy — the functional code is correct and wired. No schema migrations, no dependency changes, no architectural decisions are required. The planner should treat each task as a surgical text edit in a single well-known file.

**Primary recommendation:** One plan, seven tasks executed in order. No parallelization needed — all edits are independent and low-risk. Confirm each file edit visually before marking complete.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WFLOW-04 | Run button triggers SSE connection, streams per-cube status updates to Zustand store, updates CubeNode indicators in real-time | Implemented in 05-03 (useWorkflowSSE.ts + Toolbar.tsx). SUMMARY frontmatter gap only — add to 05-03-SUMMARY.md requirements_completed |
| WFLOW-05 | Each CubeNode shows execution status indicator: pending/running/done/error | Implemented in 05-03 (CubeNode.tsx status badges). SUMMARY frontmatter gap only |
| WFLOW-06 | Error messages from failed cubes display inline on the CubeNode | Implemented in 05-03 (error banner). SUMMARY frontmatter gap only |
| WFLOW-07 | Keyboard shortcuts — Delete removes selected, Ctrl+S saves, Ctrl+Enter runs | Implemented in 05-03 (Toolbar.tsx keydown handler). SUMMARY frontmatter gap only |
| WFLOW-08 | Overall pipeline progress indicator showing "X/Y cubes completed" with progress bar | Implemented in 05-03 (Toolbar.tsx progress bar). SUMMARY frontmatter gap only |
| RSLT-02 | Leaflet map panel with CartoDB dark tiles renders markers for lat/lon rows | Implemented in 06-02 (ResultsMap.tsx). SUMMARY frontmatter gap only — add to 06-02-SUMMARY.md |
| RSLT-03 | Bidirectional table↔map interaction — marker click scrolls table row, row click flies map | Implemented in 06-02 (ResultsDrawer.tsx bidirectional wiring). SUMMARY frontmatter gap only |
| GEO-04 | Get Learned Paths cube with centerline/corridor modes | Implemented in 08-02 (get_learned_paths.py). SUMMARY frontmatter gap only — add to 08-02-SUMMARY.md |
| BACK-08 | POST /api/workflows/{id}/run endpoint | Dead code — frontend uses SSE stream exclusively. Remove endpoint from workflows.py |
| BACK-11 | Result rows capped at 100 per cube with truncation flag | Actual limit is 10,000 (config.py result_row_limit=10000). Fix ResultsTable.tsx display string |
| BACK-13 | SSE endpoint (GET /api/workflows/{id}/run/stream) | Actual implementation is POST /api/workflows/run/stream (graph-in-body, no {id}). Update REQUIREMENTS.md requirement text |
| GEO-02 | Global result_row_limit bumped from 100 to 10,000 | config.py is correct (10000). executor.py docstring still says "(100)". Fix docstring |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python (uv) | 3.12 | Backend edits | Project standard |
| TypeScript/React | 18 | Frontend edits | Project standard |

No new dependencies required for this phase. All edits are text changes in existing files.

### Supporting
None — this phase uses no new libraries.

### Alternatives Considered
None — all changes are prescribed by the audit report.

## Architecture Patterns

### Pattern 1: SUMMARY frontmatter `requirements_completed` field

**What:** Each `XX-YY-SUMMARY.md` file has a YAML frontmatter block at the top (between `---` delimiters). The field `requirements_completed` is a YAML list of requirement IDs that the plan satisfied. When this field is absent or empty, the GSD audit system cannot trace which requirements were closed by which plan.

**When to use:** Add all requirement IDs that the plan's code directly implements.

**Example (05-03-SUMMARY.md after fix):**
```yaml
---
phase: 05-workflow-management-execution-integration
plan: 03
requirements_completed: [WFLOW-04, WFLOW-05, WFLOW-06, WFLOW-07, WFLOW-08]
subsystem: frontend-execution
# ... rest of frontmatter unchanged
---
```

**Example (06-02-SUMMARY.md after fix):**
```yaml
---
phase: 06-results-display-tables-map-bidirectional-interaction
plan: 02
requirements_completed: [RSLT-02, RSLT-03]
subsystem: frontend/results
# ... rest of frontmatter unchanged
---
```

**Example (08-02-SUMMARY.md after fix):**
```yaml
---
phase: 08-geo-temporal-playback-learned-paths-and-flight-course-cubes
plan: "02"
requirements_completed: [GEO-04]
subsystem: backend-cubes
# ... rest of frontmatter unchanged
---
```

### Pattern 2: ResultsTable truncation warning text

**What:** `frontend/src/components/Results/ResultsTable.tsx` line 70 renders a warning string when `truncated === true`. The string "Showing first 100 rows" is stale — the actual limit is 10,000 (from `config.py`).

**Fix:** Change line 70 from:
```tsx
<div className="results-table__truncation-warning">Showing first 100 rows</div>
```
to:
```tsx
<div className="results-table__truncation-warning">Showing first 10,000 rows</div>
```

### Pattern 3: executor.py docstring correction

**What:** `backend/app/engine/executor.py` line 99 in `apply_row_limit` docstring says `defaults to settings.result_row_limit (100)`. The "(100)" parenthetical is stale — actual value is 10,000.

**Fix:** Change line 99 from:
```python
        limit: Row cap; defaults to settings.result_row_limit (100).
```
to:
```python
        limit: Row cap; defaults to settings.result_row_limit (10,000).
```

### Pattern 4: REQUIREMENTS.md BACK-13 text update

**What:** `REQUIREMENTS.md` line 30 documents BACK-13 as:
> SSE endpoint (GET /api/workflows/{id}/run/stream) streams per-cube status events (pending, running, done, error) via sse-starlette EventSourceResponse

The actual implementation (confirmed in `backend/app/routers/workflows.py` lines 42-66) is:
- Method: `POST` (not GET)
- Path: `/api/workflows/run/stream` (no `{id}` — graph sent in request body)

**Fix:** Update BACK-13 requirement text in `.planning/REQUIREMENTS.md` to reflect actual endpoint.

Corrected text:
```
- [x] **BACK-13**: SSE endpoint (POST /api/workflows/run/stream) accepts WorkflowGraph in request body, streams per-cube status events (pending, running, done, error) via sse-starlette EventSourceResponse
```

### Pattern 5: Remove dead `POST /api/workflows/{id}/run` endpoint

**What:** `backend/app/routers/workflows.py` lines 150-174 define `run_workflow()` which calls `execute_graph()`. This endpoint was the original synchronous execution path (Phase 2, BACK-08). It became dead code when Phase 3 introduced the SSE stream endpoint and the frontend was wired exclusively to the SSE path.

**Risks to assess before removal:**
- Check no test files call this endpoint directly
- Check `backend/app/main.py` for any direct reference beyond router inclusion
- The `execute_graph` function imported in workflows.py is used by both stream_graph (internally) and this endpoint — removing the endpoint does NOT remove execute_graph usage from stream_graph internals

**Safe removal:** Delete the entire `run_workflow` function (lines 150-174). Also remove `execute_graph` from the import on line 14 if it is no longer referenced elsewhere in the router file.

**Anti-Patterns to Avoid**
- **Touching executor.py logic:** Only change the docstring string. Do not alter the `apply_row_limit` function behavior.
- **Editing REQUIREMENTS.md traceability table:** The audit notes that GEO-01 through GEO-07 show "Not Started" in the traceability table — but fixing the traceability table is NOT listed in Phase 10's task list. Do not make unrequested edits.
- **Changing BACK-08 checkbox status:** BACK-08 is already marked `[x]` in REQUIREMENTS.md. Removing the dead endpoint does not change the requirement status — the requirement was satisfied, the endpoint just became redundant.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Frontmatter parsing | Custom YAML parser | Direct text edit | These are simple key additions in known positions |
| Row limit discovery | Runtime config check | Read config.py directly | Value is a hardcoded default: `result_row_limit: int = 10000` |

## Common Pitfalls

### Pitfall 1: Adding `requirements_completed` in wrong frontmatter position
**What goes wrong:** YAML frontmatter is sensitive to structure. Adding the field after a nested object without proper indentation breaks the YAML block.
**Why it happens:** The existing frontmatter has multi-line fields (`dependency_graph`, `tech_stack`, `key_files`).
**How to avoid:** Add `requirements_completed` as a top-level key immediately after `plan:` — before any nested objects. This matches GSD convention.
**Warning signs:** Any YAML parse error when reading the SUMMARY file after edit.

### Pitfall 2: Removing `execute_graph` import prematurely
**What goes wrong:** `execute_graph` is called internally by `stream_graph` — but the import in `workflows.py` line 14 also imports it. If `execute_graph` is used nowhere else in workflows.py after removing `run_workflow`, the import becomes unused (linting warning, not breakage). If it IS still used elsewhere, removing it breaks the module.
**How to avoid:** After deleting `run_workflow`, search workflows.py for `execute_graph` references. If zero remain, remove it from the import line.

### Pitfall 3: Stale frontend TypeScript after removing backend endpoint
**What goes wrong:** The frontend API client might call `POST /api/workflows/{id}/run`. If so, removing the backend endpoint would silently break a frontend code path.
**How to avoid:** Before removing the backend endpoint, grep the frontend for any references to `/run` that are NOT `/run/stream`. The SSE hook in `useWorkflowSSE.ts` should be the only execution caller.

### Pitfall 4: Wrong row limit number format
**What goes wrong:** Writing "10000" vs "10,000" — the display string should be human-readable with comma separator.
**How to avoid:** The fix is "10,000" (with comma) in the UI string. The docstring fix should also use "10,000" for consistency with human-readable convention.

## Code Examples

### Current state — files that need edits

**ResultsTable.tsx (line 70):**
```tsx
// BEFORE (stale)
<div className="results-table__truncation-warning">Showing first 100 rows</div>

// AFTER
<div className="results-table__truncation-warning">Showing first 10,000 rows</div>
```

**executor.py (line 99):**
```python
# BEFORE (stale)
        limit: Row cap; defaults to settings.result_row_limit (100).

# AFTER
        limit: Row cap; defaults to settings.result_row_limit (10,000).
```

**workflows.py — endpoint to remove (lines 150-174):**
```python
# DELETE THIS ENTIRE FUNCTION
@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Execute a workflow graph and return per-node results. ..."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    graph = WorkflowGraph.model_validate(wf.graph_json)
    try:
        return await execute_graph(graph)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

**REQUIREMENTS.md BACK-13 (line 30):**
```markdown
# BEFORE
- [x] **BACK-13**: SSE endpoint (GET /api/workflows/{id}/run/stream) streams per-cube status events (pending, running, done, error) via sse-starlette EventSourceResponse

# AFTER
- [x] **BACK-13**: SSE endpoint (POST /api/workflows/run/stream) accepts WorkflowGraph in request body, streams per-cube status events (pending, running, done, error) via sse-starlette EventSourceResponse
```

## File Inventory

Exact files touched per task:

| Task | File | Change Type |
|------|------|-------------|
| 1 | `.planning/phases/05-workflow-management-execution-integration/05-03-SUMMARY.md` | Add `requirements_completed: [WFLOW-04, WFLOW-05, WFLOW-06, WFLOW-07, WFLOW-08]` to frontmatter |
| 2 | `.planning/phases/06-results-display-tables-map-bidirectional-interaction/06-02-SUMMARY.md` | Add `requirements_completed: [RSLT-02, RSLT-03]` to frontmatter |
| 3 | `.planning/phases/08-geo-temporal-playback-learned-paths-and-flight-course-cubes/08-02-SUMMARY.md` | Add `requirements_completed: [GEO-04]` to frontmatter |
| 4 | `frontend/src/components/Results/ResultsTable.tsx` | Change "100 rows" to "10,000 rows" (line 70) |
| 5 | `backend/app/engine/executor.py` | Change "(100)" to "(10,000)" in docstring (line 99) |
| 6 | `.planning/REQUIREMENTS.md` | Update BACK-13 text: GET→POST, /{id}/run/stream→/run/stream |
| 7 | `backend/app/routers/workflows.py` | Remove `run_workflow` function (lines 150-174); clean up unused imports |

## Pre-Task Checks

The planner should include these verification steps before each code edit:

**Task 7 pre-checks (dead endpoint removal):**
1. Grep `frontend/` for any `/run` references NOT containing `/run/stream` — confirm zero hits
2. Read `backend/app/routers/workflows.py` fully before editing — confirm `execute_graph` is only used in `run_workflow` (not elsewhere in the file)
3. After removal, confirm `execute_graph` is not imported anywhere in the file; if unused, remove from import line 14

**All tasks:** Read the file before editing. Confirm exact line numbers match expectations (files may have been modified since audit).

## Open Questions

1. **Does any test file call `POST /api/workflows/{id}/run`?**
   - What we know: `backend/tests/` directory exists. Phase 2 plan (02-02) created executor tests.
   - What's unclear: Whether any test exercises the now-dead endpoint.
   - Recommendation: Planner should include a grep of `backend/tests/` for `/{id}/run` before removing the endpoint. If tests exist, remove them alongside the endpoint.

2. **Does the frontend SSE hook use GET or POST for the stream endpoint?**
   - What we know: `useWorkflowSSE.ts` is described in 05-03-SUMMARY as creating `new EventSource('/api/workflows/{id}/run/stream')` — but the actual current backend is `POST /api/workflows/run/stream` (graph-in-body).
   - What's unclear: Whether `useWorkflowSSE.ts` was updated after the endpoint design changed, or whether there is a mismatch being papered over.
   - Recommendation: Read `frontend/src/hooks/useWorkflowSSE.ts` as part of task planning. The SSE stream works (confirmed by audit), so this discrepancy may be in the SUMMARY description, not the actual code.

## Sources

### Primary (HIGH confidence)
- Direct file reads: `.planning/v1.0-MILESTONE-AUDIT.md` — authoritative source of all gaps
- Direct file reads: `backend/app/routers/workflows.py` — confirmed dead endpoint at lines 150-174
- Direct file reads: `backend/app/engine/executor.py` — confirmed stale docstring at line 99
- Direct file reads: `frontend/src/components/Results/ResultsTable.tsx` — confirmed "100 rows" at line 70
- Direct file reads: `backend/app/config.py` — confirmed `result_row_limit: int = 10000`
- Direct file reads: 05-03-SUMMARY.md, 06-02-SUMMARY.md, 08-02-SUMMARY.md — confirmed empty `requirements_completed`
- Direct file reads: `.planning/REQUIREMENTS.md` — confirmed BACK-13 text and BACK-08 status

### Secondary (MEDIUM confidence)
- `.planning/ROADMAP.md` phase 10 task list — confirms scope of 7 tasks exactly as listed in objective

## Metadata

**Confidence breakdown:**
- File locations: HIGH — all files read directly; line numbers confirmed
- Change content: HIGH — exact before/after text derived from file contents
- Side effects (import cleanup, test removal): MEDIUM — requires pre-task grep to confirm

**Research date:** 2026-03-05
**Valid until:** Indefinite — this is a static codebase audit; findings won't change unless someone edits the target files before Phase 10 executes
