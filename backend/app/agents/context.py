"""Agent context — ToolContext dataclass and conversation history pruning."""

import json
import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

PRUNE_THRESHOLD_TOKENS = 50_000  # Drop oldest turns when history exceeds this


@dataclass
class ToolContext:
    """Injected into every tool function call by the dispatcher."""

    db_session: Any  # AsyncSession, typed as Any to avoid circular import
    cube_registry: Any  # CubeRegistry instance
    workflow_id: str | None = None
    workflow_graph: dict | None = None      # Serialized graph for read_workflow_graph
    execution_errors: dict | None = None    # Errors from last run for read_execution_errors
    execution_results: dict | None = None   # Results summary for read_execution_results
    session_id: str | None = None           # Session ID for working memory tools


def estimate_tokens(history: list) -> int:
    """Approximate token count from history content parts.

    Uses ~4 chars per token heuristic (per D-10).
    Counts text in all content parts. Returns estimated token count.
    """
    total_chars = 0
    for content in history:
        if hasattr(content, "parts"):
            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    total_chars += len(part.text)
                elif hasattr(part, "function_response"):
                    # Function responses can be large — count serialized size
                    try:
                        total_chars += len(json.dumps(part.function_response))
                    except (TypeError, ValueError):
                        total_chars += 200  # estimate for unserializable
    return total_chars // 4


def prune_history(history: list, system_prompt_turns: int = 1) -> list:
    """Drop oldest non-system turn pairs until under token threshold.

    Per D-11: drop oldest user/assistant turn pairs first, always keep
    system prompt + recent turns. Tool results from old turns are the
    first to go (biggest token consumers).

    Args:
        history: list of Content objects (google.genai.types.Content)
        system_prompt_turns: number of turns at start to preserve (system prompt)

    Returns:
        Pruned history list (mutated in place and returned)
    """
    while estimate_tokens(history) > PRUNE_THRESHOLD_TOKENS:
        # Keep system prompt (first N turns) + at least 2 recent turns
        safe_prefix = system_prompt_turns
        if len(history) <= safe_prefix + 2:
            break  # Cannot prune further without losing system prompt or recent context
        # Remove the oldest non-system turn
        history.pop(safe_prefix)
        log.debug(
            "Pruned history turn; remaining turns: %d, tokens: ~%d",
            len(history),
            estimate_tokens(history),
        )
    return history
