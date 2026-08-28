from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MemoryScope(StrEnum):
    SESSION = "session"
    TASK = "task"
    REPOSITORY = "repository"
    USER = "user"


class Memory(BaseModel):
    id: str
    scope: MemoryScope
    content: str
    source: str
    confidence: float = Field(ge=0, le=1)
    created_at: datetime
