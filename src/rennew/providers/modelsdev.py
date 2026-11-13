"""Live model metadata from the models.dev catalog (the same catalog OpenCode uses).
Costs and context windows are looked up here first so Rennew never has to maintain
a price table; the local table in pricing.py is only a fallback."""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("rennew.modelsdev")

CATALOG_URL = "https://models.dev/api.json"
CACHE_TTL = 6 * 3600

PROVIDER_ALIASES = {
    "openai": ["openai"],
    "anthropic": ["anthropic"],
    "copilot": ["github-copilot", "copilot"],
    "bedrock": ["amazon-bedrock", "bedrock"],
    "opencode": ["opencode"],
    "opencode-go": ["opencode"],
}

_catalog: dict[str, Any] = {}
_catalog_loaded_at = 0.0
_lock: asyncio.Lock | None = None


def _cache_path() -> Path:
    return Path.home() / ".rennew" / "models.dev.json"


def _load_disk() -> dict[str, Any]:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(raw.get("fetched_at", 0)) < CACHE_TTL:
            return dict(raw.get("catalog") or {})
    except (json.JSONDecodeError, ValueError):
        pass
    return {}


def loaded() -> bool:
    return bool(_catalog)


async def refresh(force: bool = False) -> dict[str, Any]:
    global _catalog, _catalog_loaded_at, _lock
    if _lock is None:
        _lock = asyncio.Lock()
    async with _lock:
        if _catalog and not force and time.time() - _catalog_loaded_at < 3600:
            return _catalog
        if not _catalog:
            _catalog = _load_disk()
            _catalog_loaded_at = time.time()
            if _catalog:
                return _catalog
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(CATALOG_URL)
                response.raise_for_status()
                data = response.json()
            if isinstance(data, dict):
                _catalog = data
                _catalog_loaded_at = time.time()
                path = _cache_path()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps({"fetched_at": time.time(), "catalog": data}), encoding="utf-8"
                )
        except Exception as error:  # noqa: BLE001
            log.warning("models.dev refresh failed: %s", error)
    return _catalog


class ModelMeta:
    def __init__(self, raw: dict[str, Any]) -> None:
        cost = raw.get("cost") or {}
        limit = raw.get("limit") or {}
        self.input_per_m = float(cost.get("input") or 0)
        self.output_per_m = float(cost.get("output") or 0)
        self.cache_read_per_m = float(cost.get("cache_read") or 0)
        self.cache_write_per_m = float(cost.get("cache_write") or 0)
        self.context = int(limit.get("context") or 0) or None
        self.name = str(raw.get("name") or raw.get("id") or "")
        self.reasoning = bool(raw.get("reasoning"))


def lookup(provider_id: str | None, model_id: str) -> ModelMeta | None:
    """Find metadata for a model: exact provider first, then scan all providers."""
    if not _catalog or not model_id:
        return None
    candidates: list[str] = []
    if provider_id:
        candidates.extend(PROVIDER_ALIASES.get(provider_id, [provider_id]))
    for alias in candidates:
        provider = _catalog.get(alias)
        if isinstance(provider, dict):
            entry = (provider.get("models") or {}).get(model_id)
            if isinstance(entry, dict):
                return ModelMeta(entry)
    for provider in _catalog.values():
        if not isinstance(provider, dict):
            continue
        entry = (provider.get("models") or {}).get(model_id)
        if isinstance(entry, dict):
            return ModelMeta(entry)
    return None
