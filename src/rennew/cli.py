import threading
import webbrowser
from pathlib import Path

import click
import httpx
import uvicorn

from rennew.api.app import create_app
from rennew.config.loader import load_settings
from rennew.graph.contracts import GraphQueryResult
from rennew.graph.ladybug import LadybugGraphStore, UnsafeGraphQueryError
from rennew.sessions.models import Session, SessionCreate
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


def _get_live_server_url(host: str, port: int) -> str | None:
    url = f"http://{host}:{port}/api/v1"
    try:
        resp = httpx.get(f"{url}/health", timeout=0.4)
        if resp.status_code == 200:
            return url
    except Exception:
        pass
    return None


@click.group()
@click.version_option(package_name="rennew")
def cli() -> None:
    """Rennew — renewed agent workflows. Simple, graph first."""


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
    live_url = (
        _get_live_server_url(settings.server.host, settings.server.port)
        if not database
        else None
    )

    if live_url:
        try:
            resp = httpx.post(f"{live_url}/graph/query", json={"cypher": cypher}, timeout=10)
            if resp.status_code != 200:
                detail = resp.json().get("detail", resp.text)
                raise click.ClickException(detail)
            result = GraphQueryResult.model_validate(resp.json())
        except httpx.HTTPError as err:
            raise click.ClickException(f"API request failed: {err}") from err
    else:
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
    live_url = (
        _get_live_server_url(settings.server.host, settings.server.port)
        if not database
        else None
    )

    if live_url:
        try:
            resp = httpx.get(f"{live_url}/sessions", timeout=5)
            if resp.status_code != 200:
                raise click.ClickException(resp.text)
            sessions = [Session.model_validate(item) for item in resp.json()]
        except httpx.HTTPError as err:
            raise click.ClickException(f"API request failed: {err}") from err
    else:
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
    live_url = (
        _get_live_server_url(settings.server.host, settings.server.port)
        if not database
        else None
    )

    if live_url:
        try:
            resp = httpx.post(
                f"{live_url}/sessions",
                json={"title": title, "provider": provider, "model": model},
                timeout=5,
            )
            if resp.status_code != 201:
                raise click.ClickException(resp.text)
            session = Session.model_validate(resp.json())
        except httpx.HTTPError as err:
            raise click.ClickException(f"API request failed: {err}") from err
    else:
        store = LadybugGraphStore(database or settings.storage.path)
        store.initialize()
        try:
            service = SessionService(store)
            session = service.create(SessionCreate(title=title, provider=provider, model=model))
        finally:
            store.close()

    click.echo(f"Created session {session.id}: {session.title}")


@cli.command("providers")
def providers_cmd() -> None:
    """List providers and connection status."""
    from rennew.providers.catalog import load_catalog
    from rennew.providers.registry import PROVIDER_META
    from rennew.security.credentials import CredentialStore

    catalog = load_catalog(Path.cwd() / ".rennew")
    status = CredentialStore().status(list(catalog.providers))
    click.echo(f"{'PROVIDER':<16} {'AUTH':<9} {'STATUS':<14} MODEL")
    click.echo("-" * 72)
    for provider_id, spec in catalog.providers.items():
        state = status.get(provider_id) or {}
        auth = PROVIDER_META.get(provider_id, {}).get("auth", "api_key")
        connected = f"connected/{state.get('source')}" if state.get("connected") else "-"
        model = spec.models[0] if spec.models else "-"
        click.echo(f"{provider_id:<16} {auth:<9} {connected:<14} {model}")


@cli.command("connect")
@click.argument("provider")
@click.option("--key", default=None, help="API key (api_key providers). Prompted if omitted.")
def connect_cmd(provider: str, key: str | None) -> None:
    """Connect a provider: paste a key, or walk the GitHub / ChatGPT sign-in flow."""
    import asyncio
    import webbrowser

    from rennew.cli_render import console
    from rennew.providers.registry import PROVIDER_META
    from rennew.security.credentials import CredentialStore

    meta = PROVIDER_META.get(provider)
    if meta is None:
        raise click.ClickException(f"Unknown provider '{provider}'. Run `ren providers`.")
    if meta["auth"] == "none":
        click.echo(f"{provider} uses a local endpoint; no API key is required.")
        return
    store = CredentialStore()

    if meta["auth"] == "github":
        from rennew.providers import copilot

        async def flow() -> None:
            start = await copilot.start_device_flow()
            console.print(
                f"Open [bold]{start.get('verification_uri', 'https://github.com/login/device')}[/bold] "
                f"and enter code [bold cyan]{start['user_code']}[/bold cyan]"
            )
            webbrowser.open(str(start.get("verification_uri", "https://github.com/login/device")))
            interval = int(start.get("interval", 5))
            while True:
                await asyncio.sleep(interval)
                result = await copilot.poll_device_flow(str(start["device_code"]))
                if result["status"] == "complete":
                    token = await copilot.exchange_copilot_token(str(result["access_token"]))
                    store.set_secret(
                        "copilot",
                        {
                            "github_token": result["access_token"],
                            "copilot_token": token.get("token"),
                            "expires_at": token.get("expires_at"),
                        },
                    )
                    console.print("[green]GitHub Copilot connected.[/green]")
                    return
                if result["status"] == "error":
                    raise click.ClickException(f"GitHub sign-in failed: {result.get('error')}")

        asyncio.run(flow())
        return

    if meta["auth"] == "oauth":
        from rennew.providers import chatgpt

        async def flow_oauth() -> None:
            login = chatgpt.ChatGPTLogin()
            await login.start_callback_server()
            url = login.authorize_url()
            console.print(f"Opening browser for ChatGPT sign-in…\n[dim]{url}[/dim]")
            webbrowser.open(url)
            try:
                result = await login.wait()
            finally:
                await login.close()
            store.set_secret("openai", result)
            console.print("[green]ChatGPT subscription connected.[/green]")

        try:
            asyncio.run(flow_oauth())
        except Exception as error:  # noqa: BLE001
            raise click.ClickException(str(error)) from error
        return

    value = key or click.prompt("API key", hide_input=True)
    store.set_api_key(provider, value.strip())
    click.echo(f"Connected {provider}.")

