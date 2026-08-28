from pathlib import Path

from rennew.config import load_settings


def test_load_settings_uses_project_file(tmp_path: Path) -> None:
    (tmp_path / "rennew.toml").write_text(
        '[server]\nport = 7444\n\n[storage]\npath = ".rennew/test.lbdb"\n',
        encoding="utf-8",
    )

    settings = load_settings(tmp_path)

    assert settings.server.port == 7444
    assert settings.storage.path == Path(".rennew/test.lbdb")
