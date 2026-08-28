import tomllib
from pathlib import Path

from rennew.config.models import RennewSettings


def load_settings(project_dir: Path | None = None) -> RennewSettings:
    root = project_dir or Path.cwd()
    config_path = root / "rennew.toml"
    if not config_path.exists():
        return RennewSettings()

    with config_path.open("rb") as config_file:
        return RennewSettings.model_validate(tomllib.load(config_file))
