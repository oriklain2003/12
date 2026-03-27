---
phase: 20
slug: canvas-agent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend); no frontend test framework |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && uv run pytest tests/test_canvas_agent.py -x` |
| **Full suite command** | `cd backend && uv run pytest` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/test_canvas_agent.py -x`
- **After every plan wave:** Run `cd backend && uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 20-01-01 | 01 | 1 | CANVAS-03 | unit | `uv run pytest tests/test_canvas_agent.py::TestCanvasTools::test_read_workflow_graph -x` | W0 | pending |
| 20-01-02 | 01 | 1 | CANVAS-05 | unit | `uv run pytest tests/test_canvas_agent.py::TestCanvasTools::test_read_execution_errors -x` | W0 | pending |
| 20-01-03 | 01 | 1 | CANVAS-05 | unit | `uv run pytest tests/test_canvas_agent.py::TestCanvasTools::test_read_execution_results -x` | W0 | pending |
| 20-01-04 | 01 | 1 | CANVAS-07 | unit | `uv run pytest tests/test_canvas_agent.py::TestCanvasDiff::test_propose_graph_diff_schema -x` | W0 | pending |
| 20-02-01 | 02 | 2 | CANVAS-07 | manual | Manual: apply diff, verify nodes+edges render atomically | N/A | pending |
| 20-02-02 | 02 | 2 | CANVAS-07 | manual | Manual: apply diff, Ctrl+Z, verify undo restores pre-diff state | N/A | pending |
| 20-03-01 | 03 | 3 | CANVAS-01 | manual | Manual: open editor, toggle panel, verify sidebar layout | N/A | pending |
| 20-03-02 | 03 | 3 | CANVAS-02 | manual | Manual: switch modes, verify badge changes | N/A | pending |
| 20-03-03 | 03 | 3 | CANVAS-04 | manual | Manual: send optimize message, verify relevant suggestion | N/A | pending |
| 20-03-04 | 03 | 3 | CANVAS-05 | manual | Manual: run workflow with errors, verify auto-open Fix mode | N/A | pending |
| 20-03-05 | 03 | 3 | CANVAS-06 | manual | Manual: send general message, verify agent responds | N/A | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_canvas_agent.py` — stubs for CANVAS-03, CANVAS-05, CANVAS-07 (backend tools + diff schema)
- [ ] Fixtures: `make_workflow_graph()` helper (serialized graph dict), `make_execution_errors()` helper, `make_execution_results()` helper

*Existing infrastructure covers pytest framework — no new install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Chat panel opens/closes as sidebar | CANVAS-01 | Visual layout verification | Open editor, click chat icon in toolbar, verify panel appears on right without covering canvas |
| Mode toggle switches active segment | CANVAS-02 | Visual UI interaction | Click each mode segment, verify accent color moves to selected |
| Optimize suggestion is workflow-specific | CANVAS-04 | Requires Gemini response evaluation | Load workflow with redundant filter, send "optimize this", verify suggestion references actual cubes |
| Auto-open Fix mode on execution error | CANVAS-05 | Requires full execution flow | Run workflow with intentionally broken cube, verify panel auto-opens in Fix mode with diagnostic prompt |
| General mode answers questions | CANVAS-06 | Requires Gemini response evaluation | Send "what cubes can filter by date?", verify relevant response |
| Atomic diff application | CANVAS-07 | Visual canvas state verification | Apply a diff that adds nodes+edges, verify all appear simultaneously |
| Undo restores pre-agent state | CANVAS-07 | Visual canvas state verification | Apply diff, press Ctrl+Z, verify canvas matches pre-diff state exactly |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
