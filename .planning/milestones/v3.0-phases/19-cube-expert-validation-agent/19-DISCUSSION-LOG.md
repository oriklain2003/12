# Phase 19: Cube Expert + Validation Agent - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-24
**Phase:** 19-cube-expert-validation-agent
**Areas discussed:** Validation rules & severity, Validation trigger & UX, Cube Expert sub-agent, LLM role in validation

---

## Validation Rules & Severity

### Type Mismatch Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Warn but allow | Show a warning on the edge but don't block execution. Matches existing behavior. | ✓ |
| Block execution | Treat type mismatches as errors that prevent running. Stricter but changes existing behavior. | |
| You decide | Claude picks the approach that fits the existing codebase best. | |

**User's choice:** Warn but allow (Recommended)
**Notes:** Consistent with PROJECT.md spec that already allows type mismatches with warnings.

### Orphan Node Detection

| Option | Description | Selected |
|--------|-------------|----------|
| Warn about orphans | Flag isolated cubes as warnings — they won't receive input and their output goes nowhere. | ✓ |
| Ignore orphans | Don't flag them — users may intentionally leave cubes on canvas while experimenting. | |
| You decide | Claude picks based on how the executor handles orphan nodes. | |

**User's choice:** Warn about orphans (Recommended)

### Severity Levels

| Option | Description | Selected |
|--------|-------------|----------|
| Two levels: error + warning | Errors block execution, warnings are informational. Simple and clear. | ✓ |
| Three levels: error + warning + info | Adds info level for hints. More granular but more complexity. | |
| You decide | Claude picks the severity model. | |

**User's choice:** Two levels: error + warning (Recommended)

### Handle Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, validate handles | Verify sourceHandle and targetHandle exist in the cube definitions. | ✓ |
| You decide | Claude handles the specifics of handle validation. | |

**User's choice:** Yes, validate handles (Recommended)

---

## Validation Trigger & UX

### When Validation Runs

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-run only | Validation runs automatically when user clicks Run. No standalone Validate button. | ✓ |
| Pre-run + standalone button | Both: auto-validate on Run AND a separate Validate button. | |
| You decide | Claude picks the trigger strategy. | |

**User's choice:** Pre-run only (Recommended)

### Issue Display Location

| Option | Description | Selected |
|--------|-------------|----------|
| Issues panel below canvas | Collapsible panel (console style). Clicking an issue highlights relevant node. | ✓ |
| Modal dialog | Modal pops up listing all issues. Must be dismissed. | |
| Inline on nodes | Red/yellow badges directly on affected nodes. | |
| You decide | Claude picks the display approach. | |

**User's choice:** Issues panel below canvas (Recommended)

### Clean Pass Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Silent — just run | Execution starts immediately with no confirmation. | ✓ |
| Brief toast notification | Quick 'Validation passed' toast before execution. | |
| You decide | Claude picks the clean-pass behavior. | |

**User's choice:** Silent — just run (Recommended)

---

## Cube Expert Sub-Agent

### Invocation Model

| Option | Description | Selected |
|--------|-------------|----------|
| Direct function calls | Canvas/Build agents call catalog tools directly. No separate LLM call. | |
| Separate Gemini call | Cube Expert gets its own Gemini chat turn with cube_expert.md skill file. | ✓ |
| You decide | Claude picks based on Phase 20/21 needs. | |

**User's choice:** Separate Gemini call
**Notes:** User wants richer reasoning about cube selection, even at cost of extra LLM round-trip.

### Additional Tools

| Option | Description | Selected |
|--------|-------------|----------|
| Add search-by-capability | New find_cubes_for_task tool with keyword search. Pure string matching. | ✓ |
| Just the existing two | list_cubes_summary + get_cube_definition are sufficient. | |
| You decide | Claude decides based on catalog size and agent needs. | |

**User's choice:** Add search-by-capability (Recommended)

### HTTP Endpoint

| Option | Description | Selected |
|--------|-------------|----------|
| Internal only | No HTTP endpoint. Used by Canvas/Build agents internally. | ✓ |
| Also expose endpoint | Add user-facing endpoint for direct catalog exploration. | |

**User's choice:** Internal only (Recommended)

### Model Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Flash | gemini-2.5-flash per STATE.md architecture decision. Fast and cheap. | ✓ |
| Pro | gemini-2.5-pro for stronger reasoning. Slower and more expensive. | |
| You decide | Claude picks based on reasoning complexity needed. | |

**User's choice:** Flash (Recommended)

---

## LLM Role in Validation

### Check Engine

| Option | Description | Selected |
|--------|-------------|----------|
| Rule-based checks only | All checks are deterministic Python code. Fast, predictable, no API cost. | ✓ |
| LLM-assisted checks | Add semantic checks via Gemini. Richer but adds latency and cost. | |
| You decide | Claude picks the check engine approach. | |

**User's choice:** Rule-based checks only (Recommended)

### Explanation Generation

| Option | Description | Selected |
|--------|-------------|----------|
| Template-based | Pre-written templates per issue type with cube/param names filled in. Instant. | ✓ |
| LLM-generated per issue | Send issues to Gemini for natural-language explanations. More conversational. | |
| You decide | Claude picks the explanation approach. | |

**User's choice:** Template-based (Recommended)

### Endpoint Type

| Option | Description | Selected |
|--------|-------------|----------|
| Sync JSON | POST /api/agent/validate returns JSON with issues array. | ✓ |
| SSE stream | Stream validation progress. Overkill for <100ms checks. | |

**User's choice:** Sync JSON (Recommended)

---

## Claude's Discretion

- Validation rule implementation details (graph traversal, handle existence checking)
- find_cubes_for_task search algorithm
- Cube Expert Python class structure
- Issues panel frontend component design
- Validation response schema shape

## Deferred Ideas

None — discussion stayed within phase scope
