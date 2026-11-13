from typing import Protocol

from pydantic import BaseModel, Field

from rennew.sessions.models import (
    Compaction,
    FileChange,
    Handoff,
    Session,
    SessionMessage,
    SessionOverlap,
)


class GraphNode(BaseModel):
    id: str
    kind: str
    label: str
    properties: dict[str, object] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: str
    properties: dict[str, object] = Field(default_factory=dict)


class GraphSnapshot(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphQueryResult(BaseModel):
    columns: list[str]
    rows: list[dict[str, object]]


class GraphStore(Protocol):
    def initialize(self) -> None: ...

    def close(self) -> None: ...

    def create_session(self, session: Session) -> Session: ...

    def list_sessions(self) -> list[Session]: ...

    def get_session(self, session_id: str) -> Session | None: ...

    def update_session_model(self, session_id: str, provider: str, model: str) -> None: ...

    def create_handoff(self, handoff: Handoff) -> Handoff: ...

    def create_overlap(self, overlap: SessionOverlap) -> SessionOverlap: ...

    def create_compaction(self, compaction: Compaction) -> Compaction: ...

    def list_compactions(self, session_id: str) -> list[Compaction]: ...

    def create_message(self, message: SessionMessage) -> SessionMessage: ...

    def list_messages(self, session_id: str) -> list[SessionMessage]: ...

    def update_session_metrics(
        self,
        session_id: str,
        input_tokens: int,
        output_tokens: int,
        reasoning_tokens: int,
        cost_usd: float,
    ) -> None: ...

    def create_memory(
        self,
        memory_id: str,
        scope: str,
        content: str,
        source: str,
        confidence: float,
        session_id: str | None,
    ) -> None: ...

    def list_memories(self, limit: int = 200) -> list[dict[str, object]]: ...

    def create_file_change(self, change: FileChange) -> FileChange: ...

    def list_file_changes(self, session_id: str | None = None) -> list[FileChange]: ...

    def get_file_change(self, change_id: str) -> FileChange | None: ...

    def snapshot(self) -> GraphSnapshot: ...

    def query_readonly(self, cypher: str) -> GraphQueryResult: ...
