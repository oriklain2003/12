---
phase: 22
slug: results-interpreter
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) / manual browser (frontend) |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && uv run pytest tests/ -x -q --timeout=30` |
| **Full suite command** | `cd backend && uv run pytest tests/ -q --timeout=60` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/ -x -q --timeout=30`
- **After every plan wave:** Run `cd backend && uv run pytest tests/ -q --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | RESULT-01 | integration | `cd backend && uv run pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | RESULT-02 | integration | `cd backend && uv run pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | RESULT-03 | integration | `cd backend && uv run pytest tests/ -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Test stubs for RESULT-01 (interpret button trigger + SSE endpoint)
- [ ] Test stubs for RESULT-02 (mission-context interpretation)
- [ ] Test stubs for RESULT-03 (fallback cube-type-aware framing)

*Existing test infrastructure (pytest + conftest) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SSE streaming renders token-by-token in browser | RESULT-01 | Requires visual browser verification | Open ResultsDrawer, click Interpret, verify streaming text appears |
| Interpretation panel collapses/expands smoothly | RESULT-01 | CSS animation verification | Click collapse/expand toggle, verify smooth transition |
| Follow-up agent conversation flows naturally | RESULT-01 | Conversational quality check | Click "Discuss results", ask follow-up questions, verify coherent responses |

*Frontend components require manual browser verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
