"""Skill file loader — loads agent persona prompts from disk at startup."""

import logging
from pathlib import Path

log = logging.getLogger(__name__)

_skills: dict[str, str] = {}
SKILLS_DIR = Path(__file__).parent / "skills"


def load_skill_files() -> None:
    """Load all .md skill files from the skills directory into memory.

    Called once during FastAPI lifespan startup. Requires server restart
    to pick up prompt changes (uvicorn --reload handles dev).
    """
    for md_file in SKILLS_DIR.glob("*.md"):
        _skills[md_file.stem] = md_file.read_text(encoding="utf-8")
        log.info("Loaded skill file: %s", md_file.stem)
    log.info("Loaded %d skill files total", len(_skills))


def get_skill(name: str) -> str:
    """Return a skill's content by name (filename stem), or empty string if not found."""
    return _skills.get(name, "")


def get_system_prompt(persona: str) -> str:
    """Combine system_brief + persona skill into one system prompt string.

    The system brief (Tracer 42 domain context) is always prepended.
    Returns just the persona text if system_brief is missing.
    """
    brief = _skills.get("system_brief", "")
    persona_text = _skills.get(persona, "")
    return f"{brief}\n\n{persona_text}".strip()


def get_all_personas() -> list[str]:
    """Return names of all loaded skills except system_brief."""
    return [name for name in _skills if name != "system_brief"]
