from collections.abc import AsyncIterator
from typing import Any, Protocol

from pydantic import BaseModel, Field


class ToolSchema(BaseModel):
    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class ProviderMessage(BaseModel):
    role: str
    content: str = ""
    reasoning: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


class ChatRequest(BaseModel):
    model: str
    messages: list[ProviderMessage]
    tools: list[ToolSchema] = Field(default_factory=list)
    temperature: float | None = None
    max_tokens: int | None = None
    reasoning_effort: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class StreamDelta(BaseModel):
    kind: str  # "text" | "reasoning" | "tool_call" | "usage" | "finish" | "error"
    text: str = ""
    tool_call: dict[str, Any] | None = None
    usage: dict[str, int] | None = None
    finish_reason: str | None = None
    error: str | None = None


class ProviderCapabilities(BaseModel):
    streaming: bool = True
    tool_calling: bool = True
    parallel_tool_calls: bool = False
    reasoning: bool = False
    context_window: int | None = None
    auth_env: list[str] = Field(default_factory=list)


class ChatProvider(Protocol):
    """A pluggable model provider. Implement this to add a backend to Rennew."""

    name: str

    def capabilities(self) -> ProviderCapabilities: ...

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamDelta]: ...


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0
