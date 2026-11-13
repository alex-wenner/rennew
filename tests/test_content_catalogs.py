from pathlib import Path

from rennew.agent.skills import SkillCatalog
from rennew.prompts import PromptCatalog


def test_builtin_prompts_are_loadable() -> None:
    prompt = PromptCatalog().load("roles/builder")
    assert "builder session" in prompt


def test_builtin_skills_are_discoverable() -> None:
    skills = SkillCatalog.default(Path(".")).discover()
    assert {"change-validator", "repository-explorer"}.issubset({skill.name for skill in skills})
