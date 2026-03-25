---
phase: 21-build-wizard-agent
plan: "02"
subsystem: frontend-wizard
tags: [wizard, frontend, react, sse-streaming, svg, option-cards, mini-graph]
dependency_graph:
  requires: [21-01]
  provides: [wizard-page, wizard-components, build-agent-frontend]
  affects: [dashboard, routing]
tech_stack:
  added: []
  patterns: [sse-streaming, local-useState-not-zustand, svg-topological-layout, inline-tool-result-rendering]
key_files:
  created:
    - frontend/src/types/wizard.ts
    - frontend/src/pages/WizardPage.tsx
    - frontend/src/pages/WizardPage.css
    - frontend/src/components/Wizard/WizardChat.tsx
    - frontend/src/components/Wizard/WizardChat.css
    - frontend/src/components/Wizard/WizardWelcome.tsx
    - frontend/src/components/Wizard/WizardWelcome.css
    - frontend/src/components/Wizard/WizardInput.tsx
    - frontend/src/components/Wizard/WizardInput.css
    - frontend/src/components/Wizard/OptionCards.tsx
    - frontend/src/components/Wizard/OptionCards.css
    - frontend/src/components/Wizard/MiniGraph.tsx
    - frontend/src/components/Wizard/MiniGraph.css
  modified:
    - frontend/src/api/agent.ts
    - frontend/src/pages/DashboardPage.tsx
    - frontend/src/main.tsx
decisions:
  - "WizardChatMessage extends ChatMessage with toolData field for structured tool results — kept in wizard.ts rather than polluting shared agent.ts types"
  - "Dashboard single New Workflow button split into Build with Wizard (accent) + Blank Canvas (glass) per UI-SPEC D-02"
  - "MiniGraph uses BFS topological depth calculation with COL_GAP=160px/ROW_GAP=64px; label truncated in TSX (not CSS) to work in SVG context"
  - "WizardPage uses useState (not Zustand) — wizard has isolated session state that does not interact with canvas flowStore"
  - "handleBuildWorkflow and handleAdjustPlan send natural language messages to build_agent, letting the LLM interpret them rather than hardcoded tool calls"
metrics:
  duration: "~10 minutes"
  completed: "2026-03-25"
  tasks_completed: 2
  tasks_total: 2
  files_created: 13
  files_modified: 3
---

# Phase 21 Plan 02: Complete Wizard Frontend Summary

Full-screen conversational wizard UI with SSE streaming to build_agent, inline OptionCards from present_options tool, SVG MiniGraph preview from show_intent_preview tool, and automatic redirect to canvas after generate_workflow succeeds.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create wizard types and extend API client with persona parameter | f8970bc | wizard.ts (created), agent.ts (updated) |
| 2 | Build WizardPage shell, WizardChat, WizardWelcome, WizardInput, OptionCards, MiniGraph | dfa7a9b | 13 created, 3 modified |

## What Was Built

### wizard.ts

TypeScript types for all three build_agent tool result shapes:
- `WizardOption`, `WizardOptionsData` — present_options tool result
- `IntentPreviewNode`, `IntentPreviewConnection`, `IntentPreviewData` — show_intent_preview tool result
- `GenerateWorkflowResult` — generate_workflow tool result with status discriminant
- `WizardChatMessage` — local chat message type extending ChatMessage with `toolData?: unknown` for structured tool results

### agent.ts

Added `persona: string = 'canvas_agent'` as 8th parameter to `streamAgentChat`. All existing callers (ChatInput.tsx) continue working without changes — default preserves backward compatibility. WizardPage passes `'build_agent'`.

### WizardPage.tsx

Full-screen `/wizard` page shell:
- Local `useState` for messages, sessionId, isStreaming (no Zustand — isolated from canvas state)
- SSE streaming loop handles: `session` (capture sessionId), `text` (append to streaming message), `thinking` (inline indicator), `tool_call` (ToolCallIndicator), `tool_result` (routes by name: options → OptionCards, preview → MiniGraph, generate_workflow → redirect or error), `done`/`error`
- After `generate_workflow` success: Sonner toast "Workflow created — loading canvas...", then `navigate('/workflow/:id')` after 800ms
- WizardHeader: 52px glass bar with brand logo + "Back to Workflows" button
- Dashboard updated: "New Workflow" replaced by "Build with Wizard" (accent) + "Blank Canvas" (glass) button row

