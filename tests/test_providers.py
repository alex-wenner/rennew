from rennew.providers.catalog import build_registry, default_catalog
from rennew.providers.registry import PROVIDER_META, provider_is_connected


def test_shipped_provider_set() -> None:
    assert set(PROVIDER_META) == {
        "openai",
        "anthropic",
        "copilot",
        "bedrock",
        "opencode",
        "opencode-go",
    }
    assert PROVIDER_META["copilot"]["auth"] == "github"
    assert PROVIDER_META["openai"]["auth"] == "api_key|oauth"


def test_registry_builds_all_providers_and_reports_disconnected() -> None:
    registry = build_registry(default_catalog(), stored={}, persist=None)
    assert set(registry.list_ids()) == set(PROVIDER_META)
    for provider_id in registry.list_ids():
        provider = registry.get(provider_id)
        assert provider is not None
        assert provider_is_connected(provider) is False


def test_stored_credentials_connect_providers() -> None:
    stored = {
        "openai": "sk-test",
        "anthropic": "sk-ant-test",
        "copilot": {"github_token": "gho_x", "copilot_token": "tid", "expires_at": 9e12},
        "openai-chatgpt": {"access_token": "eyJ.x.y", "expires_at": 9e12},
    }
    registry = build_registry(default_catalog(), stored=stored, persist=None)
    assert provider_is_connected(registry.get("openai"))  # type: ignore[arg-type]
    assert provider_is_connected(registry.get("anthropic"))  # type: ignore[arg-type]
    assert provider_is_connected(registry.get("copilot"))  # type: ignore[arg-type]
    assert provider_is_connected(registry.get("bedrock")) is False  # type: ignore[arg-type]


def test_openai_accepts_chatgpt_oauth_secret() -> None:
    stored = {"openai": {"mode": "chatgpt", "access_token": "eyJ.x.y", "expires_at": 9e12}}
    registry = build_registry(default_catalog(), stored=stored, persist=None)
    provider = registry.get("openai")
    assert provider is not None
    assert provider_is_connected(provider)
    assert type(provider).__name__ == "ChatGPTProvider"
