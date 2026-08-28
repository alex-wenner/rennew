import re
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from threading import RLock
from typing import Any

import ladybug as lb

from rennew.graph.contracts import GraphEdge, GraphNode, GraphQueryResult, GraphSnapshot
from rennew.graph.schema import SCHEMA_STATEMENTS
from rennew.sessions.models import Compaction, Handoff, Session, SessionOverlap

_FORBIDDEN_QUERY_TOKENS = re.compile(
    r"\b(ALTER|ATTACH|BEGIN|CALL|COMMIT|COPY|CREATE|DELETE|DETACH|DROP|INSTALL|"
    r"LOAD|MERGE|REMOVE|ROLLBACK|SET)\b",
    flags=re.IGNORECASE,
)


class UnsafeGraphQueryError(ValueError):
    pass


class LadybugGraphStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._database: Any | None = None
        self._connection: Any | None = None
        self._lock = RLock()

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._database = lb.Database(str(self._path))
        self._connection = lb.Connection(self._database)
        with self._lock:
            for statement in SCHEMA_STATEMENTS:
                self._execute(statement)

    def close(self) -> None:
        self._connection = None
        self._database = None

    def create_session(self, session: Session) -> Session:
        with self._lock:
            self._execute(
                """
                CREATE (:Session {
                    id: $id,
                    title: $title,
                    status: $status,
                    provider: $provider,
                    model: $model,
                    created_at: $created_at,
                    updated_at: $updated_at
                })
                """,
                {
                    **session.model_dump(exclude={"status"}),
                    "status": session.status.value,
                },
            )
        return session

    def list_sessions(self) -> list[Session]:
        with self._lock:
            rows = self._rows(
                """
                MATCH (s:Session)
                RETURN s.id AS id, s.title AS title, s.status AS status,
                       s.provider AS provider, s.model AS model,
                       s.created_at AS created_at, s.updated_at AS updated_at
                ORDER BY s.updated_at DESC
                """
            )
        return [Session.model_validate(row) for row in rows]

    def get_session(self, session_id: str) -> Session | None:
        with self._lock:
            rows = self._rows(
                """
                MATCH (s:Session {id: $id})
                RETURN s.id AS id, s.title AS title, s.status AS status,
                       s.provider AS provider, s.model AS model,
                       s.created_at AS created_at, s.updated_at AS updated_at
                """,
                {"id": session_id},
            )
        return Session.model_validate(rows[0]) if rows else None

    def create_handoff(self, handoff: Handoff) -> Handoff:
        with self._lock:
            self._execute(
                """
                MATCH (source:Session {id: $source_id}), (target:Session {id: $target_id})
                CREATE (handoff:Handoff {
                    id: $id,
                    kind: $kind,
                    status: $status,
                    summary: $summary,
                    created_at: $created_at
                })
                CREATE (source)-[:SENT]->(handoff)
                CREATE (handoff)-[:RECEIVED_BY]->(target)
                """,
                {
                    "id": handoff.id,
                    "source_id": handoff.source_session_id,
                    "target_id": handoff.target_session_id,
                    "kind": handoff.kind.value,
                    "status": handoff.status.value,
                    "summary": handoff.summary,
                    "created_at": handoff.created_at,
                },
            )
        return handoff

    def create_overlap(self, overlap: SessionOverlap) -> SessionOverlap:
        with self._lock:
            self._execute(
                """
                MATCH (source:Session {id: $source_id}), (target:Session {id: $target_id})
                CREATE (source)-[:OVERLAPS_WITH {
                    kind: $kind,
                    score: $score,
                    evidence: $evidence,
                    inferred: $inferred
                }]->(target)
                """,
                {
                    "source_id": overlap.source_session_id,
                    "target_id": overlap.target_session_id,
                    "kind": overlap.kind.value,
                    "score": overlap.score,
                    "evidence": overlap.evidence,
                    "inferred": overlap.inferred,
                },
            )
        return overlap

    def create_compaction(self, compaction: Compaction) -> Compaction:
        with self._lock:
            self._execute(
                """
                MATCH (session:Session {id: $session_id})
                CREATE (compaction:Compaction {
                    id: $id,
                    session_id: $session_id,
                    objective: $objective,
                    completed: $completed,
                    active: $active,
                    blocked: $blocked,
                    next_move: $next_move,
                    relevant_files: $relevant_files,
                    tokens_saved: $tokens_saved,
                    created_at: $created_at
                })
                CREATE (session)-[:COMPACTED_TO]->(compaction)
                """,
                compaction.model_dump(),
            )
        return compaction

    def list_compactions(self, session_id: str) -> list[Compaction]:
        with self._lock:
            rows = self._rows(
                """
                MATCH (s:Session {id: $session_id})-[:COMPACTED_TO]->(c:Compaction)
                RETURN c.id AS id, c.session_id AS session_id, c.objective AS objective,
                       c.completed AS completed, c.active AS active, c.blocked AS blocked,
                       c.next_move AS next_move, c.relevant_files AS relevant_files,
                       c.tokens_saved AS tokens_saved, c.created_at AS created_at
                ORDER BY c.created_at DESC
                """,
                {"session_id": session_id},
            )
        return [Compaction.model_validate(row) for row in rows]

    def snapshot(self) -> GraphSnapshot:
        sessions = self.list_sessions()
        nodes = [
            GraphNode(
                id=session.id,
                kind="session",
                label=session.title,
                properties={
                    "status": session.status.value,
                    "provider": session.provider or "",
                    "model": session.model or "",
                },
            )
            for session in sessions
        ]

        with self._lock:
            overlap_rows = self._rows(
                """
                MATCH (source:Session)-[overlap:OVERLAPS_WITH]->(target:Session)
                RETURN source.id AS source, target.id AS target, overlap.kind AS kind,
                       overlap.score AS score, overlap.evidence AS evidence,
                       overlap.inferred AS inferred
                """
            )
            handoff_rows = self._rows(
                """
                MATCH (source:Session)-[:SENT]->(handoff:Handoff)-[:RECEIVED_BY]->(target:Session)
                RETURN handoff.id AS id, source.id AS source, target.id AS target,
                       handoff.kind AS kind, handoff.status AS status,
                       handoff.summary AS summary
                """
            )
            compaction_rows = self._rows(
                """
                MATCH (source:Session)-[:COMPACTED_TO]->(c:Compaction)
                RETURN c.id AS id, source.id AS source, c.objective AS objective,
                       c.tokens_saved AS tokens_saved, c.created_at AS created_at
                """
            )

        for row in compaction_rows:
            nodes.append(
                GraphNode(
                    id=str(row["id"]),
                    kind="compaction",
                    label=f"Checkpoint ({row['tokens_saved']} tokens saved)",
                    properties={
                        "objective": row["objective"],
                        "tokens_saved": row["tokens_saved"],
                    },
                )
            )

        edges = [
            GraphEdge(
                id=f"overlap:{row['source']}:{row['target']}:{index}",
                source=str(row["source"]),
                target=str(row["target"]),
                kind="overlap",
                properties={
                    "kind": row["kind"],
                    "score": row["score"],
                    "evidence": row["evidence"],
                    "inferred": row["inferred"],
                },
            )
            for index, row in enumerate(overlap_rows)
        ]
        edges.extend(
            GraphEdge(
                id=str(row["id"]),
                source=str(row["source"]),
                target=str(row["target"]),
                kind="handoff",
                properties={
                    "kind": row["kind"],
                    "status": row["status"],
                    "summary": row["summary"],
                },
            )
            for row in handoff_rows
        )
        edges.extend(
            GraphEdge(
                id=f"compacted:{row['id']}",
                source=str(row["source"]),
                target=str(row["id"]),
                kind="compaction",
                properties={"tokens_saved": row["tokens_saved"]},
            )
            for row in compaction_rows
        )
        return GraphSnapshot(nodes=nodes, edges=edges)

    def query_readonly(self, cypher: str) -> GraphQueryResult:
        query = cypher.strip()
        if not query:
            raise UnsafeGraphQueryError("A Cypher query is required.")
        if ";" in query.rstrip(";"):
            raise UnsafeGraphQueryError("Only one Cypher statement is allowed.")
        if _FORBIDDEN_QUERY_TOKENS.search(query):
            raise UnsafeGraphQueryError("The graph console is read-only.")

        with self._lock:
            rows = self._rows(query)
        normalized = [
            {str(key): _json_value(value) for key, value in row.items()} for row in rows[:1_000]
        ]
        columns = list(normalized[0]) if normalized else []
        return GraphQueryResult(columns=columns, rows=normalized)

    def _execute(
        self, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Any:
        if self._connection is None:
            raise RuntimeError("Graph store is not initialized.")
        return self._connection.execute(statement, parameters=dict(parameters or {}))

    def _rows(
        self, statement: str, parameters: Mapping[str, object] | None = None
    ) -> list[dict[str, Any]]:
        result = self._execute(statement, parameters)
        return list(result.rows_as_dict().get_all())


def _json_value(value: object) -> object:
    if value is None or isinstance(value, (bool, float, int, str)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)
