from pathlib import Path

from platformdirs import user_data_path
from pydantic import BaseModel, Field


def default_graph_path() -> Path:
    return user_data_path("rennew", appauthor=False) / "rennew.lbdb"


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=7337, ge=0, le=65535)
    open_browser: bool = True


class StorageSettings(BaseModel):
    path: Path = Field(default_factory=default_graph_path)


class RennewSettings(BaseModel):
    server: ServerSettings = Field(default_factory=ServerSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
