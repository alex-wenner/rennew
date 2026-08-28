from rennew.providers.adapters import (
    AnthropicModelBackend,
    BedrockModelBackend,
    CodexAgentBackend,
    CopilotAgentBackend,
    OpenAIModelBackend,
    OpenCodeGoModelBackend,
)
from rennew.providers.contracts import CodingAgentBackend, ModelBackend, ProviderCapabilities
from rennew.providers.registry import ProviderRegistry


def create_default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register_model(OpenAIModelBackend())
    registry.register_model(AnthropicModelBackend())
    registry.register_model(BedrockModelBackend())
    registry.register_model(OpenCodeGoModelBackend())
    registry.register_agent(CopilotAgentBackend())
    registry.register_agent(CodexAgentBackend())
    return registry


__all__ = [
    "AnthropicModelBackend",
    "BedrockModelBackend",
    "CodexAgentBackend",
    "CodingAgentBackend",
    "CopilotAgentBackend",
    "ModelBackend",
    "OpenAIModelBackend",
    "OpenCodeGoModelBackend",
    "ProviderCapabilities",
    "ProviderRegistry",
    "create_default_registry",
]
