from pydantic import BaseModel, Field

from rennew.sessions.models import new_identifier, utc_now


class MemoryEntry(BaseModel):
    id: str
    scope: str  # "workspace" | "global"
    content: str
    source: str
    confidence: float = 0.5
    created_at: str = ""
    session_id: str | None = None


def new_memory(content: str, *, scope: str = "workspace", source: str = "agent", session_id: str | None = None) -> MemoryEntry:
    return MemoryEntry(
        id=new_identifier("mem"),
        scope=scope,
        content=content,
        source=source,
        session_id=session_id,
        created_at=utc_now().isoformat(),
    )


class MemoryIndex(BaseModel):
    entries: list[MemoryEntry] = Field(default_factory=list)
