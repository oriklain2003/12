# Phase 21: Build Wizard Agent - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-25
**Phase:** 21-build-wizard-agent
**Areas discussed:** Wizard page & navigation, Step flow & option cards, Intent preview UX, Generation & delivery

---

## Wizard Page & Navigation

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated /wizard route | New WizardPage at /wizard — full-screen focused experience. Dashboard 'New Workflow' button routes here instead of /workflow/new. | |
| Modal overlay on Dashboard | Wizard opens as full-screen modal over dashboard. No route change. | |
| Embedded in EditorPage | Wizard appears inside the editor when /workflow/new is accessed. | |

**User's choice:** Dedicated /wizard route
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — skip link on wizard page | Small 'Skip to blank canvas' link at top of wizard. | |
| Yes — choice on Dashboard | Dashboard shows two buttons: 'Build with Wizard' and 'Blank Canvas'. | |
| No — wizard is the only path | All new workflows go through the wizard. | |

**User's choice:** Yes — choice on Dashboard
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| Save + redirect to /workflow/:id | Wizard creates the workflow via API, then navigates to the editor with saved workflow loaded. | |
| Load onto /workflow/new unsaved | Generated graph loaded into unsaved editor session. | |

**User's choice:** Save + redirect to /workflow/:id
**Notes:** None

---

## Step Flow & Option Cards

| Option | Description | Selected |
|--------|-------------|----------|
| 4 fixed steps | Mission, Data Source, Filters, Review/Preview. Fixed sequence with back/next. | |
| 3 steps (compact) | Mission + Data Source combined, Filters, Review. | |
| Dynamic steps from LLM | Gemini decides how many steps based on mission. | |

**User's choice:** Dynamic steps from LLM
**Notes:** "We can have steps, like mission type, and preferred data sources, but the idea here is to have the user enter an idea they have and then chat with the LLM and answer questions to get to the best workflow for that idea. In the process itself the LLM can use tools to present options to the user and plan ideas and he can click an option and also the LLM can ask for multiple answers."

---

| Option | Description | Selected |
|--------|-------------|----------|
| Free text input first | Analyst types their analysis idea. LLM interprets and starts asking clarifying questions. | |
| Mission type cards first, then chat | Start with broad category cards to anchor the conversation. | |
| Either — input field + suggested cards | Show both: text input for typing AND suggested mission type cards below. | |

**User's choice:** Either — input field + suggested cards
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| Tool-rendered cards in chat | LLM calls `present_options` tool that renders clickable cards inline. Clicking sends selection as message. | |
| Numbered list in text | LLM outputs options as numbered list. User types number. | |
| Side panel with options | Options appear in separate panel alongside chat. | |

**User's choice:** Tool-rendered cards in chat
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — LLM controls single vs multi | `present_options` tool has `multi_select` flag. LLM decides per question. | |
| Single-select only | Every card set is pick-one. | |

**User's choice:** Yes — LLM controls single vs multi
**Notes:** None

---

**Additional note from user:** "On each question the agent asks, have the user also have the option to enter free text."

---

## Intent Preview UX

| Option | Description | Selected |
|--------|-------------|----------|
| Summary card in chat | Structured summary inline in chat: mission, pipeline, parameters. Apply/Edit buttons. | |
| Visual mini-graph preview | Simplified node graph preview showing cube connections. More visual. | |
| Text-only summary | Plain text listing cubes and connections. | |

**User's choice:** Visual mini-graph preview
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| Continue chatting | Clicking 'Adjust' sends message, conversation continues. LLM asks what to change. | |
| Restart wizard | Goes back to beginning. | |
| You decide | Claude's discretion. | |

**User's choice:** Continue chatting
**Notes:** None

---

## Generation & Delivery

| Option | Description | Selected |
|--------|-------------|----------|
| LLM generates graph JSON via tool | LLM calls `generate_workflow` tool. Backend validates, saves, returns ID. Frontend redirects. | |
| Backend-only generation (no LLM) | Python function builds graph from collected choices. Deterministic. | |
| LLM generates + human edits before save | LLM generates, analyst edits parameters in preview before saving. | |

**User's choice:** LLM generates graph JSON via tool
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| LLM auto-fixes and retries | Validation errors fed back to LLM. Auto-adjusts and retries (up to 2 attempts). | |
| Show errors to analyst immediately | Display validation errors in chat. No automatic retry. | |
| You decide | Claude's discretion. | |

**User's choice:** LLM auto-fixes and retries
**Notes:** None

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — LLM generates name | `generate_workflow` includes name from mission. e.g., "Squawk 7700 in Jordan FIR". | |
| Yes — but ask analyst to confirm | LLM suggests name in preview, analyst can edit before building. | |
| No — default 'Untitled Workflow' | Use existing default naming. | |

**User's choice:** Yes — LLM generates name
**Notes:** None

---

## Claude's Discretion

- Wizard page layout and styling
- Chat UI component reuse strategy (Phase 20 components vs. new)
- `present_options` tool schema structure
- Mini-graph preview component implementation
- How the LLM determines when to show a preview
- Build Agent skill file content
- Node positioning algorithm for generated graph

## Deferred Ideas

None — discussion stayed within phase scope
