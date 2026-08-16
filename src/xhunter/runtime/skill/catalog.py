"""Skills are inert knowledge and prompts; they never receive a runtime handle."""

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Skill:
    skill_id: str
    name: str
    version: str
    prompt: str
    tags: tuple[str, ...] = ()


class SkillCatalog:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> Callable[[], None]:
        if not skill.skill_id or not skill.prompt.strip():
            raise ValueError("skill id and prompt must not be empty")
        if skill.skill_id in self._skills:
            raise ValueError(f"skill already registered: {skill.skill_id}")
        self._skills[skill.skill_id] = skill

        def dispose() -> None:
            if self._skills.get(skill.skill_id) is skill:
                del self._skills[skill.skill_id]

        return dispose

    def get(self, skill_id: str) -> Skill | None:
        return self._skills.get(skill_id)

    def render(self, skill_ids: tuple[str, ...]) -> str:
        missing = [skill_id for skill_id in skill_ids if skill_id not in self._skills]
        if missing:
            raise KeyError(f"unknown skills: {', '.join(missing)}")
        return "\n\n".join(self._skills[skill_id].prompt for skill_id in skill_ids)


def load_skill_directory(directory: Path) -> Skill:
    """Load inert TOML metadata and Markdown from a repository-owned directory."""
    metadata = tomllib.loads((directory / "skill.toml").read_text(encoding="utf-8"))
    prompt = (directory / "SKILL.md").read_text(encoding="utf-8")
    tags = metadata.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError("skill tags must be a string list")
    return Skill(
        skill_id=_required_string(metadata, "id"),
        name=_required_string(metadata, "name"),
        version=_required_string(metadata, "version"),
        prompt=prompt,
        tags=tuple(tags),
    )


def _required_string(metadata: dict[str, object], name: str) -> str:
    value = metadata.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"skill {name} must be a non-empty string")
    return value
