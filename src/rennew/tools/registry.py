from dataclasses import dataclass

from rennew.tools.models import Tool, ToolDefinition


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    definition: ToolDefinition
    handler: Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, definition: ToolDefinition, handler: Tool) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool already registered: {definition.name}")
        self._tools[definition.name] = RegisteredTool(definition, handler)

    def get(self, name: str) -> RegisteredTool:
        return self._tools[name]

    def definitions(self) -> list[ToolDefinition]:
        return [item.definition for item in self._tools.values()]