def _ensure_session_remote(
    base_url: str, session_id: str | None, title: str, provider: str | None, model: str | None
) -> str:
    if session_id:
        resp = httpx.get(f"{base_url}/sessions/{session_id}", timeout=5)
        if resp.status_code != 200:
            raise click.ClickException("Session not found.")
        return session_id
    resp = httpx.post(
        f"{base_url}/sessions",
        json={"title": title, "provider": provider, "model": model},
        timeout=5,
    )
    if resp.status_code != 201:
        raise click.ClickException(resp.text)
    return str(resp.json()["id"])


@cli.command("run")
@click.argument("prompt")
@click.option("--session", "session_id", default=None, help="Existing session id.")
@click.option("--title", default=None, help="Title when creating a session.")
@click.option("--provider", default=None)
@click.option("--model", default=None)
@click.option("--reasoning", is_flag=True, help="Show reasoning stream when available.")
def run_cmd(
    prompt: str,
    session_id: str | None,
    title: str | None,
    provider: str | None,
    model: str | None,
    reasoning: bool,
) -> None:
    """Run one agent turn. Uses the running server if there is one, else runs in-process."""
    import asyncio

    from rennew.cli_render import console, run_turn_remote, run_turn_rendered
    from rennew.sessions.models import PromptRequest

    settings = load_settings()
    request = PromptRequest(prompt=prompt, provider=provider, model=model)
    live_url = _get_live_server_url(settings.server.host, settings.server.port)

    try:
        if live_url:
            sid = _ensure_session_remote(live_url, session_id, title or prompt[:80], provider, model)
            asyncio.run(run_turn_remote(live_url, sid, request, show_reasoning=reasoning))
            console.print(f"[dim]session {sid} · via {live_url}[/dim]")
            return

        from rennew.runtime.container import RennewRuntime
        from rennew.sessions.models import SessionCreate

        runtime = RennewRuntime.open(settings)
        try:
            session = (
                runtime.sessions.get(session_id)
                if session_id
                else runtime.sessions.create(
                    SessionCreate(title=title or prompt[:80], provider=provider, model=model)
                )
            )
            async def run_local() -> None:
                await runtime.connect_mcp()
                try:
                    await run_turn_rendered(runtime, session.id, request, show_reasoning=reasoning)
                finally:
                    await runtime.mcp.close()

            asyncio.run(run_local())
            console.print(f"[dim]session {session.id}[/dim]")
        finally:
            runtime.close()
    except click.ClickException:
        raise
    except Exception as error:  # noqa: BLE001 - surface as CLI error
        raise click.ClickException(str(error)) from error


@cli.command("chat")
@click.option("--session", "session_id", default=None, help="Existing session id.")
@click.option("--provider", default=None)
@click.option("--model", default=None)
@click.option("--reasoning", is_flag=True, help="Show reasoning stream when available.")
def chat_cmd(session_id: str | None, provider: str | None, model: str | None, reasoning: bool) -> None:
    """Interactive agent chat. Type a prompt, or /quit to exit."""
    import asyncio

    from rich.prompt import Prompt

    from rennew.cli_render import console, run_turn_remote, run_turn_rendered
    from rennew.sessions.models import PromptRequest

    settings = load_settings()
    live_url = _get_live_server_url(settings.server.host, settings.server.port)
    runtime = None
    runner = asyncio.Runner()
    try:
        if live_url:
            sid = _ensure_session_remote(live_url, session_id, "CLI chat", provider, model)
            console.print(f"[bold]rennew[/bold] [dim]· {sid} · via server · /quit to exit[/dim]")
        else:
            from rennew.runtime.container import RennewRuntime
            from rennew.sessions.models import SessionCreate

            runtime = RennewRuntime.open(settings)
            runner.run(runtime.connect_mcp())
            session = (
                runtime.sessions.get(session_id)
                if session_id
                else runtime.sessions.create(
                    SessionCreate(title="CLI chat", provider=provider, model=model)
                )
            )
            sid = session.id
            console.print(f"[bold]rennew[/bold] [dim]· {sid} · /quit to exit[/dim]")

        while True:
            try:
                prompt = Prompt.ask("[cyan]›[/cyan]")
            except (EOFError, KeyboardInterrupt):
                break
            if prompt.strip() in {"/quit", "/exit", "quit", "exit"}:
                break
            if not prompt.strip():
                continue
            request = PromptRequest(prompt=prompt, provider=provider, model=model)
            try:
                if live_url:
                    runner.run(run_turn_remote(live_url, sid, request, show_reasoning=reasoning))
                else:
                    assert runtime is not None
                    runner.run(run_turn_rendered(runtime, sid, request, show_reasoning=reasoning))
            except Exception as error:  # noqa: BLE001 - keep the REPL alive
                console.print(f"[red]{error}[/red]")
    finally:
        if runtime is not None:
            runner.run(runtime.mcp.close())
            runtime.close()
        runner.close()
