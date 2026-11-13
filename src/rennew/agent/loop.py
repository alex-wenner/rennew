import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rennew.agent.context import build_system_prompt, history_to_provider_messages
from rennew.agent.events import EventBus
from rennew.agent.mcp import MCPManager
from rennew.agent.memory import MemoryEntry, new_memory
from rennew.agent.skills import SkillCatalog
from rennew.agent.tools import ChangeRecord, ToolError, WorkspaceTools, parse_arguments
from rennew.graph.contracts import GraphStore
from rennew.providers.catalog import ProviderCatalog
from rennew.providers.contracts import (
    ChatRequest,
    ProviderMessage,
    ToolSchema,
    estimate_tokens,
)
from rennew.providers.registry import ProviderRegistry, provider_is_connected
from rennew.sessions.models import (
    Compaction,
    FileChange,
    PromptRequest,
    Session,
    SessionMessage,
    TokenMetrics,
    ToolCallRecord,
    new_identifier,
    utc_now,
)
from rennew.sessions.service import SessionNotFoundError
from rennew.telemetry.pricing import calculate_cost

DEFAULT_MAX_STEPS = 12
AUTO_COMPACT_TOKEN_THRESHOLD = 120_000


class ProviderNotConfiguredError(RuntimeError):
    pass


class SessionBusyError(RuntimeError):
    pass


@dataclass(slots=True)
class TurnUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0
    steps: int = 0


