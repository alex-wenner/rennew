from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


def new_identifier(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(UTC)


class SessionStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=200)


class Session(BaseModel):
    id: str
    title: str
    status: SessionStatus
    provider: str | None
    model: str | None
    created_at: datetime
    updated_at: datetime


class HandoffKind(StrEnum):
    CONTINUE = "continue"
    DELEGATE = "delegate"
    CONSULT = "consult"
    REVIEW = "review"
    RETURN = "return"
    TAKEOVER = "takeover"


class HandoffStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    RETURNED = "returned"
    COMPLETED = "completed"


class HandoffCreate(BaseModel):
    target_session_id: str
    kind: HandoffKind
    summary: str = Field(min_length=1, max_length=20_000)


class Handoff(BaseModel):
    id: str
    source_session_id: str
    target_session_id: str
    kind: HandoffKind
    status: HandoffStatus
    summary: str
    created_at: datetime


class OverlapKind(StrEnum):
    GOAL = "goal"
    CODE = "code"
    MEMORY = "memory"
    ARTIFACT = "artifact"
    TEMPORAL = "temporal"
    LINEAGE = "lineage"
    DECISION = "decision"


class SessionOverlapCreate(BaseModel):
    target_session_id: str
    kind: OverlapKind
    score: float = Field(ge=0, le=1)
    evidence: str = Field(min_length=1, max_length=10_000)
    inferred: bool = False


class SessionOverlap(SessionOverlapCreate):
    source_session_id: str


class CompactionCreate(BaseModel):
    objective: str = Field(min_length=1, max_length=2000)
    completed: str = Field(default="", max_length=10_000)
    active: str = Field(default="", max_length=10_000)
    blocked: str = Field(default="", max_length=10_000)
    next_move: str = Field(default="", max_length=5000)
    relevant_files: str = Field(default="", max_length=10_000)
    tokens_saved: int = Field(default=0, ge=0)


class Compaction(BaseModel):
    id: str
    session_id: str
    objective: str
    completed: str
    active: str
    blocked: str
    next_move: str
    relevant_files: str
    tokens_saved: int
    created_at: datetime

