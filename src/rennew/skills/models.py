from pathlib import Path

from pydantic import BaseModel


class SkillManifest(BaseModel):
    name: str
    description: str
    path: Path
    instructions: str
