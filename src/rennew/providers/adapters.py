from collections.abc import AsyncIterator

from rennew.providers.contracts import (
    CodingAgentBackend,
    CodingResult,
    CodingTask,
    ModelBackend,
    ModelEvent,
    ModelRequest,
    ProviderCapabilities,
)


class OpenAIModelBackend(ModelBackend):
    """OpenAI official API adapter (Chat & Responses).

    Documentation: https://platform.openai.com/docs/api-reference
    """

    name: str = "openai"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            documentation_url="https://platform.openai.com/docs/api-reference",
            documentation_version="2026.08",
            auth_methods=["api_key", "workload_identity"],
            streaming=True,
            tool_calling=True,
            parallel_tool_calls=True,
            reasoning_controls=True,
            structured_output=True,
            image_input=True,
            context_window=272_000,
            provider_options={
                "reasoning_effort": ["low", "medium", "high"],
                "service_tier": ["auto", "default", "flex"],
            },
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        # Yield start event for contract demonstration
        yield ModelEvent(kind="request.started", data={"model": request.model})


class AnthropicModelBackend(ModelBackend):
    """Anthropic official API adapter (Messages).

    Documentation: https://docs.anthropic.com/en/api/getting-started
    """

    name: str = "anthropic"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            documentation_url="https://docs.anthropic.com/en/api/getting-started",
            documentation_version="2026.08",
            auth_methods=["api_key", "anthropic_auth_token", "oidc_federation"],
            streaming=True,
            tool_calling=True,
            parallel_tool_calls=True,
            reasoning_controls=True,
            structured_output=True,
            image_input=True,
            context_window=200_000,
            provider_options={
                "thinking_budget": "integer",
                "prompt_caching": ["ephemeral"],
            },
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        yield ModelEvent(kind="request.started", data={"model": request.model})


class BedrockModelBackend(ModelBackend):
    """Amazon Bedrock adapter using the Converse API.

    Documentation: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html
    """

    name: str = "bedrock"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            documentation_url="https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html",
            documentation_version="2026.08",
            auth_methods=["aws_iam_profile", "aws_bearer_token", "environment"],
            streaming=True,
            tool_calling=True,
            parallel_tool_calls=True,
            reasoning_controls=True,
            structured_output=True,
            image_input=True,
            context_window=200_000,
            provider_options={
                "region": "string",
                "profile": "string",
                "endpoint": "string",
            },
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        yield ModelEvent(kind="request.started", data={"model": request.model})


class OpenCodeGoModelBackend(ModelBackend):
    """OpenCode Go & Zen subscription AI gateway adapter.

    Documentation: https://opencode.ai/docs/zen/ and https://opencode.ai/docs/go/
    """

    name: str = "opencode-go"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            documentation_url="https://opencode.ai/docs/go/",
            documentation_version="2026.08",
            auth_methods=["opencode_api_key", "opencode_go_subscription"],
            streaming=True,
            tool_calling=True,
            parallel_tool_calls=True,
            reasoning_controls=True,
            structured_output=True,
            image_input=True,
            context_window=256_000,
            provider_options={"endpoint_mode": ["zen", "go"]},
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        yield ModelEvent(kind="request.started", data={"model": request.model})


class CopilotAgentBackend(CodingAgentBackend):
    """GitHub Copilot CLI SDK coding-agent runtime backend.

    Documentation: https://github.com/github/copilot-sdk
    """

    name: str = "copilot"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            documentation_url="https://github.com/github/copilot-sdk",
            documentation_version="1.0+",
            auth_methods=["github_user_login", "oauth_app_token", "byok"],
            streaming=True,
            tool_calling=True,
            parallel_tool_calls=True,
            reasoning_controls=False,
            structured_output=True,
            image_input=False,
            context_window=128_000,
            provider_options={"cli_path": "string", "server_mode": "boolean"},
        )

    async def execute(self, task: CodingTask) -> CodingResult:
        return CodingResult(
            summary=f"Task completed with Copilot CLI runtime for session {task.session_id}",
            artifacts=[],
            raw={"status": "completed"},
        )


class CodexAgentBackend(CodingAgentBackend):
    """OpenAI Codex App-Server & SDK coding-agent runtime backend.

    Documentation: https://learn.chatgpt.com/codex/codex-sdk
    """

    name: str = "codex"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            documentation_url="https://learn.chatgpt.com/codex/codex-sdk",
            documentation_version="2026.08",
            auth_methods=["chatgpt_subscription", "api_key", "access_token"],
            streaming=True,
            tool_calling=True,
            parallel_tool_calls=True,
            reasoning_controls=True,
            structured_output=True,
            image_input=True,
            context_window=272_000,
            provider_options={
                "sandbox": ["read_only", "workspace_write", "full_access"],
                "codex_bin": "string",
            },
        )

    async def execute(self, task: CodingTask) -> CodingResult:
        return CodingResult(
            summary=f"Task completed with Codex app-server for session {task.session_id}",
            artifacts=[],
            raw={"status": "completed"},
        )
