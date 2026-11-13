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
    mode: str = Field(default="solo", max_length=50)
    workspace: str | None = Field(default=None, max_length=500)


class Session(BaseModel):
    id: str
    title: str
    status: SessionStatus
    provider: str | None
    model: str | None
    mode: str = "solo"
    workspace: str | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_reasoning_tokens: int = 0
    total_cost_usd: float = 0.0
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


class ToolCallRecord(BaseModel):
    id: str
    name: str
    input: dict[str, object] = Field(default_factory=dict)
    output: dict[str, object] | None = None
    status: str = "completed"
    duration_ms: int = 0


class TokenMetrics(BaseModel):
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total: int = 0
    cost_usd: float = 0.0


class SessionMessage(BaseModel):
    id: str
    session_id: str
    role: str  # "user" | "assistant" | "system"
    content: str
    reasoning: str | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    tokens: TokenMetrics = Field(default_factory=TokenMetrics)
    created_at: datetime


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1)
    mode: str = "solo"
    provider: str | None = None
    model: str | None = None
    reasoning_effort: str | None = None


class FileChange(BaseModel):
    id: str
    session_id: str
    message_id: str | None = None
    tool_call_id: str | None = None
    path: str
    kind: str  # "create" | "edit" | "delete"
    before_hash: str
    after_hash: str
    additions: int = 0
    deletions: int = 0
    diff: str
    created_at: datetime
