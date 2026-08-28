from collections.abc import AsyncIterator
from typing import Protocol

from pydantic import BaseModel, Field


class ProviderCapabilities(BaseModel):
    documentation_url: str = ""
    documentation_version: str = "2026-latest"
    auth_methods: list[str] = Field(default_factory=list)
    streaming: bool = False
    tool_calling: bool = False
    parallel_tool_calls: bool = False
    reasoning_controls: bool = False
    structured_output: bool = False
    image_input: bool = False
    context_window: int | None = None
    provider_options: dict[str, object] = Field(default_factory=dict)


class ModelRequest(BaseModel):
    model: str
    messages: list[dict[str, object]]
    tools: list[dict[str, object]] = Field(default_factory=list)
    options: dict[str, object] = Field(default_factory=dict)


class ModelEvent(BaseModel):
    kind: str
    data: dict[str, object] = Field(default_factory=dict)


class CodingTask(BaseModel):
    session_id: str
    instruction: str
    repository_path: str
    options: dict[str, object] = Field(default_factory=dict)


class CodingResult(BaseModel):
    summary: str
    artifacts: list[str] = Field(default_factory=list)
    raw: dict[str, object] = Field(default_factory=dict)


class ModelBackend(Protocol):
    name: str

    def capabilities(self) -> ProviderCapabilities: ...

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]: ...


class CodingAgentBackend(Protocol):
    name: str

    def capabilities(self) -> ProviderCapabilities: ...

    async def execute(self, task: CodingTask) -> CodingResult: ...
