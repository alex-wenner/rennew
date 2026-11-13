import json

import httpx

from rennew.providers.contracts import ChatProvider
from rennew.providers.anthropic import AnthropicProvider
from rennew.providers.openai_compatible import OpenAICompatibleProvider
from rennew.providers.openai_responses import OpenAIResponsesProvider


async def discover_models(provider: ChatProvider) -> list[str]:
    """Ask the provider for its current model list. Falls back to configured defaults."""
    prepare = getattr(provider, "prepare", None)
    if callable(prepare):
        try:
            await prepare()
        except Exception:  # noqa: BLE001 - not signed in yet
            return []
    if isinstance(provider, AnthropicProvider):
        return await _anthropic_models(provider)
    if isinstance(provider, (OpenAICompatibleProvider, OpenAIResponsesProvider)):
        return await _openai_models(provider)
    return []


async def _openai_models(provider: ChatProvider) -> list[str]:
    base_url = getattr(provider, "_base_url", "")
    api_key = getattr(provider, "_api_key", None)
    if not base_url:
        return []
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    headers.update(getattr(provider, "_headers", {}) if isinstance(getattr(provider, "_headers", None), dict) else {})
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{base_url}/models", headers=headers)
            if response.status_code != 200:
                return []
            payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return []
    models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    ids = [str(item.get("id")) for item in models if isinstance(item, dict) and item.get("id")]
    return sorted(ids)


async def _anthropic_models(provider: ChatProvider) -> list[str]:
    base_url = getattr(provider, "_base_url", "https://api.anthropic.com")
    api_key = getattr(provider, "_api_key", None)
    headers = {"anthropic-version": "2023-06-01"}
    if api_key:
        headers["x-api-key"] = api_key
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{base_url}/v1/models", headers=headers)
            if response.status_code != 200:
                return []
            payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return []
    models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    ids = [str(item.get("id")) for item in models if isinstance(item, dict) and item.get("id")]
    return sorted(ids)
