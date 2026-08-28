from rennew.providers import create_default_registry


def test_default_providers_registered_with_docs() -> None:
    registry = create_default_registry()
    names = registry.names()

    assert "openai" in names["models"]
    assert "anthropic" in names["models"]
    assert "bedrock" in names["models"]
    assert "opencode-go" in names["models"]
    assert "copilot" in names["agents"]
    assert "codex" in names["agents"]

    # Verify documentation URL citations
    openai_cap = registry.model("openai").capabilities()
    assert "https://platform.openai.com" in openai_cap.documentation_url

    bedrock_cap = registry.model("bedrock").capabilities()
    assert "docs.aws.amazon.com" in bedrock_cap.documentation_url

    copilot_cap = registry.agent("copilot").capabilities()
    assert "github.com/github/copilot-sdk" in copilot_cap.documentation_url
