---
phase: 18
slug: agent-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]` with `asyncio_mode = "auto"`) |
| **Quick run command** | `cd backend && uv run pytest tests/test_agent_*.py -x` |
| **Full suite command** | `cd backend && uv run pytest` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/test_agent_*.py -x`
- **After every plan wave:** Run `cd backend && uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 18-01-01 | 01 | 1 | INFRA-01 | unit | `uv run pytest tests/test_agent_client.py -x` | ❌ W0 | ⬜ pending |
| 18-01-02 | 01 | 1 | INFRA-01 | unit | `uv run pytest tests/test_agent_client.py::test_async_interface -x` | ❌ W0 | ⬜ pending |
| 18-02-01 | 02 | 1 | INFRA-02 | integration | `uv run pytest tests/test_agent_sse.py::test_content_type -x` | ❌ W0 | ⬜ pending |
| 18-02-02 | 02 | 1 | INFRA-02 | integration | `uv run pytest tests/test_agent_sse.py::test_event_types -x` | ❌ W0 | ⬜ pending |
| 18-03-01 | 03 | 1 | INFRA-03 | unit | `uv run pytest tests/test_agent_skills.py::test_all_personas_loaded -x` | ❌ W0 | ⬜ pending |
| 18-03-02 | 03 | 1 | INFRA-04 | unit | `uv run pytest tests/test_agent_skills.py::test_system_brief_prepended -x` | ❌ W0 | ⬜ pending |
| 18-04-01 | 04 | 1 | INFRA-05 | unit | `uv run pytest tests/test_agent_registry.py -x` | ❌ W0 | ⬜ pending |
| 18-04-02 | 04 | 1 | INFRA-05 | unit | `uv run pytest tests/test_agent_dispatcher.py -x` | ❌ W0 | ⬜ pending |
| 18-04-03 | 04 | 1 | INFRA-05 | unit | `uv run pytest tests/test_agent_dispatcher.py::test_tool_failure -x` | ❌ W0 | ⬜ pending |
| 18-05-01 | 05 | 2 | INFRA-06 | unit | `uv run pytest tests/test_agent_context.py::test_prune_threshold -x` | ❌ W0 | ⬜ pending |
| 18-05-02 | 05 | 2 | INFRA-06 | unit | `uv run pytest tests/test_agent_context.py::test_prune_order -x` | ❌ W0 | ⬜ pending |
| 18-06-01 | 06 | 2 | INFRA-07 | integration | `uv run pytest tests/test_agent_mission.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_agent_client.py` — stubs for INFRA-01 (client init, async interface)
- [ ] `backend/tests/test_agent_sse.py` — stubs for INFRA-02 (SSE endpoint, typed events)
- [ ] `backend/tests/test_agent_skills.py` — stubs for INFRA-03, INFRA-04 (skill loading, system brief)
- [ ] `backend/tests/test_agent_registry.py` — stubs for INFRA-05 (decorator registration)
- [ ] `backend/tests/test_agent_dispatcher.py` — stubs for INFRA-05 (dispatch loop, failure handling)
- [ ] `backend/tests/test_agent_context.py` — stubs for INFRA-06 (pruning logic)
- [ ] `backend/tests/test_agent_mission.py` — stubs for INFRA-07 (mission persistence)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SSE streaming renders typed events in browser | INFRA-02 | Requires browser SSE client | Open `/api/agent/chat` with EventSource, verify `text`, `tool_call`, `tool_result`, `done` events render |
| Agent chat does not block workflow execution | INFRA-02 | Concurrent connection test | Run agent chat and workflow execution simultaneously, verify both complete |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
