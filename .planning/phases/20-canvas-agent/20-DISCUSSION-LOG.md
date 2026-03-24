# Phase 20: Canvas Agent - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-24
**Phase:** 20-canvas-agent
**Areas discussed:** Chat panel layout, Mode switching UX, Diff preview & apply, Agent tools & context

---

## Chat Panel Layout

### Panel Position

| Option | Description | Selected |
|--------|-------------|----------|
| Right sidebar | Collapsible panel on right edge, CubeCatalog left, chat right, canvas centered ~320px | ✓ |
| Overlay drawer (right) | Slides over canvas from right, canvas stays full-width underneath | |
| Bottom panel | Same zone as IssuesPanel/ResultsDrawer, terminal-like chat at bottom | |

**User's choice:** Right sidebar
**Notes:** None

### Toggle Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Toolbar button | Chat icon in Toolbar, click toggles panel | |
| Keyboard shortcut only | Toggle with hotkey, no visible button | |
| Both button + shortcut | Toolbar button + Ctrl+Shift+A for power users | ✓ |

**User's choice:** Both button + shortcut
**Notes:** None

### Resize

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed width (~320px) | Simpler, consistent size, no drag handle | |
| Resizable with drag handle | User can drag left edge to resize | ✓ |

**User's choice:** Resizable with drag handle
**Notes:** None

### Coexistence with CubeCatalog

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, both open | Canvas shrinks between both sidebars | ✓ |
| Mutually exclusive | Opening one auto-closes the other | |
| You decide | Claude's discretion | |

**User's choice:** Yes, both open simultaneously
**Notes:** None

---

## Mode Switching UX

### Mode Switcher Design

| Option | Description | Selected |
|--------|-------------|----------|
| Segmented control in panel header | Three-segment toggle: Optimize / Fix / General, always visible | ✓ |
| Dropdown in header | Single dropdown showing current mode | |
| Auto-detect only | No manual switcher, auto-detect based on context | |

**User's choice:** Segmented control in panel header
**Notes:** None

### Auto-Fix Activation

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, auto-switch | Auto-switch to Fix mode when errors occur (if panel open) | |
| No, manual only | User must manually select Fix mode | |
| Auto-open panel in Fix mode | If panel closed and errors occur, auto-open in Fix mode | ✓ |

**User's choice:** Auto-open panel in Fix mode (most proactive)
**Notes:** None

### History on Mode Switch

| Option | Description | Selected |
|--------|-------------|----------|
| Shared history | One continuous conversation, mode changes system prompt only | ✓ |
| Separate history per mode | Each mode has its own conversation thread | |
| Clear on switch | Switching modes resets the conversation | |

**User's choice:** Shared history
**Notes:** None

---

## Diff Preview & Apply

### Diff Presentation Format

| Option | Description | Selected |
|--------|-------------|----------|
| Inline text summary | Agent describes changes in chat with structured list + Apply/Reject buttons | ✓ |
| Visual canvas preview | Ghost nodes on canvas (semi-transparent new, red-dashed removed) | |
| Side-by-side diff | Split canvas view: current state vs proposed state | |

**User's choice:** Inline text summary
**Notes:** None

### Undo/Discard After Apply

| Option | Description | Selected |
|--------|-------------|----------|
| Reload last saved | Discard button reloads workflow from server | |
| Zustand undo via pushSnapshot | Ctrl+Z reverts via undo history | |
| Both options available | pushSnapshot for Ctrl+Z + Discard button for server reload | ✓ |

**User's choice:** Both options available (belt and suspenders)
**Notes:** None

### Diff Batching

| Option | Description | Selected |
|--------|-------------|----------|
| One diff at a time | Agent proposes one set of changes, user accepts/rejects, then another | ✓ |
| Multiple queued diffs | Agent can propose several changes in one response | |
| You decide | Claude's discretion | |

**User's choice:** One diff at a time
**Notes:** None

---

## Agent Tools & Context

### Available Tools

| Option | Description | Selected |
|--------|-------------|----------|
| read_workflow_graph | Returns current canvas state (nodes, edges, params) | ✓ |
| propose_graph_diff | Structured diff output with Apply/Reject in chat | ✓ |
| read_execution_errors | Error messages from last workflow run | ✓ |
| read_execution_results | Summarized results from last run (capped at store limit) | ✓ |

**User's choice:** All four tools selected
**Notes:** User emphasized that read_execution_results should make clear to the user that results are capped at the store limit (max ~100 results shown to agent)

### Context Per Turn

| Option | Description | Selected |
|--------|-------------|----------|
| Graph summary on first turn only | Compact summary at conversation start, tools for updates | |
| Full graph every turn | Serialize entire WorkflowGraph in every request | ✓ |
| No auto-context, tools only | Agent must call read_workflow_graph explicitly | |

**User's choice:** Full graph every turn
**Notes:** None

### Param Edit Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Both structural + param edits | propose_graph_diff can add/remove nodes+edges AND update parameter values | ✓ |
| Structural only | Only add/remove nodes and edges, params must be manual | |
| You decide | Claude's discretion | |

**User's choice:** Both structural + param edits
**Notes:** None

---

## Claude's Discretion

- Chat panel CSS animation and styling details
- Drag handle resize implementation
- SSE event rendering in chat messages
- `propose_graph_diff` JSON schema structure
- Fix mode auto-open initial prompt generation approach
- Chat input component design
- Message bubble styling

## Deferred Ideas

None — discussion stayed within phase scope
