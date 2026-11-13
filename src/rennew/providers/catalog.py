import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from rennew.providers.contracts import ChatProvider
from rennew.providers.registry import (
    KNOWN_BASE_URLS,
    PROVIDER_META,
    Persist,
    ProviderRegistry,
    build_provider,
)


class ProviderSpec(BaseModel):
    id: str
    api: str = "openai-completions"
    base_url: str = ""
    api_key_env: str = ""
    region: str = ""
    context_window: int | None = None
    supports_reasoning: bool = False
    headers: dict[str, str] = Field(default_factory=dict)
    models: list[str] = Field(default_factory=list)


class ProviderCatalog(BaseModel):
    providers: dict[str, ProviderSpec] = Field(default_factory=dict)
    default_provider: str | None = None
    default_model: str | None = None


def default_catalog() -> ProviderCatalog:
    specs: dict[str, ProviderSpec] = {}
    for provider_id, meta in PROVIDER_META.items():
        specs[provider_id] = ProviderSpec(
            id=provider_id,
            api=meta["api"],
            base_url=KNOWN_BASE_URLS.get(provider_id, ""),
        )
    return ProviderCatalog(providers=specs, default_provider=None, default_model=None)


def load_catalog(config_dir: Path | None = None) -> ProviderCatalog:
    """Merge user `providers.json` over defaults. Custom OpenAI-compatible or
    Anthropic-compatible endpoints can be added here."""
    catalog = default_catalog()
    if config_dir is None:
        return catalog
    providers_file = config_dir / "providers.json"
    if not providers_file.exists():
        return catalog
    try:
        raw = json.loads(providers_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return catalog
    for provider_id, spec in (raw.get("providers") or {}).items():
        data = dict(spec)
        data["id"] = provider_id
        existing = catalog.providers.get(provider_id)
        merged = {**(existing.model_dump() if existing else {}), **data}
        catalog.providers[provider_id] = ProviderSpec.model_validate(merged)
    if raw.get("default_provider"):
        catalog.default_provider = str(raw["default_provider"])
    if raw.get("default_model"):
        catalog.default_model = str(raw["default_model"])
    return catalog


def build_registry(
    catalog: ProviderCatalog | None = None,
    stored: dict[str, Any] | None = None,
    persist: Persist | None = None,
) -> ProviderRegistry:
    registry = ProviderRegistry()
    catalog = catalog or load_catalog()
    env = dict(os.environ)
    for spec in catalog.providers.values():
        provider: ChatProvider = build_provider(spec.model_dump(), env, stored, persist)
        registry.register(provider)
    return registry
