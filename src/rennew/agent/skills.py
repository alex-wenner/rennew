from pathlib import Path

from pydantic import BaseModel

from rennew.providers.contracts import ToolSchema


class Skill(BaseModel):
    name: str
    description: str
    path: Path
    body: str


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Minimal YAML frontmatter parser for flat `key: value` pairs."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    meta: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, "\n".join(lines[index + 1 :])
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip("\"'")
    return {}, text


class SkillCatalog:
    """Discovers SKILL.md files. Skills are listed by name+description in the
    system prompt and loaded on demand through the `skill` tool, keeping
    context small until a skill is actually needed."""

    def __init__(self, roots: list[Path]) -> None:
        self._roots = roots

    @classmethod
    def default(cls, workspace: Path) -> "SkillCatalog":
        builtin = Path(__file__).parent.parent / "skills" / "builtin"
        return cls(
            roots=[
                workspace / ".rennew" / "skills",
                workspace / ".agents" / "skills",
                builtin,
            ]
        )

    def discover(self) -> list[Skill]:
        skills: dict[str, Skill] = {}
        for root in self._roots:
            if not root.exists():
                continue
            for skill_file in sorted(root.glob("*/SKILL.md")):
                meta, body = parse_frontmatter(skill_file.read_text(encoding="utf-8"))
                name = meta.get("name") or skill_file.parent.name
                if name in skills:
                    continue
                skills[name] = Skill(
                    name=name,
                    description=meta.get("description") or _first_heading(body),
                    path=skill_file,
                    body=body.strip(),
                )
        return list(skills.values())

    def get(self, name: str) -> Skill | None:
        return next((skill for skill in self.discover() if skill.name == name), None)

    def prompt_listing(self) -> str:
        skills = self.discover()
        if not skills:
            return ""
        lines = ["Available skills (load one with the `skill` tool):"]
        lines.extend(f"- {skill.name}: {skill.description}" for skill in skills)
        return "\n".join(lines)

    def tool_schema(self) -> ToolSchema:
        return ToolSchema(
            name="skill",
            description="Load a skill's full instructions by name. Use when a task matches a listed skill.",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Skill name."}},
                "required": ["name"],
            },
        )


def _first_heading(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""
