from pathlib import Path

from fastapi.testclient import TestClient

from rennew.api.app import create_app
from rennew.config.models import RennewSettings, StorageSettings


def test_ui_serves_single_page_app(tmp_path: Path) -> None:
    settings = RennewSettings(storage=StorageSettings(path=tmp_path / "ui_test.lbdb"))

    with TestClient(create_app(settings)) as client:
        # Root route serves index.html
        response = client.get("/")
        assert response.status_code == 200
        assert "<div id=\"root\"></div>" in response.text

        # Static assets
        health_resp = client.get("/api/v1/health")
        assert health_resp.status_code == 200
        assert health_resp.json() == {"status": "ok"}
