import json
import os
import sys
from pathlib import Path
from typing import Any

from platformdirs import user_data_path


def default_credentials_path() -> Path:
    home_rennew = Path.home() / ".rennew" / "credentials.json"
    if home_rennew.parent.exists():
        return home_rennew
    return user_data_path("rennew", appauthor=False) / "credentials.json"


class CredentialStore:
    """Local credential storage. Values are either a plain API key string or a JSON
    object for OAuth-style providers (access/refresh tokens, expiry, account ids)."""

    DEFAULT_ENV_MAP: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "bedrock": "AWS_BEARER_TOKEN_BEDROCK",
        "opencode": "OPENCODE_API_KEY",
        "opencode-go": "OPENCODE_API_KEY",
        "copilot": "GITHUB_TOKEN",
    }

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_credentials_path()

    def _read_all(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_all(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        if sys.platform != "win32":
            try:
                os.chmod(temp_path, 0o600)
            except OSError:
                pass
        temp_path.replace(self._path)
        if sys.platform != "win32":
            try:
                os.chmod(self._path, 0o600)
            except OSError:
                pass

    # --- API keys -------------------------------------------------------------

    def get_api_key(self, provider: str, env_var: str | None = None) -> str | None:
        stored = self._read_all().get(provider)
        if isinstance(stored, str) and stored:
            return stored
        var_name = env_var or self.DEFAULT_ENV_MAP.get(provider)
        if var_name and os.environ.get(var_name):
            return os.environ[var_name]
        return None

    def set_api_key(self, provider: str, key: str) -> None:
        data = self._read_all()
        data[provider] = key
        self._write_all(data)

    def delete_api_key(self, provider: str) -> None:
        data = self._read_all()
        if provider in data:
            del data[provider]
            self._write_all(data)

    # --- OAuth-style secrets --------------------------------------------------

    def get_secret(self, provider: str) -> dict[str, Any] | None:
        stored = self._read_all().get(provider)
        return stored if isinstance(stored, dict) else None

    def set_secret(self, provider: str, secret: dict[str, Any]) -> None:
        data = self._read_all()
        data[provider] = secret
        self._write_all(data)

    def stored(self) -> dict[str, Any]:
        return self._read_all()

    def status(self, provider_ids: list[str] | None = None) -> dict[str, dict[str, object]]:
        stored = self._read_all()
        ids = provider_ids or sorted(set(stored) | set(self.DEFAULT_ENV_MAP))
        result: dict[str, dict[str, object]] = {}
        for provider_id in ids:
            env_name = self.DEFAULT_ENV_MAP.get(provider_id)
            value = stored.get(provider_id)
            in_store = bool(value)
            in_env = bool(env_name and os.environ.get(env_name))
            if in_store:
                source = "oauth" if isinstance(value, dict) else "store"
            elif in_env:
                source = "env"
            else:
                source = None
            result[provider_id] = {"connected": bool(source), "source": source}
        return result
