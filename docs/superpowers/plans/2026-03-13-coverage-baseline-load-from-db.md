# Coverage Baseline: Load from DB at Startup

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load the coverage baseline from the pre-existing `coverage_baseline` DB table at startup instead of recomputing it from the raw `positions` table every time.

**Architecture:** The batch script (`detect_batch.py`) already creates a `coverage_baseline` table but never populates it. We'll (1) add a write step to the batch script so it persists the computed baseline (DELETE + COPY full refresh), and (2) replace the app's startup computation with a simple SELECT from that table. A fallback to the current compute path remains if the table is empty.

**Tech Stack:** Python, SQLAlchemy async, psycopg, FastAPI lifespan, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/detect_batch.py` | Modify | Add `save_coverage_baseline()` to persist computed baseline to DB |
| `backend/app/signal/rule_based.py` | Modify | Add `load_coverage_baseline_async()`, update `start_coverage_baseline_build()` to load-then-fallback |
| `backend/tests/test_signal_rule_based.py` | Modify | Add tests for the new load path |

---

## Chunk 1: Persist baseline in batch script

### Task 1: Add `save_coverage_baseline()` to detect_batch.py

**Files:**
- Modify: `scripts/detect_batch.py:150-163` (after ensure_schema), and add new function + call site

- [ ] **Step 1: Write the `save_coverage_baseline` function**

Add this function after the `ensure_schema` function (around line 163) in `scripts/detect_batch.py`:

```python
def save_coverage_baseline(
    conn: psycopg.Connection,
    coverage: dict[tuple[float, float], dict[str, Any]],
) -> None:
    """Persist the computed coverage baseline to the coverage_baseline table.

    Uses DELETE + COPY for a full table refresh each run.
    Reuses the existing `_copy_value` helper for consistent formatting.
    No new imports needed — `io` is already imported at the top of the file.
    """
    if not coverage:
        log.warning("Empty coverage baseline — skipping DB write")
        return

    cols = "lat_cell, lon_cell, median_rssi, reports_per_hour, temporal_coverage, is_coverage_hole"
    buf = io.StringIO()
    for (lat_cell, lon_cell), cell in coverage.items():
        vals = [
            lat_cell,
            lon_cell,
            cell["median_rssi"],
            cell["reports_per_hour"],
            cell["temporal_coverage"],
            cell["is_coverage_hole"],
        ]
        buf.write("\t".join(_copy_value(v) for v in vals) + "\n")

    buf.seek(0)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM coverage_baseline")
        with cur.copy(f"COPY coverage_baseline ({cols}) FROM STDIN") as copy:
            for line in buf:
                copy.write(line)
    conn.commit()
    log.info("Saved %d coverage baseline cells to DB", len(coverage))
```

- [ ] **Step 2: Call `save_coverage_baseline` after baseline is built**

In the `main()` function, after line 715 (`coverage = build_coverage_baseline(...)`), add:

```python
        if not args.dry_run:
            save_coverage_baseline(conn, coverage)
