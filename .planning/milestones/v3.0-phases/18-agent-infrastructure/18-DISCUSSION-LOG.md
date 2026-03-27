# Phase 18: Agent Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-24
**Phase:** 18-agent-infrastructure
**Areas discussed:** Skill file design, Tool dispatch API, Context & history, Config & API key

---

## Skill File Design

### Organization

| Option | Description | Selected |
|--------|-------------|----------|
| One file per agent | backend/app/agents/skills/ with .md per persona + shared system_brief.md | ✓ |
| Structured YAML | YAML files with role/instructions/tools/constraints keys | |
| Python constants | String constants in prompts.py module | |

**User's choice:** One file per agent
**Notes:** Complete system prompt per agent persona in markdown

### System Brief

| Option | Description | Selected |
|--------|-------------|----------|
| Hand-written markdown | Single system_brief.md with domain context, manually updated | ✓ |
| Auto-generated at startup | Built from CubeRegistry + DB schema introspection | |
| Hybrid | Hand-written narrative + auto-injected catalog summary | |

**User's choice:** Hand-written markdown

### Loading Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Load at startup, cache in memory | Read .md files during lifespan startup, zero I/O per request | ✓ |
| Re-read per request | Dev-friendly but slower | |
| Startup + dev reload flag | Cache in prod, re-read in debug mode | |

**User's choice:** Load at startup, cache in memory

### File Path

| Option | Description | Selected |
|--------|-------------|----------|
| backend/app/agents/skills/ | Inside agents package | ✓ |
| backend/skills/ | Top-level in backend | |
| backend/app/agents/prompts/ | Sub-directory called prompts/ | |

**User's choice:** backend/app/agents/skills/

---

## Tool Dispatch API

### Registration

| Option | Description | Selected |
|--------|-------------|----------|
| Decorator-based | @agent_tool on async functions, registry collects at import | ✓ |
| Explicit registry dict | Manual TOOLS dict in tools.py | |
| Class-based tools | Each tool is a class with execute() method | |

**User's choice:** Decorator-based

### Input Schemas

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic models | Auto-convert to Gemini JSON schema, validates input | ✓ |
| Raw JSON schema dicts | Plain dicts matching Gemini format | |
| You decide | Claude's discretion | |

**User's choice:** Pydantic models

### Error Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Return error to LLM | Send error as tool result for Gemini to reason about | |
| Retry once then return error | Single retry for transient failures, then error to LLM | ✓ |
| Fail the whole turn | Stop agent turn on tool failure | |

**User's choice:** Retry once then return error

### Tool Context

| Option | Description | Selected |
|--------|-------------|----------|
| Injected context arg | ToolContext dataclass with db_session, registry, etc. | ✓ |
| Global imports | Tools import dependencies directly | |
| You decide | Claude's discretion | |

**User's choice:** Injected context arg

---

## Context & History

### History Transport

| Option | Description | Selected |
|--------|-------------|----------|
| Full messages in POST body | Client sends complete message array each request | |
| Server-side session with ID | Server stores conversation, client sends session_id + new message | ✓ |

**User's choice:** Server-side session with ID
**Notes:** Departs from research assumption of client-carried history

### Token Counting

| Option | Description | Selected |
|--------|-------------|----------|
| Approximate char-based | ~4 chars per token estimate | ✓ |
| tiktoken library | Accurate but adds dependency, Gemini tokenization differs | |
| Gemini count_tokens API | Most accurate but adds latency | |

**User's choice:** Approximate char-based

### Session Store

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory dict | Simple Python dict with TTL, lost on restart | ✓ |
| Workflow DB table | JSONB column on workflows table | |
| Separate SQLite/file | Local SQLite or JSON files | |

**User's choice:** In-memory dict

### SSE Event Types

| Option | Description | Selected |
|--------|-------------|----------|
| Typed event stream | Distinct SSE types: text, tool_call, tool_result, thinking, done | ✓ |
| Text-only with markers | Single text stream with inline markers | |
| You decide | Claude's discretion | |

**User's choice:** Typed event stream
**Notes:** User explicitly requested real-time streaming of agent thinking and tool execution

### History Pruning

| Option | Description | Selected |
|--------|-------------|----------|
| Drop oldest turns, keep system + recent | Remove oldest pairs first, tool results go first | ✓ |
| Summarize old turns | LLM summarizes first half into compact paragraph | |
| You decide | Claude's discretion | |

**User's choice:** Drop oldest turns, keep system + recent

---

## Config & API Key

### API Key Location

| Option | Description | Selected |
|--------|-------------|----------|
| GEMINI_API_KEY in .env | Add to existing Settings class in config.py | ✓ |
| Separate agent config file | New agents/config.py with own Settings | |
| You decide | Claude's discretion | |

**User's choice:** GEMINI_API_KEY in .env

### Model Names

| Option | Description | Selected |
|--------|-------------|----------|
| Config with sensible defaults | Settings fields with env-var-overridable defaults | ✓ |
| Hardcoded constants | Constants in agent module | |
| Per-agent config in skill files | Frontmatter in .md files | |

**User's choice:** Config with sensible defaults

### Retry Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Simple retry with backoff | Up to 2 retries on 429/503 with exponential backoff | ✓ |
| No retry, fail fast | Return error immediately | |
| You decide | Claude's discretion | |

**User's choice:** Simple retry with backoff

### Session TTL

| Option | Description | Selected |
|--------|-------------|----------|
| 30 minute TTL | Sessions expire after 30min inactivity with background cleanup | ✓ |
| 1 hour TTL | Longer window, more memory usage | |
| You decide | Claude's discretion | |

**User's choice:** 30 minute TTL

---

## Claude's Discretion

- Tool dispatch implementation details (decorator internals, registry data structures)
- Pydantic-to-Gemini schema conversion approach
- Session cleanup background task implementation
- SSE event serialization format (JSON structure within each event type)

## Deferred Ideas

None — discussion stayed within phase scope
