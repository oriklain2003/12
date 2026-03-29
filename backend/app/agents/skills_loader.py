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


def get_system_prompt(persona: str, working_memory: dict[str, str] | None = None) -> str:
    """Combine system_brief + persona skill + working memory into one system prompt.

    The system brief (Tracer 42 domain context) is always prepended.
    Working memory (mission, investigation, plan) is appended when present.
    """
    brief = _skills.get("system_brief", "")
    persona_text = _skills.get(persona, "")
    prompt = f"{brief}\n\n{persona_text}"

    # Inject working memory if any field has content
    if working_memory:
        sections = []
        if working_memory.get("mission"):
            sections.append(f"### Current Mission\n{working_memory['mission']}")
        if working_memory.get("investigation"):
            sections.append(f"### Investigation Log\n{working_memory['investigation']}")
        if working_memory.get("implementation_plan"):
            sections.append(f"### Implementation Plan\n{working_memory['implementation_plan']}")
        if working_memory.get("last_preview"):
            sections.append(
                f"### Last Preview (structured JSON from show_intent_preview)\n"
                f"Use this exact data when generating the workflow. The cubes, connections, "
                f"and parameters here are what the analyst approved.\n"
                f"```json\n{working_memory['last_preview']}\n```"
            )
        if sections:
            prompt += "\n\n## Working Memory (from previous turns)\n" + "\n\n".join(sections)

    return prompt.strip()


def get_all_personas() -> list[str]:
    """Return names of all loaded skills except system_brief."""
    return [name for name in _skills if name != "system_brief"]