```

- [ ] **Step 3: Verify manually (optional)**

Run: `cd scripts && python detect_batch.py --dry-run --lookback-days 2`

This should still work without writing. A non-dry-run execution will populate the table.

- [ ] **Step 4: Commit**

```bash
git add scripts/detect_batch.py
git commit -m "feat: persist coverage baseline to DB in batch script"
```

---

## Chunk 2: Load baseline from DB at app startup

### Task 2: Add `load_coverage_baseline_async()` to rule_based.py

**Files:**
- Modify: `backend/app/signal/rule_based.py:44-75`

- [ ] **Step 1: Write failing test for the load function**

Add to `backend/tests/test_signal_rule_based.py`:

```python
class TestLoadCoverageBaseline:

    @pytest.mark.asyncio
    async def test_load_coverage_baseline_from_db(self):
        """Load baseline from coverage_baseline table -> dict with correct structure."""
        from app.signal.rule_based import load_coverage_baseline_async

        # Row: lat_cell, lon_cell, median_rssi, reports_per_hour, temporal_coverage, is_coverage_hole
        fake_rows = [
            (32.0, 34.0, -8.0, 45.0, 0.85, False),
            (32.5, 34.5, -25.0, 3.0, 0.2, True),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = fake_rows

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.signal.rule_based.engine", mock_engine):
            baseline = await load_coverage_baseline_async()

        assert len(baseline) == 2
        assert (32.0, 34.0) in baseline
        assert baseline[(32.0, 34.0)]["median_rssi"] == -8.0
        assert baseline[(32.0, 34.0)]["is_coverage_hole"] is False
        assert (32.5, 34.5) in baseline
        assert baseline[(32.5, 34.5)]["is_coverage_hole"] is True

    @pytest.mark.asyncio
    async def test_load_coverage_baseline_empty_falls_back(self):
        """Empty coverage_baseline table -> returns empty dict (no error)."""
        from app.signal.rule_based import load_coverage_baseline_async

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.signal.rule_based.engine", mock_engine):
            baseline = await load_coverage_baseline_async()

        assert baseline == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_signal_rule_based.py::TestLoadCoverageBaseline -v`

Expected: FAIL with `ImportError: cannot import name 'load_coverage_baseline_async'`

- [ ] **Step 3: Implement `load_coverage_baseline_async`**

Add this function in `backend/app/signal/rule_based.py` after the `get_coverage_baseline` function (after line 57), before `start_coverage_baseline_build`:

```python
async def load_coverage_baseline_async() -> dict[tuple[float, float], dict[str, Any]]:
    """Load pre-computed coverage baseline from the coverage_baseline table.

    Returns an empty dict if the table is empty or doesn't exist.
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(
                "SELECT lat_cell, lon_cell, median_rssi, reports_per_hour, "
                "temporal_coverage, is_coverage_hole FROM coverage_baseline"
            ))
            rows = result.fetchall()
    except Exception as exc:
        log.warning("Failed to load coverage_baseline table: %s", exc)
        return {}

    baseline: dict[tuple[float, float], dict[str, Any]] = {}
    for row in rows:
        lat_cell, lon_cell, median_rssi, reports_per_hour, temporal_coverage, is_coverage_hole = row
        baseline[(float(lat_cell), float(lon_cell))] = {
            "median_rssi": float(median_rssi) if median_rssi is not None else None,
            "reports_per_hour": float(reports_per_hour) if reports_per_hour is not None else None,
            "temporal_coverage": float(temporal_coverage) if temporal_coverage is not None else None,
            "is_coverage_hole": bool(is_coverage_hole),
        }

    return baseline
```

Note: No logging here — the caller (`start_coverage_baseline_build`) handles timing and logging to avoid duplicate log lines.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_signal_rule_based.py::TestLoadCoverageBaseline -v`

Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/signal/rule_based.py backend/tests/test_signal_rule_based.py
git commit -m "feat: add load_coverage_baseline_async to read from DB table"
```

### Task 3: Update startup to load from DB with compute fallback

**Files:**
- Modify: `backend/app/signal/rule_based.py:60-74` (`start_coverage_baseline_build`)

- [ ] **Step 1: Write failing test for load-then-fallback behavior**

Add to `backend/tests/test_signal_rule_based.py`:

```python
class TestStartCoverageBaselineBuild:

    @pytest.mark.asyncio
    async def test_startup_loads_from_db_when_populated(self):
        """start_coverage_baseline_build loads from DB when table has data."""
        import app.signal.rule_based as rb

        fake_baseline = {(32.0, 34.0): {"median_rssi": -8.0, "reports_per_hour": 45.0, "temporal_coverage": 0.85, "is_coverage_hole": False}}

        with patch.object(rb, "load_coverage_baseline_async", AsyncMock(return_value=fake_baseline)):
            with patch.object(rb, "build_coverage_baseline_async", AsyncMock()) as mock_build:
                rb._baseline_cache = None
                await rb.start_coverage_baseline_build()

                assert rb._baseline_cache == fake_baseline
                mock_build.assert_not_called()

    @pytest.mark.asyncio
    async def test_startup_falls_back_to_compute_when_empty(self):
        """start_coverage_baseline_build computes when DB table is empty."""
        import app.signal.rule_based as rb

        computed_baseline = {(33.0, 35.0): {"median_rssi": -5.0, "reports_per_hour": 60.0, "temporal_coverage": 0.9, "is_coverage_hole": False}}

        with patch.object(rb, "load_coverage_baseline_async", AsyncMock(return_value={})):
            with patch.object(rb, "build_coverage_baseline_async", AsyncMock(return_value=computed_baseline)) as mock_build:
                rb._baseline_cache = None
                await rb.start_coverage_baseline_build()

                assert rb._baseline_cache == computed_baseline
                mock_build.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_signal_rule_based.py::TestStartCoverageBaselineBuild -v`

Expected: FAIL (current implementation always computes, never loads)

- [ ] **Step 3: Update `start_coverage_baseline_build` to load-then-fallback**

Replace the `start_coverage_baseline_build` function (lines 60-74) in `backend/app/signal/rule_based.py` with:

```python
async def start_coverage_baseline_build() -> None:
    """Load or build the coverage baseline and cache it in memory.

    Called from the lifespan hook in main.py via asyncio.create_task().
    First tries to load from the coverage_baseline DB table (fast).
    Falls back to computing from the positions table if the table is empty.
    """
    global _baseline_cache
    t0 = time.monotonic()
    try:
        _baseline_cache = await load_coverage_baseline_async()
        if _baseline_cache:
            elapsed = time.monotonic() - t0
            log.info("Coverage baseline loaded from DB: %d cells in %.1fs", len(_baseline_cache), elapsed)
            return

        log.info("coverage_baseline table empty — computing from positions...")
        _baseline_cache = await build_coverage_baseline_async(lookback_days=2)
        elapsed = time.monotonic() - t0
        log.info("Coverage baseline computed: %d cells in %.1fs", len(_baseline_cache), elapsed)
    except Exception as exc:
        log.warning("Coverage baseline build failed: %s", exc)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_signal_rule_based.py::TestStartCoverageBaselineBuild -v`

Expected: PASS (both tests)

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd backend && uv run pytest tests/test_signal_rule_based.py -v`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/signal/rule_based.py backend/tests/test_signal_rule_based.py
git commit -m "feat: load coverage baseline from DB at startup, fallback to compute"
```

### Task 4: Update public API docstring

**Files:**
- Modify: `backend/app/signal/rule_based.py:1-15`

- [ ] **Step 1: Update module docstring to reflect new function**

In the module docstring at the top of `backend/app/signal/rule_based.py`, add `load_coverage_baseline_async()` to the public API list:

```python
"""Rule-based GPS anomaly detection — async module for SignalHealthAnalyzerCube.

Public API:
  get_coverage_baseline() -> dict                       (startup-loaded, no TTL)
  load_coverage_baseline_async() -> dict                (reads from coverage_baseline table)
  start_coverage_baseline_build() -> None               (load from DB, fallback to compute)
  ...
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/signal/rule_based.py
git commit -m "docs: update rule_based.py public API docstring"
```
