import threading
import webbrowser
from pathlib import Path

import click
import uvicorn

from rennew.api.app import create_app
from rennew.config.loader import load_settings
from rennew.graph.ladybug import LadybugGraphStore, UnsafeGraphQueryError
from rennew.sessions.models import SessionCreate
from rennew.sessions.service import SessionService


def _serve(host: str, port: int, *, open_browser: bool, reload: bool = False) -> None:
    url = f"http://{host}:{port}"
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    if reload:
        uvicorn.run(
            "rennew.api.app:create_app",
            factory=True,
            host=host,
            port=port,
            reload=True,
        )
        return
    uvicorn.run(create_app(), host=host, port=port)


@click.group()
@click.version_option(package_name="rennew")
def cli() -> None:
    """Rennew: A local-first, session-centric coding agent runtime."""


@cli.command("ui")
@click.option("--host", help="Local interface host.", default=None)
@click.option("--port", type=int, help="Local interface port.", default=None)
@click.option("--no-open", is_flag=True, help="Do not open a browser.")
def ui(host: str | None, port: int | None, no_open: bool) -> None:
    """Start Rennew and open the local web interface."""
    settings = load_settings()
    _serve(
        host or settings.server.host,
        port if port is not None else settings.server.port,
        open_browser=settings.server.open_browser and not no_open,
    )


@cli.command("server")
@click.option("--host", help="Local API host.", default=None)
@click.option("--port", type=int, help="Local API port.", default=None)
@click.option("--reload", is_flag=True, help="Reload after Python changes.")
def server(host: str | None, port: int | None, reload: bool) -> None:
    """Start the local API server without opening a browser."""
    settings = load_settings()
    _serve(
        host or settings.server.host,
        port if port is not None else settings.server.port,
        open_browser=False,
        reload=reload,
    )


@cli.group("graph")
def graph_group() -> None:
    """Inspect and query the local session graph."""


@graph_group.command("query")
@click.argument("cypher")
@click.option(
    "--database",
    type=click.Path(path_type=Path),
    help="Override the graph database path.",
    default=None,
)
def graph_query(cypher: str, database: Path | None) -> None:
    """Execute a read-only Cypher query against the session graph."""
    settings = load_settings()
    store = LadybugGraphStore(database or settings.storage.path)
    store.initialize()
    try:
        result = store.query_readonly(cypher)
    except UnsafeGraphQueryError as error:
        raise click.ClickException(str(error)) from error
    finally:
        store.close()

    if not result.rows:
        click.echo("0 rows returned.")
        return

    # Print clean formatted table
    col_widths = {
        col: max(len(col), max(len(str(r.get(col, ""))) for r in result.rows))
        for col in result.columns
    }
    header = " | ".join(col.ljust(col_widths[col]) for col in result.columns)
    divider = "-+-".join("-" * col_widths[col] for col in result.columns)
    click.echo(header)
    click.echo(divider)
    for row in result.rows:
        line = " | ".join(str(row.get(col, "")).ljust(col_widths[col]) for col in result.columns)
        click.echo(line)


@cli.group("session")
def session_group() -> None:
    """Manage local sessions."""


@session_group.command("list")
@click.option(
    "--database",
    type=click.Path(path_type=Path),
    help="Override the graph database path.",
    default=None,
)
def session_list(database: Path | None) -> None:
    """List all sessions in the local graph."""
    settings = load_settings()
    store = LadybugGraphStore(database or settings.storage.path)
    store.initialize()
    try:
        service = SessionService(store)
        sessions = service.list_sessions()
    finally:
        store.close()

    if not sessions:
        click.echo("No sessions found.")
        return

    click.echo(f"{'ID':<36} | {'STATUS':<10} | {'PROVIDER':<12} | {'TITLE'}")
    click.echo("-" * 80)
    for s in sessions:
        click.echo(f"{s.id:<36} | {s.status.value:<10} | {s.provider or '-':<12} | {s.title}")


@session_group.command("create")
@click.argument("title")
@click.option("--provider", help="Provider name (e.g. openai, anthropic, bedrock, copilot).")
@click.option("--model", help="Model name.")
@click.option(
    "--database",
    type=click.Path(path_type=Path),
    help="Override the graph database path.",
    default=None,
)
def session_create(
    title: str,
    provider: str | None,
    model: str | None,
    database: Path | None,
) -> None:
    """Create a new session."""
    settings = load_settings()
    store = LadybugGraphStore(database or settings.storage.path)
    store.initialize()
    try:
        service = SessionService(store)
        session = service.create(SessionCreate(title=title, provider=provider, model=model))
    finally:
        store.close()

    click.echo(f"Created session {session.id}: {session.title}")
