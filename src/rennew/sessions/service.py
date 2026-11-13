from rennew.graph.contracts import GraphStore
from rennew.sessions.models import (
    Compaction,
    CompactionCreate,
    Handoff,
    HandoffCreate,
    HandoffStatus,
    Session,
    SessionCreate,
    SessionMessage,
    SessionOverlap,
    SessionOverlapCreate,
    SessionStatus,
    new_identifier,
    utc_now,
)


class SessionNotFoundError(LookupError):
    pass


class SessionService:
    def __init__(self, store: GraphStore) -> None:
        self._store = store

    def create(self, command: SessionCreate) -> Session:
        now = utc_now()
        session = Session(
            id=new_identifier("ses"),
            title=command.title,
            status=SessionStatus.ACTIVE,
            provider=command.provider,
            model=command.model,
            mode=command.mode,
            workspace=command.workspace,
            created_at=now,
            updated_at=now,
        )
        return self._store.create_session(session)

    def list_sessions(self) -> list[Session]:
        return self._store.list_sessions()

    def get(self, session_id: str) -> Session:
        session = self._store.get_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def list_messages(self, session_id: str) -> list[SessionMessage]:
        self.get(session_id)
        return self._store.list_messages(session_id)

    def add_message(self, message: SessionMessage) -> SessionMessage:
        return self._store.create_message(message)

    def handoff(self, source_session_id: str, command: HandoffCreate) -> Handoff:
        self.get(source_session_id)
        self.get(command.target_session_id)
        handoff = Handoff(
            id=new_identifier("hnd"),
            source_session_id=source_session_id,
            target_session_id=command.target_session_id,
            kind=command.kind,
            status=HandoffStatus.PENDING,
            summary=command.summary,
            created_at=utc_now(),
        )
        return self._store.create_handoff(handoff)

    def overlap(
        self, source_session_id: str, command: SessionOverlapCreate
    ) -> SessionOverlap:
        self.get(source_session_id)
        self.get(command.target_session_id)
        overlap = SessionOverlap(source_session_id=source_session_id, **command.model_dump())
        return self._store.create_overlap(overlap)

    def compact(self, session_id: str, command: CompactionCreate) -> Compaction:
        self.get(session_id)
        compaction = Compaction(
            id=new_identifier("cmp"),
            session_id=session_id,
            objective=command.objective,
            completed=command.completed,
            active=command.active,
            blocked=command.blocked,
            next_move=command.next_move,
            relevant_files=command.relevant_files,
            tokens_saved=command.tokens_saved,
            created_at=utc_now(),
        )
        return self._store.create_compaction(compaction)

    def list_compactions(self, session_id: str) -> list[Compaction]:
        self.get(session_id)
        return self._store.list_compactions(session_id)
