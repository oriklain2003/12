# Phase 17: Optimize Squawk Filter Cube Performance - Research

**Researched:** 2026-03-13
**Domain:** Python/SQLAlchemy performance optimization — SQL pushdown, set-based accumulation, loop hoisting
**Confidence:** HIGH

## Summary

This is a pure refactoring phase with a fully-specified implementation. The optimization spec in `docs/squawk_filter_optimizations.md` provides exact before/after code for all three changes. No library research is needed; the work is mechanical application of three known patterns to one file.

The key insight is that the current custom-mode SQL fetches ALL non-null squawk rows and discards non-matching rows in Python. At scale (500 hexes, thousands of positions each) this wastes significant network bandwidth. Adding `AND squawk = ANY(:codes)` to the SQL guarantees every returned row is a match, making the subsequent Python `any(...)` check redundant.

The secondary concern is that the existing 14 unit tests mock the DB layer. Two tests (`test_custom_mode_fr_provider`, `test_custom_mode_alison_provider`) currently rely on the mock returning non-matching rows that Python filters out. After the SQL pushdown, those rows would never arrive from a real DB — the mock data should be updated to reflect the new contract (SQL guarantees only matching rows return).

**Primary recommendation:** Apply the 3 optimizations in a single pass to `squawk_filter.py`, then update the 2 affected unit tests to match the new SQL contract.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**SQL pushdown (Issue 1)**
- Apply `AND squawk = ANY(:codes)` filter to BOTH FR and Alison custom mode queries — not just Alison
- Once SQL guarantees only matching rows return, replace Python `any(...)` matching with `len(position_rows) > 0`

**Set-based accumulation (Issue 2)**
- Convert `codes_seen`, `matched_codes`, `emergency_values` from lists to sets during accumulation
- Convert to sorted lists only at output time

**Loop hoisting (Issue 3)**
- Hoist `mode == "emergency"` and `provider == "alison"` to booleans before the per-row loop

**Test updates**
- Update existing squawk filter tests in-phase if changes are straightforward (new `:codes` SQL param, removed Python filtering)
- Don't over-engineer test changes — match the new query signatures and verify behavior is preserved

### Claude's Discretion
- Whether to combine any of the 3 fixes into a single commit or keep separate
- Test assertion adjustments needed for new SQL signatures

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

## Standard Stack

### Core
| Component | Version | Purpose |
|-----------|---------|---------|
| SQLAlchemy `text()` | Already in use | Parameterized SQL queries |
| Python `set` | Built-in | O(1) membership testing |
| AsyncMock / patch | Already in use | DB mocking in tests |

No new libraries needed. All changes are within existing patterns.

---

## Architecture Patterns

### File Scope
Only one production file is modified:
```
backend/app/cubes/squawk_filter.py   # sole file being optimized
backend/tests/test_squawk_filter.py  # test updates for new SQL contract
```

### Pattern 1: SQL Pushdown (Issue 1)

**What:** Move `squawk` filtering from Python into the WHERE clause using PostgreSQL's `= ANY(:codes)` array operator.

**Current SQL (FR custom mode):**
```sql
WHERE flight_id = ANY(:ids)
  AND squawk IS NOT NULL
```

**After (FR custom mode):**
```sql
WHERE flight_id = ANY(:ids)
  AND squawk = ANY(:codes)
```
Params: `{"ids": ids, "codes": list(target_codes)}`

**Current SQL (Alison custom mode):**
```sql
WHERE hex = ANY(:ids)
  AND ts >= to_timestamp(:cutoff)
  AND squawk IS NOT NULL
```

**After (Alison custom mode):**
```sql
WHERE hex = ANY(:ids)
  AND ts >= to_timestamp(:cutoff)
  AND squawk = ANY(:codes)
```
Params: `{"ids": ids, "cutoff": cutoff_epoch, "codes": list(target_codes)}`

**Downstream Python change:** Because SQL now guarantees all returned rows match, the Python matching check in Step 4 for custom mode becomes:
```python
# BEFORE
matched = any(r["squawk"] in target_codes for r in position_rows if r["squawk"])

# AFTER
matched = len(position_rows) > 0
```

Note: FR emergency mode still uses the `any(r["squawk"] in target_codes ...)` pattern (unchanged) because its SQL does not filter on squawk — it fetches all non-null squawk rows and checks against EMERGENCY_CODES_FR in Python.

### Pattern 2: Set-Based Accumulation (Issue 2)

**What:** Replace list accumulation with sets, convert to sorted lists at output.

**Before:**
```python
codes_seen: list[str] = []
matched_codes: list[str] = []
emergency_values: list[str] = []

if code not in codes_seen:       # O(N) scan
    codes_seen.append(code)
```

**After:**
```python
codes_seen_set: set[str] = set()
matched_codes_set: set[str] = set()
emergency_values_set: set[str] = set()

codes_seen_set.add(code)         # O(1)

# at output time:
"codes_seen": sorted(codes_seen_set),
"matched_codes": sorted(matched_codes_set),
```

