import json
import os
import sys
from pathlib import Path

from platformdirs import user_data_path


def default_credentials_path() -> Path:
    # Prefer ~/.rennew/credentials.json or system user data directory
    home_rennew = Path.home() / ".rennew" / "credentials.json"
    if home_rennew.parent.exists():
        return home_rennew
    return user_data_path("rennew", appauthor=False) / "credentials.json"


class CredentialStore:
    """Manages provider API keys and tokens locally in a simple JSON file on the user's machine.

    Zero cloud syncing, zero telemetry, zero external dependencies.
    """

    DEFAULT_ENV_MAP: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "bedrock": "AWS_BEARER_TOKEN_BEDROCK",
        "copilot": "GITHUB_COPILOT_TOKEN",
        "codex": "CODEX_ACCESS_TOKEN",
        "opencode-go": "OPENCODE_API_KEY",
    }

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_credentials_path()

    def _read_all(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_all(self, data: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Restrict permissions on POSIX
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

    def get_api_key(self, provider: str, env_var: str | None = None) -> str | None:
        """Fetch API key from local machine storage, falling back to local environment variables."""
        data = self._read_all()
        stored = data.get(provider)
        if stored:
            return stored
        var_name = env_var or self.DEFAULT_ENV_MAP.get(provider)
        if var_name and var_name in os.environ:
            return os.environ[var_name]
        return None

    def set_api_key(self, provider: str, key: str) -> None:
        """Store an API key directly on the user's machine."""
        data = self._read_all()
        data[provider] = key
        self._write_all(data)

    def delete_api_key(self, provider: str) -> None:
        """Remove an API key from local storage."""
        data = self._read_all()
        if provider in data:
            del data[provider]
            self._write_all(data)
