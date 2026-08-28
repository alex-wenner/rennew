from typing import Protocol

from pydantic import BaseModel, Field

from rennew.sessions.models import Compaction, Handoff, Session, SessionOverlap


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

    def create_handoff(self, handoff: Handoff) -> Handoff: ...

    def create_overlap(self, overlap: SessionOverlap) -> SessionOverlap: ...

    def create_compaction(self, compaction: Compaction) -> Compaction: ...

    def list_compactions(self, session_id: str) -> list[Compaction]: ...

    def snapshot(self) -> GraphSnapshot: ...

    def query_readonly(self, cypher: str) -> GraphQueryResult: ...