### Pattern 3: Loop Hoisting (Issue 3)

**What:** Compute invariant mode/provider booleans once before the per-row loop.

**Before (inside per-row loop):**
```python
if code in target_codes or mode == "emergency":
    ...
if provider == "alison" and emergency_values:
    ...
```

**After (hoisted before loop):**
```python
is_emergency = (mode == "emergency")
is_alison = (provider == "alison")

for r in position_rows:
    if is_emergency or code in target_codes:
        ...
if is_alison and emergency_values_set:
    ...
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| SQL array membership | Custom string formatting | PostgreSQL `= ANY(:codes)` with SQLAlchemy `text()` + list param |
| Unique accumulation | List + `not in` guard | Python `set.add()` |

---

## Common Pitfalls

### Pitfall 1: FR Emergency Mode — Do Not Add SQL Pushdown

**What goes wrong:** Applying `AND squawk = ANY(:codes)` to the FR emergency mode query by mistake.
**Why it happens:** The fix reads "apply to BOTH FR and Alison custom mode" but FR emergency is a different branch.
**How to avoid:** The FR provider has a single SQL block that handles both custom and emergency modes together (it always fetches by `squawk IS NOT NULL`). The `:codes` param is only added to the custom-mode path. Alison has two separate SQL blocks — emergency is already correct, only the custom block changes.
**Actual code structure:** Looking at the current code (lines 201-264 of `squawk_filter.py`), the FR provider has ONE SQL block for both modes. The fix must either (a) split FR into two SQL paths (emergency vs custom) similar to Alison, or (b) pass `target_codes` as the `:codes` param — which for emergency mode would be `EMERGENCY_CODES_FR = {"7500", "7600", "7700"}`.

**Resolution:** Option (b) is simpler. Pass `list(target_codes)` for both FR modes — in emergency mode `target_codes` is already set to `EMERGENCY_CODES_FR`, so the SQL naturally handles both cases. The Python `any(...)` check for FR emergency can then also become `len(position_rows) > 0`.

### Pitfall 2: Test Mock Data Represents Pre-Filter DB Output

**What goes wrong:** Tests `test_custom_mode_fr_provider` and `test_custom_mode_alison_provider` currently include non-matching rows in mock data (e.g., rows with squawk="1200" when filtering for "7700"). After SQL pushdown, the SQL would never return those rows.
**Why it happens:** Before the fix, Python was the filter — mock data could include everything. After the fix, SQL is the filter — mock data should represent what SQL returns (only matching rows).
**How to avoid:** Update those two tests to remove non-matching rows from mock data. The behavioral assertion (FL002 not in result) changes meaning slightly — with SQL pushdown, FL002 is absent because it was never returned, not because Python filtered it. The test still passes either way.
**Warning signs:** If tests pass with non-matching rows still in mock data, it's not a test failure — but it's a misleading test that doesn't model the new contract.

### Pitfall 3: Output Order of codes_seen / matched_codes

**What goes wrong:** Existing tests check `assert "1200" in details["codes_seen"]` — these still pass. But if any test checks exact list equality like `assert details["codes_seen"] == ["1200", "7700"]`, order now depends on `sorted()` not insertion order.
**How to avoid:** Check all assertions in `test_code_change_detection`. The current test uses `in` membership checks, not exact list equality — no change needed.

### Pitfall 4: `emergency_values_set` Conditional

**What goes wrong:** The current code checks `if provider == "alison" and emergency_values:`. After converting to a set, the check becomes `if is_alison and emergency_values_set:`.
**How to avoid:** The set conditional evaluates truthiness the same way as a list — empty set is falsy. No behavioral change, just rename.

---

## Code Examples

### SQL Change — FR Provider (custom + emergency unified)

```python
# Source: docs/squawk_filter_optimizations.md + current squawk_filter.py analysis
if provider == "fr":
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT flight_id AS id,
                       squawk,
                       NULL AS emergency,
                       timestamp AS ts
                FROM research.normal_tracks
                WHERE flight_id = ANY(:ids)
                  AND squawk = ANY(:codes)
                ORDER BY flight_id, timestamp
                LIMIT 100000
                """
            ),
            {"ids": ids, "codes": list(target_codes)},
        )
        rows = result.fetchall()
```

Note: For FR emergency mode, `target_codes` is already `EMERGENCY_CODES_FR = {"7500", "7600", "7700"}` at this point in the code (set in Step 2). So `list(target_codes)` passes the right codes for both modes.

### Hoisted Booleans + Set Accumulation

```python
# Source: docs/squawk_filter_optimizations.md
is_emergency = (mode == "emergency")
is_alison = (provider == "alison")

codes_seen_set: set[str] = set()
matched_codes_set: set[str] = set()
emergency_values_set: set[str] = set()
prev_code: str | None = None

for r in position_rows:
    code = r["squawk"]
    em = r["emergency"]
    ts = r["ts"]

    if code is not None:
        codes_seen_set.add(code)
        if is_emergency or code in target_codes:
            matched_codes_set.add(code)
        if prev_code is not None and code != prev_code:
            code_changes.append({
                "from": prev_code,
                "to": code,
                "ts": ts.isoformat() if hasattr(ts, "isoformat") else str(ts) if ts else None,
            })
        prev_code = code

    if em and em != "none":
        emergency_values_set.add(em)

detail: dict[str, Any] = {
    "codes_seen": sorted(codes_seen_set),
    "code_changes": code_changes,
    "matched_codes": sorted(matched_codes_set),
}
if is_alison and emergency_values_set:
    detail["emergency_values"] = sorted(emergency_values_set)
```

### Matching Logic After SQL Pushdown

```python
# Source: docs/squawk_filter_optimizations.md
# For all cases after SQL pushdown, every returned row is already a match
matched = len(position_rows) > 0
```

---

## Test Impact Analysis

### Tests in `backend/tests/test_squawk_filter.py` (14 tests)

| Test | Impact | Change Required |
|------|--------|-----------------|
| `test_cube_metadata` | None | No change |
| `test_cube_inputs` | None | No change |
| `test_cube_outputs` | None | No change |
| `test_full_result_input_accepts_full_result` | None | No change |
| `test_empty_input_guard` | None | No change |
| `test_custom_mode_fr_provider` | MOCK DATA | Remove non-matching row (FL002/squawk=1200) from mock; SQL no longer returns it |
| `test_custom_mode_alison_provider` | MOCK DATA | Remove non-matching row (DEF456/squawk=1200) from mock; SQL no longer returns it |
| `test_custom_mode_empty_squawk_codes` | None | No change |
| `test_emergency_mode_fr` | MOCK DATA | If FR now uses `squawk = ANY(:codes)`, mock should only return rows with 7500/7600/7700 — remove FL002/squawk=1200 |
| `test_emergency_mode_alison` | None | Alison emergency query unchanged |
| `test_code_change_detection` | None | Uses `in` membership checks; sorted output still passes |
| `test_full_result_extraction_flight_ids` | None | No change |
| `test_full_result_extraction_hex_list` | None | No change |
| `test_emergency_values_in_alison_details` | None | `"general" in details["emergency_values"]` still works for sorted list |

**Tests needing mock data updates: 3** (`test_custom_mode_fr_provider`, `test_custom_mode_alison_provider`, `test_emergency_mode_fr`)

### Tests in `backend/tests/test_integration_pipelines.py`

The integration pipeline tests use `MockSquawkFilterCube` (a stub, not the real cube). No changes needed — the stub is not affected by the optimization.

---

## State of the Art

| Aspect | Current State | After Optimization |
|--------|--------------|-------------------|
| FR custom mode SQL | Fetches all non-null squawk rows | Fetches only rows matching `:codes` |
| Alison custom mode SQL | Fetches all non-null squawk rows | Fetches only rows matching `:codes` |
| Python match check | `any(r["squawk"] in target_codes ...)` — O(N) scan | `len(position_rows) > 0` — O(1) |
| Unique code accumulation | List + O(N) `not in` check | Set + O(1) `add()` |
| Per-row string compares | `mode == "emergency"` re-evaluated every row | Hoisted to boolean before loop |

---

## Open Questions

1. **FR emergency mode — unified or split SQL path?**
   - What we know: Current FR code has one SQL block used for both custom and emergency modes. The spec says add `:codes` to "both FR and Alison custom mode."
   - What's unclear: Should FR emergency get its own SQL path (like Alison) or reuse the same block with `target_codes = EMERGENCY_CODES_FR`?
   - Recommendation: Reuse with `list(target_codes)` — simpler, and `target_codes` is already set to `EMERGENCY_CODES_FR` for FR emergency in Step 2. The Python `matched = len(position_rows) > 0` then applies uniformly to all paths.

---

## Sources

### Primary (HIGH confidence)
- `docs/squawk_filter_optimizations.md` — Complete optimization spec with exact before/after SQL and Python
- `backend/app/cubes/squawk_filter.py` — Current implementation (read in full)
- `backend/tests/test_squawk_filter.py` — All 14 existing tests (read in full)
- `backend/tests/test_integration_pipelines.py` — Integration tests (squawk stubs confirmed independent)

### Secondary (HIGH confidence)
- `.planning/phases/17-optimize-squawk-filter-cube-performance/17-CONTEXT.md` — User decisions
- `.planning/STATE.md` — Project history and established patterns

---

## Metadata

**Confidence breakdown:**
- Optimization spec: HIGH — exact code provided in `docs/squawk_filter_optimizations.md`
- Test impact: HIGH — all 14 tests read and analyzed
- FR emergency unification: MEDIUM — spec says "custom mode" only, but unified `:codes` approach is simpler and correct

**Research date:** 2026-03-13
**Valid until:** Indefinite — no external dependencies, pure refactoring
