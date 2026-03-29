"""Server-side agent session management with TTL cleanup."""

import asyncio
import logging
import time
import uuid as uuid_mod

from app.config import settings

log = logging.getLogger(__name__)

# Each session: {"history": list, "last_accessed": float, "persona": str}
_sessions: dict[str, dict] = {}


def create_session(persona: str = "canvas_agent") -> str:
    """Create a new session and return its ID."""
    session_id = str(uuid_mod.uuid4())
    _sessions[session_id] = {
        "history": [],
        "last_accessed": time.time(),
        "persona": persona,
    }
    return session_id


def get_or_create_session(session_id: str | None, persona: str = "canvas_agent") -> tuple[str, list]:
    """Get existing session history or create a new one.

    Returns (session_id, history). If session_id is None or not found,
    creates a new session and returns the new ID.
    """
    if session_id and session_id in _sessions:
        _sessions[session_id]["last_accessed"] = time.time()
        return session_id, _sessions[session_id]["history"]
    # Create new
    new_id = session_id or str(uuid_mod.uuid4())
    _sessions[new_id] = {
        "history": [],
        "last_accessed": time.time(),
        "persona": persona,
    }
    return new_id, _sessions[new_id]["history"]


def update_session(session_id: str, history: list) -> None:
    """Update session with new history after a turn."""
    if session_id in _sessions:
        _sessions[session_id]["history"] = history
        _sessions[session_id]["last_accessed"] = time.time()


def get_session_persona(session_id: str) -> str:
    """Return the persona for a session, or default."""
    if session_id in _sessions:
        return _sessions[session_id].get("persona", "canvas_agent")
    return "canvas_agent"


async def start_cleanup_task() -> None:
    """Periodic background task: remove sessions idle > TTL (per D-09)."""
    ttl_seconds = settings.agent_session_ttl_minutes * 60
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes
            now = time.time()
            expired = [
                sid for sid, s in _sessions.items()
                if now - s["last_accessed"] > ttl_seconds
            ]
            for sid in expired:
                del _sessions[sid]
            if expired:
                log.info("Cleaned up %d expired agent sessions", len(expired))
        except asyncio.CancelledError:
            break  # Clean shutdown


def get_working_memory(session_id: str) -> dict[str, str]:
    """Return the working memory notes for a session.

    Keys: mission, investigation, implementation_plan, last_preview. Each is a string.
    """
    if session_id not in _sessions:
        return {"mission": "", "investigation": "", "implementation_plan": "", "last_preview": ""}
    mem = _sessions[session_id].get("working_memory", {})
    return {
        "mission": mem.get("mission", ""),
        "investigation": mem.get("investigation", ""),
        "implementation_plan": mem.get("implementation_plan", ""),
        "last_preview": mem.get("last_preview", ""),
    }


def update_working_memory(session_id: str, key: str, value: str) -> None:
    """Update one working memory note for a session."""
    if session_id not in _sessions:
        return
    if "working_memory" not in _sessions[session_id]:
        _sessions[session_id]["working_memory"] = {}
    _sessions[session_id]["working_memory"][key] = value


def active_session_count() -> int:
    """Return number of active sessions (for monitoring)."""
    return len(_sessions)
