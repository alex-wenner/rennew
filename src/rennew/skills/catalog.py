from pathlib import Path

from rennew.skills.models import SkillManifest


class SkillCatalog:
    def __init__(self, roots: list[Path] | None = None) -> None:
        builtin_root = Path(__file__).parent / "builtin"
        self._roots = roots or [builtin_root]

    def discover(self) -> list[SkillManifest]:
        manifests: list[SkillManifest] = []
        for root in self._roots:
            for skill_file in sorted(root.glob("*/SKILL.md")):
                text = skill_file.read_text(encoding="utf-8")
                title, _, body = text.partition("\n")
                manifests.append(
                    SkillManifest(
                        name=skill_file.parent.name,
                        description=title.removeprefix("# ").strip(),
                        path=skill_file,
                        instructions=body.strip(),
                    )
                )
        return manifests
