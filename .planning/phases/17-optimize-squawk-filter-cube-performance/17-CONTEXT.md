# Phase 17: Optimize Squawk Filter Cube Performance - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Apply the 3 performance optimizations documented in `docs/squawk_filter_optimizations.md` to `backend/app/cubes/squawk_filter.py`. SQL pushdown, set-based accumulation, and loop hoisting. Update existing tests if straightforward.

</domain>

<decisions>
## Implementation Decisions

### SQL pushdown (Issue 1)
- Apply `AND squawk = ANY(:codes)` filter to BOTH FR and Alison custom mode queries — not just Alison
- Once SQL guarantees only matching rows return, replace Python `any(...)` matching with `len(position_rows) > 0`

### Set-based accumulation (Issue 2)
- Convert `codes_seen`, `matched_codes`, `emergency_values` from lists to sets during accumulation
- Convert to sorted lists only at output time

### Loop hoisting (Issue 3)
- Hoist `mode == "emergency"` and `provider == "alison"` to booleans before the per-row loop

### Test updates
- Update existing squawk filter tests in-phase if changes are straightforward (new `:codes` SQL param, removed Python filtering)
- Don't over-engineer test changes — match the new query signatures and verify behavior is preserved

### Claude's Discretion
- Whether to combine any of the 3 fixes into a single commit or keep separate
- Test assertion adjustments needed for new SQL signatures

</decisions>

<specifics>
## Specific Ideas

- Reference implementation is fully specified in `docs/squawk_filter_optimizations.md` with before/after code
- Scope is strictly the 3 documented issues — no additional cleanup

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docs/squawk_filter_optimizations.md`: Complete optimization spec with exact code changes
- `backend/tests/test_squawk_filter.py`: 14 existing unit tests (mock DB via `patch` at import location)
- `backend/tests/test_integration_pipelines.py`: Integration tests referencing squawk filter

### Established Patterns
- DB mocking via `patch` at import location (`app.cubes.squawk_filter.engine`) with AsyncMock context managers (Phase 15 decision)
- String comparison for squawk codes throughout — no type conversion needed (Phase 11 decision)

### Integration Points
- `backend/app/cubes/squawk_filter.py` — sole file being optimized
- Test files may need SQL param updates to match new query signatures

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-optimize-squawk-filter-cube-performance*
*Context gathered: 2026-03-13*
