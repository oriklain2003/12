---
phase: 20-canvas-agent
plan: "03"
subsystem: frontend/chat-ui
tags: [react, zustand, sse, chat, canvas-agent]
dependency_graph:
  requires: [20-02]
  provides: [ChatPanel, ModeToggle, MessageList, MessageBubble, DiffProposal, ChatInput, ToolCallIndicator]
  affects: []
tech_stack:
  added: []
  patterns: [zustand-getState-in-async, sse-async-generator, css-pseudo-element-streaming-cursor]
key_files:
  created:
    - frontend/src/components/Chat/ChatPanel.tsx
    - frontend/src/components/Chat/ChatPanel.css
    - frontend/src/components/Chat/ModeToggle.tsx
    - frontend/src/components/Chat/ToolCallIndicator.tsx
    - frontend/src/components/Chat/MessageList.tsx
    - frontend/src/components/Chat/MessageBubble.tsx
    - frontend/src/components/Chat/DiffProposal.tsx
    - frontend/src/components/Chat/ChatInput.tsx
  modified: []
decisions:
  - "DiffProposal does not take messageId prop — prop was unneeded since component manages its own applied/rejected state locally"
  - "ChatInput uses useFlowStore.getState() inside async handleSend to avoid stale closure issues with streaming loop"
  - "All streaming state mutations in the done/tool_result handlers use useFlowStore.setState directly for atomic array update without triggering extra re-renders"
metrics:
  duration_minutes: 25
  completed_date: "2026-03-25"
  tasks_completed: 2
  tasks_total: 2
  files_created: 8
  files_modified: 0
---

# Phase 20 Plan 03: Chat UI Components Summary

Eight React components for the Canvas Agent chat panel: resizable right sidebar shell with drag handle, three-segment mode toggle (Optimize/Fix/General), scrollable message thread, user/agent message bubbles with streaming cursor, structured diff proposal with Apply/Reject, textarea chat input with full SSE send flow, and tool call indicator with spinner.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | ChatPanel shell, CSS, ModeToggle, ToolCallIndicator | f01bb3f | ChatPanel.tsx, ChatPanel.css, ModeToggle.tsx, ToolCallIndicator.tsx |
| 2 | MessageList, MessageBubble, DiffProposal, ChatInput | b19d3e5 | MessageList.tsx, MessageBubble.tsx, DiffProposal.tsx, ChatInput.tsx |

## What Was Built

**Task 1 — Panel shell and primitive components:**

- `ChatPanel.tsx`: Right sidebar with `useState` width (default 320px, min 240, max 480), `mousedown/mousemove/mouseup` drag-resize via document event listeners, animated left-edge gradient line (CSS `::after` mirroring `sidebar::after`), 44px header with "AGENT" title, ModeToggle, close button, and body slot containing MessageList + ChatInput.
- `ChatPanel.css`: Complete stylesheet for all Chat components — panel layout, drag handle, header, all message bubble variants, diff proposal block, chat input row. Uses only existing CSS custom properties.
- `ModeToggle.tsx`: Three-segment toggle reading `chatPanelMode` and `setChatPanelMode` from flowStore. Fix segment shows 4px error dot when `executionStatus` has any `status === 'error'`. Does NOT call `clearChat` on mode switch (per D-07).
- `ToolCallIndicator.tsx`: Inline spinner row with `stroke-dasharray="14 8"` circle SVG rotated via CSS `@keyframes spinner-rotate`. Maps 6 known tool names to human-readable labels.

**Task 2 — Message rendering and send flow:**

- `MessageList.tsx`: Reads `chatMessages` from store, auto-scrolls via `containerRef.scrollTop = scrollHeight` in `useEffect` on `chatMessages.length`. Routes each message to `ToolCallIndicator` (type=tool_call), `MessageBubble + DiffProposal` (has diff), or plain `MessageBubble`. Empty state with mode-specific body copy.
- `MessageBubble.tsx`: Conditional class `message-bubble--user` or `message-bubble--agent` (with `--streaming` modifier for blinking cursor). Renders `message.content` as plain text with `white-space: pre-wrap`.
- `DiffProposal.tsx`: Iterates `diff.add_nodes`, `remove_node_ids`, `update_params`, `add_edges`, `remove_edge_ids`. Badge variants: `+` (green), `−` (red), `~` (orange). Local `applied`/`rejected` state — after Apply shows "Applied" label; after Reject removes block. Calls `applyAgentDiff` and `toast.success('Changes applied to canvas')`.
- `ChatInput.tsx`: Full SSE send flow — serializes graph via `serializeGraph`, builds errors from `executionStatus`, calls `streamAgentChat` async generator. Handles `session`, `text`, `tool_call`, `tool_result` (extracts `proposed_diff`), and `done` events. Captures session ID from first SSE event. Enter sends, Shift+Enter inserts newline. Auto-grows textarea up to `max-height: 120px`.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Minor Scope Adjustments

**1. [Rule 1 - Bug] Removed unused `messageId` prop from DiffProposal**
- Found during: Task 2 implementation review
- Issue: `messageId` was added to DiffProposal props but never used in JSX or logic, causing `noUnusedParameters` TypeScript error
- Fix: Removed `messageId` from DiffProposal props and call site in MessageList
- Files modified: DiffProposal.tsx, MessageList.tsx

## Known Stubs

None — all components are fully wired to store state and the SSE API client from Plan 02. The components are not yet mounted in EditorPage (that is Plan 04's responsibility).

## Verification

- `cd frontend && npx tsc --noEmit` — zero TypeScript errors (confirmed)
- All 8 files created in `frontend/src/components/Chat/`
- ChatPanel reads `chatPanelOpen` and renders nothing when false
- ModeToggle switches modes without clearing chat
- DiffProposal `Apply Changes` calls `applyAgentDiff`
- ChatInput `streamAgentChat` integration with session capture and `proposed_diff` detection

## Self-Check: PASSED

Files verified:
- frontend/src/components/Chat/ChatPanel.tsx — FOUND
- frontend/src/components/Chat/ChatPanel.css — FOUND
- frontend/src/components/Chat/ModeToggle.tsx — FOUND
- frontend/src/components/Chat/ToolCallIndicator.tsx — FOUND
- frontend/src/components/Chat/MessageList.tsx — FOUND
- frontend/src/components/Chat/MessageBubble.tsx — FOUND
- frontend/src/components/Chat/DiffProposal.tsx — FOUND
- frontend/src/components/Chat/ChatInput.tsx — FOUND

Commits verified:
- f01bb3f (Task 1) — FOUND
- b19d3e5 (Task 2) — FOUND