@dataclass(slots=True)
class AgentLoop:
    graph: GraphStore
    registry: ProviderRegistry
    catalog: ProviderCatalog
    events: EventBus
    workspace: Path
    mcp: MCPManager | None = None
    max_steps: int = DEFAULT_MAX_STEPS
    _busy: set[str] = field(default_factory=set)

    @property
    def running_sessions(self) -> list[str]:
        return sorted(self._busy)

    async def run_turn(self, session_id: str, request: PromptRequest) -> SessionMessage:
        session = self._graph_get_session(session_id)
        if session_id in self._busy:
            raise SessionBusyError("Session already has an active turn.")
        self._busy.add(session_id)
        try:
            return await self._run_turn(session, request)
        except asyncio.CancelledError:
            self._emit({"type": "run.error", "session_id": session_id, "error": "Turn interrupted."})
            raise
        except Exception as error:
            self._emit({"type": "run.error", "session_id": session_id, "error": str(error)})
            raise
        finally:
            self._busy.discard(session_id)

    async def _run_turn(self, session: Session, request: PromptRequest) -> SessionMessage:
        session_id = session.id
        provider_id, model_id = self._resolve_model(session, request)
        provider = self.registry.get(provider_id)
        if provider is None:
            raise ProviderNotConfiguredError(
                f"Unknown provider '{provider_id}'. Open Providers and connect one."
            )
        if not provider_is_connected(provider):
            raise ProviderNotConfiguredError(
                f"'{provider_id}' is not connected. Open Providers and sign in or add a key."
            )

        workspace_root = (
            Path(session.workspace).expanduser().resolve() if session.workspace else self.workspace
        )
        if not workspace_root.is_dir():
            raise ProviderNotConfiguredError(f"Workspace directory does not exist: {workspace_root}")
        pending_changes: list[ChangeRecord] = []
        workspace_tools = WorkspaceTools(workspace_root, on_change=pending_changes.append)
        self.graph.update_session_model(session_id, provider_id, model_id)
        skills = SkillCatalog.default(workspace_root)
        memories = self._recall_for(request.prompt)
        system_prompt = build_system_prompt(
            workspace_root, skills, memories, mode=request.mode or session.mode
        )

        self._emit(
            {
                "type": "run.started",
                "session_id": session_id,
                "provider": provider_id,
                "model": model_id,
            }
        )

        user_message = SessionMessage(
            id=new_identifier("msg"),
            session_id=session_id,
            role="user",
            content=request.prompt,
            tokens=TokenMetrics(input=estimate_tokens(request.prompt)),
            created_at=utc_now(),
        )
        self.graph.create_message(user_message)
        self._emit(
            {
                "type": "message.saved",
                "session_id": session_id,
                "message": user_message.model_dump(mode="json"),
            }
        )

        messages = self.graph.list_messages(session_id)
        compactions = self.graph.list_compactions(session_id)
        provider_messages: list[dict[str, object]] = history_to_provider_messages(
            messages[:-1], compactions[0] if compactions else None
        )
        provider_messages.append({"role": "user", "content": request.prompt})

        usage = TurnUsage()
        try:
            for step in range(self.max_steps):
                usage.steps = step + 1
                assistant_text, reasoning, tool_calls, step_usage = await self._stream_step(
                    provider,
                    model_id,
                    system_prompt,
                    provider_messages,
                    workspace_tools,
                    skills,
                    session_id,
                    request,
                )
                usage.input_tokens += step_usage.get("input", 0)
                usage.output_tokens += step_usage.get("output", 0)
                usage.reasoning_tokens += step_usage.get("reasoning", 0)

                message_id = new_identifier("msg")
                change_links: list[tuple[str, ChangeRecord]] = []
                if tool_calls:
                    for tool in tool_calls:
                        pending_changes.clear()
                        started = time.perf_counter()
                        output, status = await self._execute_tool(
                            tool.name, tool.input, workspace_tools, skills, session_id, tool.id
                        )
                        tool.output = {"result": output}
                        tool.status = status
                        tool.duration_ms = int((time.perf_counter() - started) * 1000)
                        change_links.extend((tool.id, change) for change in pending_changes)

                assistant_message = SessionMessage(
                    id=message_id,
                    session_id=session_id,
                    role="assistant",
                    content=assistant_text,
                    reasoning=reasoning or None,
                    tool_calls=tool_calls,
                    tokens=TokenMetrics(
                        input=step_usage.get("input", 0),
                        output=step_usage.get("output", 0),
                        reasoning=step_usage.get("reasoning", 0),
                        total=step_usage.get("input", 0) + step_usage.get("output", 0),
                    ),
                    created_at=utc_now(),
                )
                self.graph.create_message(assistant_message)
                self._emit(
                    {
                        "type": "message.saved",
                        "session_id": session_id,
                        "message": assistant_message.model_dump(mode="json"),
                    }
                )
                for tool_call_id, change in change_links:
                    file_change = FileChange(
                        id=new_identifier("chg"),
                        session_id=session_id,
                        message_id=message_id,
                        tool_call_id=tool_call_id,
                        path=change.path,
                        kind=change.kind,
                        before_hash=change.before_hash,
                        after_hash=change.after_hash,
                        additions=change.additions,
                        deletions=change.deletions,
                        diff=change.diff,
                        created_at=utc_now(),
                    )
                    self.graph.create_file_change(file_change)
                    self._emit(
                        {
                            "type": "change.created",
                            "session_id": session_id,
                            "change": file_change.model_dump(mode="json"),
                        }
                    )

                if not tool_calls:
                    break

                provider_messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_text,
                        "tool_calls": [
                            {
                                "id": tool.id,
                                "type": "function",
                                "function": {
                                    "name": tool.name,
                                    "arguments": json.dumps(tool.input, default=str),
                                },
                            }
                            for tool in tool_calls
                        ],
                    }
                )
                for tool in tool_calls:
                    output_text = str((tool.output or {}).get("result", ""))
                    provider_messages.append(
                        {"role": "tool", "tool_call_id": tool.id, "content": output_text}
                    )
            else:
                self._emit(
                    {
                        "type": "run.notice",
                        "session_id": session_id,
                        "notice": f"Reached step limit ({self.max_steps}).",
                    }
                )
        finally:
            cost = calculate_cost(
                model_id,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                provider=provider_id,
            )
            self.graph.update_session_metrics(
                session_id,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                cost_usd=cost,
            )
        self._emit(
            {
                "type": "run.finished",
                "session_id": session_id,
                "usage": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "reasoning_tokens": usage.reasoning_tokens,
                    "steps": usage.steps,
                },
            }
        )

        await self._maybe_compact(session_id, provider_id, model_id)
        return assistant_message

    async def _stream_step(
        self,
        provider: Any,
        model_id: str,
        system_prompt: str,
        provider_messages: list[dict[str, object]],
        workspace_tools: WorkspaceTools,
        skills: SkillCatalog,
        session_id: str,
        request: PromptRequest,
    ) -> tuple[str, str, list[ToolCallRecord], dict[str, int]]:
        tools = self._tool_schemas(workspace_tools, skills)
        messages = [ProviderMessage(role="system", content=system_prompt)]
        messages.extend(ProviderMessage.model_validate(message) for message in provider_messages)
        chat_request = ChatRequest(
            model=model_id,
            messages=messages,
            tools=tools,
            reasoning_effort=request.reasoning_effort,
        )

        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[ToolCallRecord] = []
        usage: dict[str, int] = {}
        error: str | None = None

        async for delta in provider.stream(chat_request):
            if delta.kind == "text":
                text_parts.append(delta.text)
                self._emit({"type": "message.delta", "session_id": session_id, "delta": delta.text})
            elif delta.kind == "reasoning":
                reasoning_parts.append(delta.text)
                self._emit(
                    {"type": "reasoning.delta", "session_id": session_id, "delta": delta.text}
                )
            elif delta.kind == "tool_call" and delta.tool_call:
                arguments = parse_arguments(str(delta.tool_call.get("arguments") or "{}"))
                tool_calls.append(
                    ToolCallRecord(
                        id=str(delta.tool_call.get("id") or new_identifier("tool")),
                        name=str(delta.tool_call.get("name") or ""),
                        input=arguments,
                        output=None,
                        status="pending",
                        duration_ms=0,
                    )
                )
            elif delta.kind == "usage" and delta.usage:
                for key, value in delta.usage.items():
                    usage[key] = usage.get(key, 0) + int(value)
            elif delta.kind == "error":
                error = delta.error or "provider error"

        if error:
            raise RuntimeError(error)
        return "".join(text_parts), "".join(reasoning_parts), tool_calls, usage

    def _tool_schemas(self, workspace_tools: WorkspaceTools, skills: SkillCatalog) -> list[ToolSchema]:
        schemas = list(workspace_tools.schemas())
        schemas.append(skills.tool_schema())
        schemas.append(
            ToolSchema(
                name="remember",
                description="Store a durable fact in graph memory for future sessions.",
                parameters={
                    "type": "object",
                    "properties": {"content": {"type": "string"}},
                    "required": ["content"],
                },
            )
        )
        schemas.append(
            ToolSchema(
                name="recall",
                description="Search graph memory for prior knowledge.",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            )
        )
        if self.mcp is not None:
            schemas.extend(self.mcp.tool_schemas())
        return schemas

    async def _execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        workspace_tools: WorkspaceTools,
        skills: SkillCatalog,
        session_id: str,
        tool_call_id: str,
    ) -> tuple[str, str]:
        started = time.perf_counter()
        self._emit(
            {
                "type": "tool.started",
                "session_id": session_id,
                "tool": name,
                "tool_call_id": tool_call_id,
                "arguments": arguments,
            }
        )
        try:
            if name == "skill":
                skill = skills.get(str(arguments.get("name") or ""))
                result = skill.body if skill else f"Skill not found: {arguments.get('name')}"
            elif name == "remember":
                entry = new_memory(
                    str(arguments.get("content") or ""), source="agent", session_id=session_id
                )
                self.graph.create_memory(
                    entry.id, entry.scope, entry.content, entry.source, entry.confidence, session_id
                )
                result = f"Remembered: {entry.id}"
                self._emit(
                    {
                        "type": "memory.created",
                        "session_id": session_id,
                        "memory": entry.model_dump(mode="json"),
                    }
                )
            elif name == "recall":
                matches = self._recall_for(str(arguments.get("query") or ""))
                result = (
                    "\n".join(f"- {match.content}" for match in matches)
                    if matches
                    else "No memories matched."
                )
            elif self.mcp is not None and self.mcp.is_mcp_tool(name):
                result = await self.mcp.call(name, arguments)
            else:
                result = await asyncio.to_thread(workspace_tools.execute, name, arguments)
            status = "completed"
        except (ToolError, RuntimeError, OSError, ValueError, KeyError, TypeError) as error:
            result = f"error: {error}"
            status = "failed"
        duration_ms = int((time.perf_counter() - started) * 1000)
        self._emit(
            {
                "type": "tool.finished",
                "session_id": session_id,
                "tool": name,
                "tool_call_id": tool_call_id,
                "status": status,
                "duration_ms": duration_ms,
                "preview": result[:400],
            }
        )
        return result, status

    def _recall_for(self, query: str) -> list[MemoryEntry]:
        if not query.strip():
            return []
        terms = {term.lower() for term in query.split() if len(term) > 3}
        if not terms:
            return []
        scored: list[tuple[int, MemoryEntry]] = []
        for row in self.graph.list_memories(limit=500):
            content = str(row.get("content") or "")
            hits = sum(1 for term in terms if term in content.lower())
            if hits > 0:
                scored.append(
                    (
                        hits,
                        MemoryEntry(
                            id=str(row.get("id") or ""),
                            scope=str(row.get("scope") or "workspace"),
                            content=content,
                            source=str(row.get("source") or ""),
                            confidence=float(str(row.get("confidence") or 0.5)),
                        ),
                    )
                )
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [entry for _, entry in scored[:8]]

    async def _maybe_compact(self, session_id: str, provider_id: str, model_id: str) -> None:
        messages = self.graph.list_messages(session_id)
        checkpoints = self.graph.list_compactions(session_id)
        previous = checkpoints[0] if checkpoints else None
        active = [m for m in messages if previous is None or m.created_at > previous.created_at]
        total_chars = sum(len(m.content) + len(json.dumps([t.model_dump() for t in m.tool_calls])) for m in active)
        estimated_tokens = total_chars // 4
        if estimated_tokens < AUTO_COMPACT_TOKEN_THRESHOLD:
            return

        provider = self.registry.get(provider_id)
        summary = ""
        if provider is not None:
            transcript = json.dumps(history_to_provider_messages(messages, previous), default=str)
            try:
                request = ChatRequest(
                    model=model_id,
                    messages=[
                        ProviderMessage(
                            role="user",
                            content=(
                                "Summarize this agent transcript into a compact checkpoint: "
                                "objective, completed work, active state, blockers, next move, "
                                "relevant files.\n\n" + transcript[:60000]
                            ),
                        )
                    ],
                    max_tokens=1024,
                )
                parts: list[str] = []
                async for delta in provider.stream(request):
                    if delta.kind == "text":
                        parts.append(delta.text)
                    elif delta.kind == "error":
                        return
                summary = "".join(parts).strip()
            except Exception:  # noqa: BLE001 - compaction must never break the session
                summary = ""
        if not summary:
            return

        compaction = Compaction(
            id=new_identifier("cmp"),
            session_id=session_id,
            objective=summary.splitlines()[0][:200] if summary else "Context checkpoint",
            completed=summary[:2000],
            active="Continuing from checkpoint",
            blocked="(none)",
            next_move="Continue session objective",
            relevant_files="",
            tokens_saved=estimated_tokens // 2,
            created_at=utc_now(),
        )
        self.graph.create_compaction(compaction)
        self._emit({"type": "session.compacted", "session_id": session_id})

    def _resolve_model(self, session: Session, request: PromptRequest) -> tuple[str, str]:
        provider_id = request.provider or session.provider or self.catalog.default_provider
        if not provider_id:
            raise ProviderNotConfiguredError("No provider configured.")
        spec = self.catalog.providers.get(provider_id)
        spec_default = spec.models[0] if spec is not None and spec.models else None
        session_model = session.model if session.provider == provider_id else None
        default_model = self.catalog.default_model if self.catalog.default_provider == provider_id else None
        model_id = request.model or session_model or default_model or spec_default or ""
        if not model_id:
            raise ProviderNotConfiguredError(
                f"No model configured for provider '{provider_id}'. "
                "Set agent.model, a session model, or pass a model."
            )
        return provider_id, model_id

    def _graph_get_session(self, session_id: str) -> Session:
        session = self.graph.get_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def _emit(self, event: dict[str, Any]) -> None:
        event.setdefault("at", utc_now().isoformat())
        self.events.publish(event)
