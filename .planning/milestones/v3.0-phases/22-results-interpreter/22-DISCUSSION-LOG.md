# Phase 22: Results Interpreter - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-26
**Phase:** 22-results-interpreter
**Areas discussed:** Trigger & placement, Interpretation display, Mission context depth, Scope of analysis

---

## Trigger & Placement

| Option | Description | Selected |
|--------|-------------|----------|
| ResultsDrawer header | Button next to Close in the existing results drawer header. Contextual — only visible when results are showing. | :heavy_check_mark: |
| Per-cube badge on canvas | Small 'Interpret' icon on each cube node after execution. | |
| Toolbar action button | A new button in the editor Toolbar (next to Run/Save/Chat). | |

**User's choice:** ResultsDrawer header
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Manual only | Analyst clicks 'Interpret Results' when they want it. No auto Gemini call. | :heavy_check_mark: |
| Auto-suggest after run | Show a subtle prompt after successful execution. | |
| Auto-interpret after run | Automatically call the interpreter after every execution. | |

**User's choice:** Manual only
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Current cube | Interprets the results of whichever cube is selected in the drawer. | :heavy_check_mark: |
| Whole workflow | Sends all cube results for a holistic summary. | |
| Current cube + pipeline context | Interprets selected cube with upstream awareness. | |

**User's choice:** Current cube
**Notes:** None

---

## Interpretation Display

| Option | Description | Selected |
|--------|-------------|----------|
| Inline panel in drawer | Collapsible section inside ResultsDrawer, above the table. | :heavy_check_mark: |
| Canvas Agent chat panel | Reuse the right-sidebar chat panel from Phase 20. | |
| Modal overlay | Centered modal over the results drawer. | |

**User's choice:** Inline panel in drawer
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Stream tokens | Text appears progressively via SSE. | :heavy_check_mark: |
| One-shot render | Wait for full response, then display all at once. | |

**User's choice:** Stream tokens
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| One-shot, no follow-ups | Click Interpret → see interpretation → done. | |
| Inline follow-ups | Small input field below interpretation for follow-up questions. | |

**User's choice:** Other — dedicated follow-up agent
**Notes:** User wants follow-up capability but via a separate dedicated agent that can tool-call to fetch specific cube results, not inline in the drawer or via the Canvas Agent.

| Option | Description | Selected |
|--------|-------------|----------|
| Canvas Agent chat | 'Discuss results' link opens Canvas Agent with interpretation pre-loaded. | |
| Dedicated follow-up agent | New lightweight agent for results Q&A with tool-calling access. | :heavy_check_mark: |
| Same Results Interpreter, new session | Mini-chat in drawer using results_interpreter persona. | |

**User's choice:** Dedicated follow-up agent
**Notes:** User wants a dedicated agent because it should get the summary and then be able to call tools to fetch specific cube results to answer questions.

---

## Mission Context Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Reference + compare | Name mission intent AND compare results against it. | :heavy_check_mark: |
| Light reference only | Mention mission in opening sentence, then describe generically. | |
| Deep expectation matching | Infer what analyst expected and call out surprises. | |

**User's choice:** Reference + compare
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Flight-analysis framing | Use domain knowledge for generic flight-analysis framing. | |
| Statistical summary | Pure data summary — row counts, distributions, ranges. | |
| Cube-type-aware framing | Tailor framing based on which cube produced the results. | :heavy_check_mark: |

**User's choice:** Cube-type-aware framing
**Notes:** None

---

## Scope of Analysis

| Option | Description | Selected |
|--------|-------------|----------|
| Include pipeline summary | Current cube's results plus upstream path summary. | :heavy_check_mark: |
| Current cube only | Only the selected cube's results and definition. | |
| Full workflow graph | Entire workflow graph + all cube results. | |

**User's choice:** Include pipeline summary
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Key findings (bullets) | 3-5 bullet-point findings highlighting notable patterns. | |
| Narrative summary | Flowing paragraph(s) summarizing results in context. | :heavy_check_mark: |
| Structured report | Formatted report with Overview, Key Findings, etc. | |

**User's choice:** Narrative summary only
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Explain why empty | Interpreter explains possible reasons for 0 rows with actionable guidance. | :heavy_check_mark: |
| Simple 'no results' message | Just show 'No results to interpret.' without LLM call. | |

**User's choice:** Explain why empty
**Notes:** None

---

## Claude's Discretion

- SSE event format for interpretation streaming
- Interpretation panel CSS styling and collapse/expand animation
- Pipeline summary construction
- Follow-up agent persona details and skill file content
- `read_cube_results` tool implementation
- How interpretation summary is passed to follow-up agent
- Loading indicator design during streaming

## Deferred Ideas

None — discussion stayed within phase scope
