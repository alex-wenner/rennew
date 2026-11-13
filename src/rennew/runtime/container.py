import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rennew.agent.events import EventBus
from rennew.agent.loop import AgentLoop
from rennew.agent.mcp import MCPManager, MCPServerConfig
from rennew.agent.skills import SkillCatalog
from rennew.agent.tools import WorkspaceTools
from rennew.config.models import RennewSettings
from rennew.graph.ladybug import LadybugGraphStore
from rennew.logging_setup import configure_logging
from rennew.providers.catalog import ProviderCatalog, build_registry, load_catalog
from rennew.runtime.auth import AuthFlows
from rennew.security.credentials import CredentialStore
from rennew.sessions.service import SessionService

log = logging.getLogger("rennew.runtime")


@dataclass(slots=True)
class RennewRuntime:
    settings: RennewSettings
    graph: LadybugGraphStore
    sessions: SessionService
    events: EventBus
    agent: AgentLoop
    credentials: CredentialStore
    catalog: ProviderCatalog
    auth: AuthFlows
    mcp: MCPManager = field(default_factory=MCPManager)

    @classmethod
    def open(cls, settings: RennewSettings, workspace: Path | None = None) -> "RennewRuntime":
        configure_logging()
        graph = LadybugGraphStore(settings.storage.path)
        graph.initialize()

        resolved_workspace = (workspace or settings.agent.workspace or Path.cwd()).resolve()
        catalog = load_catalog(resolved_workspace / ".rennew")
        if settings.agent.provider:
            catalog.default_provider = settings.agent.provider
        if settings.agent.model:
            catalog.default_model = settings.agent.model
        credentials = CredentialStore()
        registry = build_registry(catalog, credentials.stored(), credentials.set_secret)
        events = EventBus()
        agent = AgentLoop(
            graph=graph,
            registry=registry,
            catalog=catalog,
            events=events,
            workspace=resolved_workspace,
            max_steps=settings.agent.max_steps,
        )
        runtime = cls(
            settings=settings,
            graph=graph,
            sessions=SessionService(graph),
            events=events,
            agent=agent,
            credentials=credentials,
            catalog=catalog,
            auth=AuthFlows(credentials, lambda: None),
        )
        runtime.auth = AuthFlows(credentials, runtime.reload_providers)
        runtime.agent.mcp = runtime.mcp
        return runtime

    def reload_providers(self) -> None:
        self.agent.registry = build_registry(
            self.catalog, self.credentials.stored(), self.credentials.set_secret
        )

    # --- MCP ------------------------------------------------------------------------

    @property
    def mcp_config_path(self) -> Path:
        return self.agent.workspace / ".rennew" / "mcp.json"

    def mcp_configs(self) -> list[MCPServerConfig]:
        paths = [self.mcp_config_path, Path.home() / ".rennew" / "mcp.json"]
        configs: dict[str, MCPServerConfig] = {}
        for path in paths:
            if not path.exists():
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                log.warning("invalid mcp config: %s", path)
                continue
            for name, spec in (raw.get("mcpServers") or {}).items():
                if name in configs or not isinstance(spec, dict):
                    continue
                if spec.get("enabled") is False or not spec.get("command"):
                    continue
                configs[name] = MCPServerConfig(
                    name=name,
                    command=str(spec["command"]),
                    args=[str(a) for a in spec.get("args") or []],
                    env={str(k): str(v) for k, v in (spec.get("env") or {}).items()},
                )
        return list(configs.values())

    async def connect_mcp(self) -> None:
        await self.mcp.close()
        self.mcp = MCPManager()
        self.agent.mcp = self.mcp
        configs = self.mcp_configs()
        if configs:
            await asyncio.gather(*(self.mcp.connect(c) for c in configs))
            log.info("mcp connected: %s", [c.name for c in configs])

    def add_mcp_server(self, name: str, command: str, args: list[str], env: dict[str, str]) -> None:
        path = self.mcp_config_path
        raw: dict[str, Any] = {"mcpServers": {}}
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        raw.setdefault("mcpServers", {})[name] = {"command": command, "args": args, "env": env}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    def remove_mcp_server(self, name: str) -> None:
        path = self.mcp_config_path
        if not path.exists():
            return
        raw = json.loads(path.read_text(encoding="utf-8"))
        (raw.get("mcpServers") or {}).pop(name, None)
        path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    # --- capability listings --------------------------------------------------------

    def describe_tools(self) -> dict[str, Any]:
        builtin = [
            {"name": s.name, "description": s.description}
            for s in WorkspaceTools(self.agent.workspace).schemas()
        ]
        builtin += [
            {"name": "skill", "description": "Load a skill's instructions on demand."},
            {"name": "remember", "description": "Store a durable fact in graph memory."},
            {"name": "recall", "description": "Search graph memory."},
        ]
        skills = [
            {"name": s.name, "description": s.description, "path": str(s.path)}
            for s in SkillCatalog.default(self.agent.workspace).discover()
        ]
        mcp_status = self.mcp.status()
        mcp_tools = [s.name for s in self.mcp.tool_schemas()]
        return {
            "workspace": str(self.agent.workspace),
            "builtin": builtin,
            "skills": skills,
            "skill_roots": [
                str(self.agent.workspace / ".rennew" / "skills"),
                str(self.agent.workspace / ".agents" / "skills"),
            ],
            "mcp": {
                "config_path": str(self.mcp_config_path),
                "servers": mcp_status,
                "tools": mcp_tools,
            },
        }

    def close(self) -> None:
        self.graph.close()
