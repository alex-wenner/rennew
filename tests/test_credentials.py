from pathlib import Path

import pytest

from rennew.security.credentials import CredentialStore


def test_local_credential_storage(tmp_path: Path) -> None:
    creds_file = tmp_path / "credentials.json"
    store = CredentialStore(creds_file)

    assert store.get_api_key("openai") is None

    store.set_api_key("openai", "sk-test-local-123")
    assert store.get_api_key("openai") == "sk-test-local-123"

    store.delete_api_key("openai")
    assert store.get_api_key("openai") is None


def test_credential_store_env_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    creds_file = tmp_path / "credentials.json"
    store = CredentialStore(creds_file)

    # Test env fallback when no local key is stored
    monkeypatch.setenv("OPENAI_API_KEY", "env-key-abc")
    assert store.get_api_key("openai") == "env-key-abc"

    # Stored local key takes precedence over env
    store.set_api_key("openai", "stored-local-xyz")
    assert store.get_api_key("openai") == "stored-local-xyz"
