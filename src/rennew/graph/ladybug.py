import json
import re
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from threading import RLock
from typing import Any

import ladybug as lb

from rennew.graph.contracts import GraphEdge, GraphNode, GraphQueryResult, GraphSnapshot
from rennew.graph.schema import MIGRATION_STATEMENTS, SCHEMA_STATEMENTS
from rennew.sessions.models import (
    Compaction,
    FileChange,
    Handoff,
    Session,
    SessionMessage,
    SessionOverlap,
    TokenMetrics,
    ToolCallRecord,
)

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
            for statement in MIGRATION_STATEMENTS:
                try:
                    self._execute(statement)
                except RuntimeError:
                    pass  # column already present

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
                    mode: $mode,
                    workspace: $workspace,
                    total_input_tokens: $total_input_tokens,
                    total_output_tokens: $total_output_tokens,
                    total_reasoning_tokens: $total_reasoning_tokens,
                    total_cost_usd: $total_cost_usd,
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
                       s.provider AS provider, s.model AS model, s.mode AS mode,
                       s.workspace AS workspace,
                       s.total_input_tokens AS total_input_tokens,
                       s.total_output_tokens AS total_output_tokens,
                       s.total_reasoning_tokens AS total_reasoning_tokens,
                       s.total_cost_usd AS total_cost_usd,
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
                       s.provider AS provider, s.model AS model, s.mode AS mode,
                       s.workspace AS workspace,
                       s.total_input_tokens AS total_input_tokens,
                       s.total_output_tokens AS total_output_tokens,
                       s.total_reasoning_tokens AS total_reasoning_tokens,
                       s.total_cost_usd AS total_cost_usd,
                       s.created_at AS created_at, s.updated_at AS updated_at
                """,
                {"id": session_id},
            )
        return Session.model_validate(rows[0]) if rows else None

    def update_session_model(self, session_id: str, provider: str, model: str) -> None:
        with self._lock:
            self._execute(
                "MATCH (s:Session {id: $id}) SET s.provider = $provider, s.model = $model",
                {"id": session_id, "provider": provider, "model": model},
            )

    def update_session_metrics(
        self,
        session_id: str,
        input_tokens: int,
        output_tokens: int,
        reasoning_tokens: int,
        cost_usd: float,
    ) -> None:
        with self._lock:
            self._execute(
                """
                MATCH (s:Session {id: $id})
                SET s.total_input_tokens = s.total_input_tokens + $input_tokens,
                    s.total_output_tokens = s.total_output_tokens + $output_tokens,
                    s.total_reasoning_tokens = s.total_reasoning_tokens + $reasoning_tokens,
                    s.total_cost_usd = s.total_cost_usd + $cost_usd,
                    s.updated_at = $now
                """,
                {
                    "id": session_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "reasoning_tokens": reasoning_tokens,
                    "cost_usd": cost_usd,
                    "now": datetime.now(),
                },
            )

    def create_message(self, message: SessionMessage) -> SessionMessage:
        tool_json = json.dumps([t.model_dump() for t in message.tool_calls])
        with self._lock:
            self._execute(
                """
                MATCH (s:Session {id: $session_id})
                CREATE (m:Message {
                    id: $id,
                    session_id: $session_id,
                    role: $role,
                    content: $content,
                    reasoning: $reasoning,
                    tool_calls_json: $tool_calls_json,
                    input_tokens: $input_tokens,
                    output_tokens: $output_tokens,
                    reasoning_tokens: $reasoning_tokens,
                    cost_usd: $cost_usd,
                    created_at: $created_at
                })
                CREATE (s)-[:HAS_MESSAGE]->(m)
                """,
                {
                    "id": message.id,
                    "session_id": message.session_id,
                    "role": message.role,
                    "content": message.content,
                    "reasoning": message.reasoning or "",
                    "tool_calls_json": tool_json,
                    "input_tokens": message.tokens.input,
                    "output_tokens": message.tokens.output,
                    "reasoning_tokens": message.tokens.reasoning,
                    "cost_usd": message.tokens.cost_usd,
                    "created_at": message.created_at,
                },
            )
        return message

    def list_messages(self, session_id: str) -> list[SessionMessage]:
        with self._lock:
            rows = self._rows(
                """
                MATCH (s:Session {id: $session_id})-[:HAS_MESSAGE]->(m:Message)
                RETURN m.id AS id, m.session_id AS session_id, m.role AS role,
                       m.content AS content, m.reasoning AS reasoning,
                       m.tool_calls_json AS tool_calls_json,
                       m.input_tokens AS input_tokens,
                       m.output_tokens AS output_tokens,
                       m.reasoning_tokens AS reasoning_tokens,
                       m.cost_usd AS cost_usd,
                       m.created_at AS created_at
                ORDER BY m.created_at ASC
                """,
                {"session_id": session_id},
            )
        messages: list[SessionMessage] = []
        for r in rows:
            raw_tools = json.loads(str(r.get("tool_calls_json") or "[]"))
            tool_calls = [ToolCallRecord.model_validate(tc) for tc in raw_tools]
            tokens = TokenMetrics(
                input=int(r.get("input_tokens") or 0),
                output=int(r.get("output_tokens") or 0),
                reasoning=int(r.get("reasoning_tokens") or 0),
                total=int(r.get("input_tokens") or 0) + int(r.get("output_tokens") or 0),
                cost_usd=float(r.get("cost_usd") or 0.0),
            )
            messages.append(
                SessionMessage(
                    id=str(r["id"]),
                    session_id=str(r["session_id"]),
                    role=str(r["role"]),
                    content=str(r["content"]),
                    reasoning=str(r["reasoning"]) if r.get("reasoning") else None,
                    tool_calls=tool_calls,
                    tokens=tokens,
                    created_at=r["created_at"],
                )
            )
        return messages

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

    def create_memory(
        self,
        memory_id: str,
        scope: str,
        content: str,
        source: str,
        confidence: float,
        session_id: str | None,
    ) -> None:
        with self._lock:
            self._execute(
                """
                CREATE (m:Memory {
                    id: $id,
                    scope: $scope,
                    content: $content,
                    source: $source,
                    confidence: $confidence,
                    created_at: $created_at
                })
                """,
                {
                    "id": memory_id,
                    "scope": scope,
                    "content": content,
                    "source": source,
                    "confidence": confidence,
                    "created_at": datetime.now(),
                },
            )
            if session_id:
                self._execute(
                    """
                    MATCH (s:Session {id: $session_id}), (m:Memory {id: $memory_id})
                    CREATE (s)-[:REMEMBERED]->(m)
                    """,
                    {"session_id": session_id, "memory_id": memory_id},
                )

    def create_file_change(self, change: FileChange) -> FileChange:
        with self._lock:
            self._execute(
                """
                MATCH (s:Session {id: $session_id})
                CREATE (f:FileChange {
                    id: $id,
                    session_id: $session_id,
                    message_id: $message_id,
                    tool_call_id: $tool_call_id,
                    path: $path,
                    kind: $kind,
                    before_hash: $before_hash,
                    after_hash: $after_hash,
                    additions: $additions,
                    deletions: $deletions,
                    diff: $diff,
                    created_at: $created_at
                })
                CREATE (s)-[:CHANGED]->(f)
                """,
                {
                    **change.model_dump(),
                    "message_id": change.message_id or "",
                    "tool_call_id": change.tool_call_id or "",
                },
            )
            if change.message_id:
                self._execute(
                    """
                    MATCH (m:Message {id: $message_id}), (f:FileChange {id: $id})
                    CREATE (m)-[:APPLIED]->(f)
                    """,
                    {"message_id": change.message_id, "id": change.id},
                )
        return change

    def list_file_changes(self, session_id: str | None = None) -> list[FileChange]:
        where = "WHERE f.session_id = $session_id" if session_id else ""
        with self._lock:
            rows = self._rows(
                f"""
                MATCH (f:FileChange) {where}
                RETURN f.id AS id, f.session_id AS session_id, f.message_id AS message_id,
                       f.tool_call_id AS tool_call_id, f.path AS path, f.kind AS kind,
                       f.before_hash AS before_hash, f.after_hash AS after_hash,
                       f.additions AS additions, f.deletions AS deletions, f.diff AS diff,
                       f.created_at AS created_at
                ORDER BY f.created_at DESC
                """,
                {"session_id": session_id} if session_id else None,
            )
        result: list[FileChange] = []
        for row in rows:
            data = dict(row)
            data["message_id"] = data.get("message_id") or None
            data["tool_call_id"] = data.get("tool_call_id") or None
            result.append(FileChange.model_validate(data))
        return result

    def get_file_change(self, change_id: str) -> FileChange | None:
        with self._lock:
            rows = self._rows(
                """
                MATCH (f:FileChange {id: $id})
                RETURN f.id AS id, f.session_id AS session_id, f.message_id AS message_id,
                       f.tool_call_id AS tool_call_id, f.path AS path, f.kind AS kind,
                       f.before_hash AS before_hash, f.after_hash AS after_hash,
                       f.additions AS additions, f.deletions AS deletions, f.diff AS diff,
                       f.created_at AS created_at
                """,
                {"id": change_id},
            )
        if not rows:
            return None
        data = dict(rows[0])
        data["message_id"] = data.get("message_id") or None
        data["tool_call_id"] = data.get("tool_call_id") or None
        return FileChange.model_validate(data)

    def list_memories(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._rows(
                """
                MATCH (m:Memory)
                RETURN m.id AS id, m.scope AS scope, m.content AS content,
                       m.source AS source, m.confidence AS confidence,
                       m.created_at AS created_at
                ORDER BY m.created_at DESC
                LIMIT $limit
                """,
                {"limit": limit},
            )
        return [dict(row) for row in rows]

    def snapshot(self) -> GraphSnapshot:
        """Hub-centric graph: sessions are hubs; file changes, memories, compactions
        hang off them. Messages are summarized as counts, not rendered as nodes."""
        sessions = self.list_sessions()
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        with self._lock:
            message_counts = self._rows(
                """
                MATCH (s:Session)-[:HAS_MESSAGE]->(m:Message)
                RETURN s.id AS session_id, count(m) AS messages
                """
            )
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
                       handoff.summary AS summary, handoff.created_at AS created_at
                """
            )
            compaction_rows = self._rows(
                """
                MATCH (source:Session)-[:COMPACTED_TO]->(c:Compaction)
                RETURN c.id AS id, source.id AS source, c.objective AS objective,
                       c.completed AS completed, c.next_move AS next_move,
                       c.tokens_saved AS tokens_saved, c.created_at AS created_at
                """
            )
            change_rows = self._rows(
                """
                MATCH (source:Session)-[:CHANGED]->(f:FileChange)
                RETURN f.id AS id, source.id AS source, f.path AS path, f.kind AS kind,
                       f.additions AS additions, f.deletions AS deletions,
                       f.message_id AS message_id, f.created_at AS created_at
                """
            )
            memory_rows = self._rows(
                """
                MATCH (source:Session)-[:REMEMBERED]->(m:Memory)
                RETURN m.id AS id, source.id AS source, m.content AS content,
                       m.scope AS scope, m.confidence AS confidence, m.created_at AS created_at
                """
            )

        counts = {str(row["session_id"]): int(row["messages"]) for row in message_counts}

        for session in sessions:
            nodes.append(
                GraphNode(
                    id=session.id,
                    kind="session",
                    label=session.title,
                    properties={
                        "id": session.id,
                        "title": session.title,
                        "status": session.status.value,
                        "provider": session.provider or "none",
                        "model": session.model or "none",
                        "messages": counts.get(session.id, 0),
                        "total_tokens": (
                            session.total_input_tokens
                            + session.total_output_tokens
                            + session.total_reasoning_tokens
                        ),
                        "total_cost_usd": session.total_cost_usd,
                        "updated_at": session.updated_at.isoformat(),
                    },
                )
            )

        for row in change_rows:
            change_id = str(row["id"])
            nodes.append(
                GraphNode(
                    id=change_id,
                    kind="change",
                    label=str(row["path"]).rsplit("/", 1)[-1],
                    properties={
                        "id": change_id,
                        "session_id": str(row["source"]),
                        "path": str(row["path"]),
                        "kind": str(row["kind"]),
                        "additions": int(row.get("additions") or 0),
                        "deletions": int(row.get("deletions") or 0),
                        "message_id": str(row.get("message_id") or ""),
                        "created_at": str(row.get("created_at") or ""),
                    },
                )
            )
            edges.append(
                GraphEdge(
                    id=f"changed:{change_id}",
                    source=str(row["source"]),
                    target=change_id,
                    kind="change",
                    properties={"kind": str(row["kind"])},
                )
            )

        for row in memory_rows:
            memory_id = str(row["id"])
            content = str(row.get("content") or "")
            nodes.append(
                GraphNode(
                    id=memory_id,
                    kind="memory",
                    label=content[:40] + ("…" if len(content) > 40 else ""),
                    properties={
                        "id": memory_id,
                        "session_id": str(row["source"]),
                        "content": content,
                        "scope": str(row.get("scope") or ""),
                        "confidence": float(str(row.get("confidence") or 0.5)),
                        "created_at": str(row.get("created_at") or ""),
                    },
                )
            )
            edges.append(
                GraphEdge(
                    id=f"remembered:{memory_id}",
                    source=str(row["source"]),
                    target=memory_id,
                    kind="memory",
                )
            )

        for row in compaction_rows:
            compaction_id = str(row["id"])
            nodes.append(
                GraphNode(
                    id=compaction_id,
                    kind="compaction",
                    label="checkpoint",
                    properties={
                        "id": compaction_id,
                        "session_id": str(row["source"]),
                        "objective": str(row.get("objective") or ""),
                        "completed": str(row.get("completed") or ""),
                        "next_move": str(row.get("next_move") or ""),
                        "tokens_saved": int(row.get("tokens_saved") or 0),
                        "created_at": str(row.get("created_at") or ""),
                    },
                )
            )
            edges.append(
                GraphEdge(
                    id=f"compacted:{compaction_id}",
                    source=str(row["source"]),
                    target=compaction_id,
                    kind="compaction",
                    properties={"tokens_saved": row["tokens_saved"]},
                )
            )

        edges.extend(
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
        )
        edges.extend(
            GraphEdge(
                id=str(row["id"]),
                source=str(row["source"]),
                target=str(row["target"]),
                kind="handoff",
                properties={
                    "id": str(row["id"]),
                    "kind": row["kind"],
                    "status": row["status"],
                    "summary": row["summary"],
                    "created_at": str(row.get("created_at") or ""),
                },
            )
            for row in handoff_rows
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
