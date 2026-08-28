from rennew.prompts import PromptCatalog
from rennew.skills import SkillCatalog


def test_builtin_prompts_are_loadable() -> None:
    prompt = PromptCatalog().load("roles/builder")
    assert "builder session" in prompt


def test_builtin_skills_are_discoverable() -> None:
    skills = SkillCatalog().discover()
    assert {skill.name for skill in skills} == {"change-validator", "repository-explorer"}
