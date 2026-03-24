---
phase: 20-canvas-agent
plan: "04"
subsystem: frontend + agent-skill
tags: [canvas-agent, chat-panel, toolbar, auto-fix, skill-file]
dependency_graph:
  requires: ["20-02", "20-03"]
  provides: ["chat-panel-wired", "toolbar-chat-toggle", "auto-fix-mode", "canvas-agent-skill"]
  affects: ["EditorPage", "Toolbar", "canvas_agent.md"]
tech_stack:
  added: []
  patterns: ["useRef guard for one-shot useEffect", "Zustand getState() in keyboard handler"]
key_files:
  created: []
  modified:
    - frontend/src/pages/EditorPage.tsx
    - frontend/src/components/Toolbar/Toolbar.tsx
    - frontend/src/components/Toolbar/Toolbar.css
    - backend/app/agents/skills/canvas_agent.md
decisions:
  - "useRef(false) guard prevents auto-open Fix mode from firing more than once per failed run; resets when isRunning flips true"
  - "Keyboard shortcut Ctrl+Shift+A handled before isInputField guard so it works in textareas and inputs"
  - "canvas_agent.md extended to 68 lines with mode-specific behavioral sections for Optimize, Fix, and General"
metrics:
  duration_minutes: 8
  completed_date: "2026-03-24"
  tasks_completed: 2
  tasks_total: 3
  files_modified: 4
---

# Phase 20 Plan 04: EditorPage Wiring and Agent Skill Extension Summary

ChatPanel wired into EditorPage layout with toolbar toggle button (chat bubble SVG, Ctrl+Shift+A shortcut), auto-open Fix mode on execution errors, and comprehensive Canvas Agent skill file with Optimize/Fix/General mode instructions.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wire ChatPanel, toolbar toggle, keyboard shortcut, auto-open Fix mode | 7b4ad4a | EditorPage.tsx, Toolbar.tsx, Toolbar.css |
| 2 | Extend Canvas Agent skill file with mode-specific instructions | 78f8129 | canvas_agent.md |

## Task 3: Checkpoint Reached

**Type:** human-verify
**Status:** Awaiting visual verification of complete Canvas Agent chat panel

### What Was Built

**Task 1 — EditorPage wiring:**
- `ChatPanel` imported and rendered as right sibling of `.app__canvas-area` inside `.app__body`
- Added `isRunning`, `executionStatus`, `setChatPanelOpen`, `setChatPanelMode`, `addChatMessage` selectors
- `autoFixFired` useRef guard: resets to false when `isRunning` goes true, fires once on execution completion with errors
- Auto-open sends Fix mode activation + diagnostic message: "I see errors in N cube(s) from the last run..."

**Task 1 — Toolbar additions:**
- `chatPanelOpen` + `setChatPanelOpen` selectors added
- Chat bubble SVG toggle button with `aria-label="Toggle agent chat panel"`, active dot when panel is open
- `Ctrl+Shift+A` / `Cmd+Shift+A` keyboard shortcut (placed before `isInputField` guard)
- "Agent panel" shortcut row added to the keyboard shortcuts panel

**Task 1 — CSS:**
- `.toolbar__chat-btn { position: relative }`
- `.toolbar__chat-dot` with `var(--color-accent)` background, 6×6px circle, top-right position

**Task 2 — Skill file:**
- 68-line comprehensive Canvas Agent persona in `backend/app/agents/skills/canvas_agent.md`
- 7 tools listed with descriptions (including `read_execution_errors`, `read_execution_results`, `read_workflow_graph`)
- 6 behavioral rules (including "One proposal at a time", "Results are capped")
- Mode-specific sections: Optimize (performance/redundancy), Fix (immediate diagnosis, diff-first), General (discovery/explanation)

## Verification

TypeScript compilation: zero errors (`npx tsc --noEmit` clean pass)

## How To Verify (Task 3 — Human)

1. Start backend: `cd backend && uv run uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && pnpm dev`
3. Open http://localhost:5173/workflow/new

**Test 1 — Panel toggle:** Click chat bubble icon in toolbar (between ? and Save). Verify right sidebar opens with AGENT header. Press Cmd+Shift+A — panel closes. Press again — reopens.

**Test 2 — Mode switching:** Click Optimize/Fix/General segments — each highlights. Switching modes does NOT clear chat messages.

**Test 3 — Chat interaction (requires GEMINI_API_KEY):** In General mode, ask "What cubes are available for filtering flights?" Verify streaming response with tool call indicators.

**Test 4 — Diff proposal:** Add all_flights cube. Ask agent to "Add a squawk filter connected to the flights cube." Verify DiffProposal block appears. Click Apply Changes — node appears on canvas. Ctrl+Z reverts.

**Test 5 — Auto-open Fix mode:** Create workflow with failing cube. Click Run. After failure, verify chat panel auto-opens in Fix mode with "I see errors in N cube(s)..." message. Run again — verify no duplicate message.

**Test 6 — Panel resize:** Hover left edge of panel — cursor becomes col-resize. Drag to resize. Verify min (240px) and max (480px) constraints.

## Deviations from Plan

None — plan executed exactly as written. ChatPanel component was already present from plan 03 (parallel wave 2 execution), confirmed by zero TypeScript errors.

## Known Stubs

None. All wiring connects to existing live components and store actions.

## Self-Check: PASSED

- `frontend/src/pages/EditorPage.tsx` — exists and contains `ChatPanel`, `autoFixFired`, `setChatPanelMode('fix')`, `I see errors in`
- `frontend/src/components/Toolbar/Toolbar.tsx` — contains `Toggle agent chat panel`, `setChatPanelOpen`, `toolbar__chat-btn`, `Agent panel`, `e.key === 'a' || e.key === 'A'`
- `frontend/src/components/Toolbar/Toolbar.css` — contains `toolbar__chat-dot`, `var(--color-accent)`
- `backend/app/agents/skills/canvas_agent.md` — 68 lines, contains `Optimize Mode`, `Fix Mode`, `General Mode`, `One proposal at a time`, `Results are capped`
- Commit 7b4ad4a: feat(20-04): wire ChatPanel...
- Commit 78f8129: feat(20-04): extend canvas_agent.md...
