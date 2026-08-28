from pathlib import Path

from fastapi.testclient import TestClient

from rennew.api.app import create_app
from rennew.config.models import RennewSettings, StorageSettings


def test_sessions_handoffs_overlaps_and_graph_query(tmp_path: Path) -> None:
    settings = RennewSettings(storage=StorageSettings(path=tmp_path / "test.lbdb"))

    with TestClient(create_app(settings)) as client:
        builder = client.post(
            "/api/v1/sessions",
            json={"title": "Implement session graph", "provider": "openai", "model": "gpt"},
        )
        validator = client.post(
            "/api/v1/sessions",
            json={"title": "Validate session graph", "provider": "copilot", "model": "gpt"},
        )
        assert builder.status_code == 201
        assert validator.status_code == 201

        builder_id = builder.json()["id"]
        validator_id = validator.json()["id"]
        handoff = client.post(
            f"/api/v1/sessions/{builder_id}/handoffs",
            json={
                "target_session_id": validator_id,
                "kind": "review",
                "summary": "Review the candidate graph implementation.",
            },
        )
        overlap = client.post(
            f"/api/v1/sessions/{builder_id}/overlaps",
            json={
                "target_session_id": validator_id,
                "kind": "code",
                "score": 1,
                "evidence": "Both sessions touch graph.py.",
                "inferred": False,
            },
        )

        assert handoff.status_code == 201
        assert overlap.status_code == 201

        compaction = client.post(
            f"/api/v1/sessions/{builder_id}/compactions",
            json={
                "objective": "Implement session graph store and schema",
                "completed": "Added Ladybug graph tables and CRUD",
                "active": "Adding compaction tests",
                "blocked": "(none)",
                "next_move": "Verify with pytest",
                "relevant_files": "src/rennew/graph/ladybug.py: Graph store implementation",
                "tokens_saved": 45000,
            },
        )
        assert compaction.status_code == 201
        assert compaction.json()["tokens_saved"] == 45000

        compactions_list = client.get(f"/api/v1/sessions/{builder_id}/compactions")
        assert compactions_list.status_code == 200
        assert len(compactions_list.json()) == 1

        snapshot = client.get("/api/v1/graph/snapshot")
        assert snapshot.status_code == 200
        assert len(snapshot.json()["nodes"]) == 3
        assert {edge["kind"] for edge in snapshot.json()["edges"]} == {
            "compaction",
            "handoff",
            "overlap",
        }

        query = client.post(
            "/api/v1/graph/query",
            json={"cypher": "MATCH (s:Session) RETURN s.title AS title"},
        )
        assert query.status_code == 200
        assert {row["title"] for row in query.json()["rows"]} == {
            "Implement session graph",
            "Validate session graph",
        }


def test_graph_query_rejects_mutation(tmp_path: Path) -> None:
    settings = RennewSettings(storage=StorageSettings(path=tmp_path / "test.lbdb"))

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/graph/query",
            json={"cypher": "CREATE (:Session {id: 'unsafe'})"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "The graph console is read-only."
