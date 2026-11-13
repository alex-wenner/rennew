from pathlib import Path

from click.testing import CliRunner

from rennew.cli import cli

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "graph first" in result.output.lower()


def test_cli_session_create_list_and_graph_query(tmp_path: Path) -> None:
    db_path = tmp_path / "cli_test.lbdb"

    # Create session via CLI
    create_res = runner.invoke(
        cli,
        [
            "session",
            "create",
            "Build auth module",
            "--provider",
            "openai",
            "--model",
            "gpt-5.6-terra",
            "--database",
            str(db_path),
        ],
    )
    assert create_res.exit_code == 0
    assert "Created session" in create_res.output
    assert "Build auth module" in create_res.output

    # List sessions via CLI
    list_res = runner.invoke(cli, ["session", "list", "--database", str(db_path)])
    assert list_res.exit_code == 0
    assert "Build auth module" in list_res.output
    assert "openai" in list_res.output

    # Query graph via CLI
    query_res = runner.invoke(
        cli,
        [
            "graph",
            "query",
            "MATCH (s:Session) RETURN s.title AS title, s.model AS model",
            "--database",
            str(db_path),
        ],
    )
    assert query_res.exit_code == 0
    assert "Build auth module" in query_res.output
    assert "gpt-5.6-terra" in query_res.output
