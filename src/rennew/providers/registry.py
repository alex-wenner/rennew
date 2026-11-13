from collections.abc import Callable
from typing import Any

from rennew.providers.anthropic import AnthropicProvider
from rennew.providers.bedrock import BedrockProvider
from rennew.providers.chatgpt import ChatGPTProvider
from rennew.providers.contracts import ChatProvider
from rennew.providers.copilot import CopilotProvider
from rennew.providers.openai_compatible import OpenAICompatibleProvider
from rennew.providers.openai_responses import OpenAIResponsesProvider

# Provider ids Rennew ships with. `auth` drives the connect UI:
#   api_key  -> paste a key
#   github   -> GitHub device-code sign-in
#   oauth    -> browser OAuth (ChatGPT subscription); "api_key|oauth" offers both
PROVIDER_META: dict[str, dict[str, str]] = {
    "openai": {"label": "OpenAI", "auth": "api_key|oauth", "api": "openai-responses"},
    "anthropic": {"label": "Anthropic", "auth": "api_key", "api": "anthropic-messages"},
    "copilot": {"label": "GitHub Copilot", "auth": "github", "api": "openai-completions"},
    "bedrock": {"label": "Amazon Bedrock (API key)", "auth": "api_key", "api": "openai-completions"},
    "opencode": {"label": "OpenCode Zen", "auth": "api_key", "api": "openai-completions"},
    "opencode-go": {"label": "OpenCode Go", "auth": "api_key", "api": "openai-completions"},
    "openrouter": {"label": "OpenRouter", "auth": "api_key", "api": "openai-completions"},
    "groq": {"label": "Groq", "auth": "api_key", "api": "openai-completions"},
    "together": {"label": "Together AI", "auth": "api_key", "api": "openai-completions"},
    "ollama": {"label": "Ollama", "auth": "none", "api": "openai-completions"},
    "lmstudio": {"label": "LM Studio", "auth": "none", "api": "openai-completions"},
    "vllm": {"label": "vLLM", "auth": "none", "api": "openai-completions"},
}

KNOWN_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "opencode": "https://opencode.ai/zen/v1",
    "opencode-go": "https://opencode.ai/zen/go/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "together": "https://api.together.xyz/v1",
    "ollama": "http://127.0.0.1:11434/v1",
    "lmstudio": "http://127.0.0.1:1234/v1",
    "vllm": "http://127.0.0.1:8000/v1",
}

DEFAULT_ENV_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "bedrock": "AWS_BEARER_TOKEN_BEDROCK",
    "opencode": "OPENCODE_API_KEY",
    "opencode-go": "OPENCODE_API_KEY",
    "copilot": "GITHUB_TOKEN",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "together": "TOGETHER_API_KEY",
}

Persist = Callable[[str, dict[str, Any]], None]


def _resolve_api_key(provider_id: str, env: dict[str, str]) -> str | None:
    env_key = DEFAULT_ENV_KEYS.get(provider_id)
    if env_key and env.get(env_key):
        return env[env_key]
    generic = env.get(f"{provider_id.upper().replace('-', '_')}_API_KEY")
    return generic or None


def build_provider(
    spec: dict[str, object],
    env: dict[str, str],
    stored: dict[str, Any] | None = None,
    persist: Persist | None = None,
) -> ChatProvider:
    """Instantiate a provider from a spec. `stored` is the credential store contents."""
    provider_id = str(spec.get("id") or "")
    meta = PROVIDER_META.get(provider_id, {})
    api_format = str(spec.get("api") or meta.get("api") or "openai-completions")
    base_url = str(spec.get("base_url") or KNOWN_BASE_URLS.get(provider_id, ""))
    stored_value = (stored or {}).get(provider_id)
    context_window = _optional_int(spec.get("context_window"))

    if provider_id == "copilot":
        secret = stored_value if isinstance(stored_value, dict) else None
        if secret is None and env.get("GITHUB_TOKEN"):
            secret = {"github_token": env["GITHUB_TOKEN"]}
        return CopilotProvider(
            secret, persist=(lambda s: persist("copilot", s)) if persist else None
        )

    if provider_id == "openai" and isinstance(stored_value, dict):
        return ChatGPTProvider(
            stored_value, persist=(lambda s: persist("openai", s)) if persist else None
        )

    api_key_env = str(spec.get("api_key_env") or "")
    api_key = (
        stored_value
        if isinstance(stored_value, str) and stored_value
        else (env.get(api_key_env) if api_key_env else _resolve_api_key(provider_id, env))
    )

    if provider_id == "bedrock":
        return BedrockProvider(api_key, region=str(spec.get("region") or env.get("AWS_REGION") or "us-east-1"))

    if api_format == "anthropic-messages":
        return AnthropicProvider(name=provider_id, base_url=base_url or None, api_key=api_key)

    if api_format == "openai-responses":
        return OpenAIResponsesProvider(
            name=provider_id, base_url=base_url or None, api_key=api_key, context_window=context_window
        )

    return OpenAICompatibleProvider(
        name=provider_id,
        base_url=base_url,
        api_key=api_key,
        default_headers=_extract_headers(spec),
        supports_reasoning=bool(spec.get("supports_reasoning") or False),
        context_window=context_window,
    )


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(str(value))


def _extract_headers(spec: dict[str, object]) -> dict[str, str]:
    headers = spec.get("headers")
    if isinstance(headers, dict):
        return {str(key): str(value) for key, value in headers.items()}
    return {}


def provider_is_connected(provider: ChatProvider) -> bool:
    if PROVIDER_META.get(provider.name, {}).get("auth") == "none":
        return True
    connected = getattr(provider, "connected", None)
    if isinstance(connected, bool):
        return connected
    return bool(getattr(provider, "_api_key", None))


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ChatProvider] = {}

    def register(self, provider: ChatProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, provider_id: str) -> ChatProvider | None:
        return self._providers.get(provider_id)

    def list_ids(self) -> list[str]:
        return list(self._providers)

    def describe(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for provider_id, provider in self._providers.items():
            caps = provider.capabilities()
            meta = PROVIDER_META.get(provider_id, {})
            result.append(
                {
                    "id": provider_id,
                    "label": meta.get("label", provider_id),
                    "auth": meta.get("auth", "api_key"),
                    "streaming": caps.streaming,
                    "tool_calling": caps.tool_calling,
                    "reasoning": caps.reasoning,
                    "context_window": caps.context_window,
                }
            )
        return result