### WizardWelcome.tsx

Initial state component shown when message list is empty:
- Heading "What do you want to analyze?" (24px weight 600)
- Subheading "Describe your idea or pick a starting point below." (16px weight 600, secondary color)
- 2-column grid of 6 mission cards: Squawk Analysis, Geographic Monitoring, Signal Health Check, Flight Tracking, Anomaly Detection, General Exploration
- Clicking a card sends "I want to do: {title} — {description}" as the first message

### WizardInput.tsx

Text input at chat bottom:
- Auto-expanding textarea (up to 5 lines), Enter to send, Shift+Enter for newline
- Placeholder "Describe your analysis idea..."
- Send button shows pulse dot in accent color while streaming, SVG arrow otherwise
- `readOnly` on textarea while streaming (prevents input during LLM response)

### OptionCards.tsx

Inline option cards from `present_options` tool:
- Single-select: card click immediately calls `onSelect("I selected: {title}")` and dims block
- Multi-select: toggles accent border on cards, shows "Confirm selection" button when ≥1 selected
- Free-text fallback below cards: input placeholder "Or type your own...", "Send Message" button
- Entire block dims to opacity 0.5 with pointer-events disabled after any selection is sent

### MiniGraph.tsx

SVG graph preview from `show_intent_preview` tool:
- BFS topological layout: nodes grouped by depth, x = PADDING + depth × 160px, y = PADDING + index × 64px
- Node rectangles: 120×44px, rx=8, `--color-surface-raised` fill, `rgba(255,255,255,0.12)` stroke
- Connection lines: `<line>` elements with SVG `<marker>` arrowhead, `rgba(255,255,255,0.25)` stroke
- Mission name (16px weight 600) + description (13px secondary) below SVG
- "Adjust Plan" (glass-btn) and "Build This" (glass-btn--accent) buttons; after Build clicked: "Building..." with pulse dot, both buttons disabled

### WizardChat.tsx

Scrollable chat column (max-width 720px, centered):
- Routes messages to MessageBubble, ToolCallIndicator, OptionCards, MiniGraph, or error block by `msg.type`
- Validation error block: red left-border, dimmed background, "Retry Generation" button sends "Please try again"
- Auto-scrolls to bottom on every new message via `useEffect` + `scrollIntoView`

## Deviations from Plan

None — plan executed exactly as written. One additional change made per UI-SPEC (not breaking any plan task):
- Dashboard "New Workflow" button replaced by "Build with Wizard" + "Blank Canvas" per UI-SPEC D-02, which was referenced by the plan's objective but not explicitly listed as a task file. Applied as part of completing the wizard frontend deliverable.

## Known Stubs

None — all components are fully wired:
- WizardPage streams from real `/api/agent/chat` endpoint with `persona: 'build_agent'`
- OptionCards sends real selections as messages to the agent
- MiniGraph triggers `onBuildWorkflow` which sends a message prompting the agent to call `generate_workflow`
- Redirect after generation uses the real `workflow_id` from the tool result

## Self-Check: PASSED

File existence:
- `frontend/src/types/wizard.ts` — exists
- `frontend/src/pages/WizardPage.tsx` — exists (>100 lines)
- `frontend/src/pages/WizardPage.css` — exists
- `frontend/src/components/Wizard/WizardChat.tsx` — exists
- `frontend/src/components/Wizard/WizardWelcome.tsx` — exists
- `frontend/src/components/Wizard/WizardInput.tsx` — exists
- `frontend/src/components/Wizard/OptionCards.tsx` — exists
- `frontend/src/components/Wizard/OptionCards.css` — exists
- `frontend/src/components/Wizard/MiniGraph.tsx` — exists
- `frontend/src/components/Wizard/MiniGraph.css` — exists

Commits verified: f8970bc and dfa7a9b present in git log.

TypeScript: `npx tsc --noEmit` exits 0 — no errors.
