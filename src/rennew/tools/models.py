from collections.abc import Awaitable, Callable

from pydantic import BaseModel, Field


class ToolContext(BaseModel):
    session_id: str
    repository_path: str


Tool = Callable[[ToolContext, dict[str, object]], Awaitable[dict[str, object]]]


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, object] = Field(default_factory=dict)
    permission: str
