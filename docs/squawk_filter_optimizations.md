# Squawk Filter — Performance Optimizations

Three issues, ranked by impact. Two are in the SQL, one is in the Python loop.

---

## Issue 1 — Custom mode fetches every squawk row, filters in Python (biggest win)

For both FR and Alison custom mode, the SQL returns **all rows where `squawk IS NOT NULL`**, then Python discards every row that isn't in `target_codes`. If you have 500 hexes with thousands of positions each, you're shipping the entire squawk history across the network just to throw most of it away.

**Current:**
```python
# Alison custom — fetches all non-null squawk rows, Python filters later
WHERE hex = ANY(:ids)
  AND ts >= to_timestamp(:cutoff)
  AND squawk IS NOT NULL          # ← brings back everything
```

**Fix — push the filter into SQL:**
```python
# Alison custom — only rows that actually match come back
WHERE hex = ANY(:ids)
  AND ts >= to_timestamp(:cutoff)
  AND squawk = ANY(:codes)        # ← Postgres filters, not Python

# params:
{"ids": ids, "cutoff": cutoff_epoch, "codes": list(target_codes)}
```

Same fix for FR custom mode:
```python
WHERE flight_id = ANY(:ids)
  AND squawk = ANY(:codes)        # ← add this
```

Once this is in place, **every row returned is already a match**, so the Python `any(...)` check in Step 4 becomes redundant and can be removed entirely:

```python
# BEFORE — two passes: SQL fetches all, Python filters
matched = any(r["squawk"] in target_codes for r in position_rows if r["squawk"])

# AFTER — SQL already guarantees every row matches, skip the scan
matched = len(position_rows) > 0
```

---

## Issue 2 — `codes_seen` and `matched_codes` use list + O(N) membership checks

In the code-change loop, `codes_seen` and `matched_codes` are **lists**, and every new code does a linear scan to check membership with `if code not in codes_seen`. For a flight with 1,000 positions cycling through a handful of squawk codes, this is quadratic work for no reason.

**Current:**
```python
codes_seen: list[str] = []
matched_codes: list[str] = []
emergency_values: list[str] = []

if code not in codes_seen:          # O(N) scan every row
    codes_seen.append(code)
if code not in matched_codes:       # O(N) scan every row
    matched_codes.append(code)
if em not in emergency_values:      # O(N) scan every row
    emergency_values.append(em)
```

**Fix — use sets during accumulation, convert to list only at the end:**
```python
codes_seen_set: set[str] = set()
matched_codes_set: set[str] = set()
emergency_values_set: set[str] = set()

# inside the loop:
if code is not None:
    codes_seen_set.add(code)                              # O(1)
    if mode == "emergency" or code in target_codes:
        matched_codes_set.add(code)                       # O(1)
    if prev_code is not None and code != prev_code:
        code_changes.append({...})
    prev_code = code

if em and em != "none":
    emergency_values_set.add(em)                          # O(1)

# at the end, convert once:
detail = {
    "codes_seen": sorted(codes_seen_set),
    "code_changes": code_changes,
    "matched_codes": sorted(matched_codes_set),
}
```

---

## Issue 3 — `mode == "emergency"` evaluated on every row in the inner loop

`mode` is a constant for the lifetime of the request. Checking `mode == "emergency"` inside the per-row loop (which runs for every position of every matching flight) re-evaluates the same string comparison thousands of times.

**Current:**
```python
for r in position_rows:            # could be thousands of rows
    ...
    if code in target_codes or mode == "emergency":   # ← checked every row
```

**Fix — compute a boolean once before the loop:**
```python
is_emergency = (mode == "emergency")

for r in position_rows:
    ...
    if is_emergency or code in target_codes:          # ← flag, not string compare
```

Same applies to the `provider == "alison"` check at the bottom of the loop body — hoist it out.

---

## Summary

| Issue | Where | Fix | Impact |
|-------|-------|-----|--------|
| Custom mode fetches all rows, filters in Python | SQL | Add `AND squawk = ANY(:codes)` | **High** — cuts network transfer to only matching rows |
| `codes_seen`/`matched_codes` use list + O(N) `not in` | Python loop | Use `set`, convert at end | **Medium** — O(N²) → O(N) per flight |
| `mode == "emergency"` checked per row | Python loop | Hoist to boolean before loop | **Low** — minor, but free |
