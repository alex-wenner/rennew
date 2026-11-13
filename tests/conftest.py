from pathlib import Path

import pytest

from rennew.providers import modelsdev
from rennew.providers.registry import DEFAULT_ENV_KEYS
from rennew.runtime.container import RennewRuntime
from rennew.security import credentials


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never use personal credentials, MCP servers, or remote metadata."""
    monkeypatch.setattr(credentials, "default_credentials_path", lambda: tmp_path / "keys.json")
    for name in DEFAULT_ENV_KEYS.values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(RennewRuntime, "mcp_configs", lambda self: [])

    async def offline_refresh(force: bool = False) -> dict[str, object]:
        return {}

    monkeypatch.setattr(modelsdev, "refresh", offline_refresh)
