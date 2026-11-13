"""Amazon Bedrock via bearer API key (AWS_BEARER_TOKEN_BEDROCK), using Bedrock's
OpenAI-compatible chat completions endpoint."""

from rennew.providers.contracts import ProviderCapabilities
from rennew.providers.openai_compatible import OpenAICompatibleProvider


class BedrockProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str | None, region: str = "us-east-1") -> None:
        super().__init__(
            name="bedrock",
            base_url=f"https://bedrock-runtime.{region}.amazonaws.com/openai/v1",
            api_key=api_key,
        )
        self.region = region

    def capabilities(self) -> ProviderCapabilities:
        caps = super().capabilities()
        caps.auth_env = ["AWS_BEARER_TOKEN_BEDROCK"]
        return caps
