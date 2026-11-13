import asyncio
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rennew.api.dependencies import get_runtime
from rennew.providers.discovery import discover_models
from rennew.providers.registry import DEFAULT_ENV_KEYS, PROVIDER_META, provider_is_connected
from rennew.runtime.container import RennewRuntime

router = APIRouter(prefix="/runtime", tags=["runtime"])
RuntimeDependency = Annotated[RennewRuntime, Depends(get_runtime)]


class ConnectProviderRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=4000)



@router.get("/providers")
async def list_providers(runtime: RuntimeDependency, live: bool = False) -> list[dict[str, Any]]:
    from rennew.providers import modelsdev

    await modelsdev.refresh()
    described = runtime.agent.registry.describe()
    status = runtime.credentials.status([str(p["id"]) for p in described])
    async def discover(provider_id: str) -> tuple[str, list[str]]:
        backend = runtime.agent.registry.get(provider_id)
        if not live or backend is None or not provider_is_connected(backend):
            return provider_id, []
        try:
            return provider_id, await discover_models(backend)
        except Exception:
            return provider_id, []

    discovered_models = dict(await asyncio.gather(*(discover(str(p["id"])) for p in described)))
    enriched: list[dict[str, Any]] = []
    for provider in described:
        provider_id = str(provider["id"])
        backend = runtime.agent.registry.get(provider_id)
        spec = runtime.agent.catalog.providers.get(provider_id)
        model_ids = list(spec.models) if spec is not None else []
        connected = backend is not None and provider_is_connected(backend)
        source = (status.get(provider_id) or {}).get("source")
        discovered = discovered_models[provider_id]
        if discovered:
            model_ids = list(dict.fromkeys([*model_ids, *discovered]))
        if PROVIDER_META.get(provider_id, {}).get("auth") == "none":
            connected = bool(discovered or model_ids)
            source = "local" if connected else None
        models: list[dict[str, Any]] = []
        for model_id in model_ids:
            meta = modelsdev.lookup(provider_id, model_id)
            models.append(
                {
                    "id": model_id,
                    "name": meta.name if meta else model_id,
                    "input_per_m": meta.input_per_m if meta else None,
                    "output_per_m": meta.output_per_m if meta else None,
                    "context": meta.context if meta else None,
                    "reasoning": meta.reasoning if meta else False,
                }
            )
        enriched.append(
            {
                **provider,
                "models": models,
                "api": spec.api if spec else PROVIDER_META.get(provider_id, {}).get("api"),
                "connected": connected,
                "auth_source": source,
                "auth_env": DEFAULT_ENV_KEYS.get(provider_id),
            }
        )
    return enriched


@router.put("/providers/{provider_id}/credentials")
async def connect_provider(
    provider_id: str, body: ConnectProviderRequest, runtime: RuntimeDependency
) -> dict[str, object]:
    if provider_id not in runtime.agent.registry.list_ids():
        raise HTTPException(status_code=404, detail="Unknown provider.")
    if not body.api_key.strip():
        raise HTTPException(status_code=422, detail="API key must not be blank.")
    runtime.credentials.set_api_key(provider_id, body.api_key.strip())
    runtime.reload_providers()
    return {"id": provider_id, "connected": True, "source": "store"}


@router.delete("/providers/{provider_id}/credentials")
def disconnect_provider(provider_id: str, runtime: RuntimeDependency) -> dict[str, object]:
    if provider_id not in runtime.agent.registry.list_ids():
        raise HTTPException(status_code=404, detail="Unknown provider.")
    runtime.credentials.delete_api_key(provider_id)
    runtime.reload_providers()
    backend = runtime.agent.registry.get(provider_id)
    return {"id": provider_id, "connected": bool(backend and provider_is_connected(backend))}


# --- sign-in flows (server-side; browser only starts + polls) ------------------------


@router.post("/auth/github/start")
async def github_start(runtime: RuntimeDependency) -> dict[str, Any]:
    try:
        return await runtime.auth.github_start()
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"GitHub device flow failed: {error}") from error


@router.get("/auth/github/status")
def github_status(runtime: RuntimeDependency) -> dict[str, Any]:
    return dict(runtime.auth.github_status())


@router.post("/auth/openai/start")
async def openai_start(runtime: RuntimeDependency) -> dict[str, Any]:
    try:
        return await runtime.auth.openai_start()
    except OSError as error:
        raise HTTPException(status_code=409, detail=f"Callback port busy: {error}") from error


@router.get("/auth/openai/status")
def openai_status(runtime: RuntimeDependency) -> dict[str, Any]:
    return dict(runtime.auth.openai_status())


# --- tools, skills, MCP --------------------------------------------------------------


class MCPServerBody(BaseModel):
    name: str = Field(min_length=1, max_length=60, pattern=r"^[a-zA-Z0-9_.-]+$")
    command: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


@router.get("/tools")
def describe_tools(runtime: RuntimeDependency) -> dict[str, Any]:
    return dict(runtime.describe_tools())


@router.post("/mcp/servers", status_code=201)
async def add_mcp_server(body: MCPServerBody, runtime: RuntimeDependency) -> dict[str, Any]:
    runtime.add_mcp_server(body.name, body.command, body.args, body.env)
    await runtime.connect_mcp()
    return dict(runtime.describe_tools()["mcp"])


@router.delete("/mcp/servers/{name}")
async def remove_mcp_server(name: str, runtime: RuntimeDependency) -> dict[str, Any]:
    runtime.remove_mcp_server(name)
    await runtime.connect_mcp()
    return dict(runtime.describe_tools()["mcp"])


@router.post("/mcp/reconnect")
async def reconnect_mcp(runtime: RuntimeDependency) -> dict[str, Any]:
    await runtime.connect_mcp()
    return dict(runtime.describe_tools()["mcp"])

# --- graph-adjacent listings -------------------------------------------------------


@router.get("/mcp")
def mcp_status(runtime: RuntimeDependency) -> list[dict[str, object]]:
    if runtime.agent.mcp is None:
        return []
    return runtime.agent.mcp.status()


@router.get("/changes")
def list_all_changes(runtime: RuntimeDependency) -> list[dict[str, Any]]:
    return [change.model_dump(mode="json") for change in runtime.graph.list_file_changes()]


@router.get("/changes/{change_id}")
def get_change(change_id: str, runtime: RuntimeDependency) -> dict[str, Any]:
    change = runtime.graph.get_file_change(change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found.")
    return change.model_dump(mode="json")


@router.get("/memories")
def list_memories(runtime: RuntimeDependency) -> list[dict[str, Any]]:
    rows = runtime.graph.list_memories(limit=500)
    return [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()} for r in rows]


@router.get("/events")
async def event_stream(runtime: RuntimeDependency) -> StreamingResponse:
    async def generate() -> Any:
        queue = runtime.events.attach()
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            runtime.events.detach(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/health")
def runtime_health(runtime: RuntimeDependency) -> dict[str, object]:
    return {
        "status": "ok",
        "workspace": str(runtime.agent.workspace),
        "providers": runtime.agent.registry.list_ids(),
        "default_provider": runtime.agent.catalog.default_provider,
        "default_model": runtime.agent.catalog.default_model,
        "subscribers": runtime.events.subscriber_count,
        "running_sessions": runtime.agent.running_sessions,
    }
