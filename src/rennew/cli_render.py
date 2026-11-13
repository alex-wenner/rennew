import asyncio
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from rennew.runtime.container import RennewRuntime
from rennew.sessions.models import PromptRequest, SessionMessage

console = Console(highlight=False, soft_wrap=True)

_TOOL_SUMMARY_KEYS = {
    "read_file": "path",
    "write_file": "path",
    "edit_file": "path",
    "list_files": "pattern",
    "grep_files": "pattern",
    "run_command": "command",
    "skill": "name",
    "recall": "query",
    "remember": "content",
}


def _summary(tool: str, arguments: dict[str, Any]) -> str:
    key = _TOOL_SUMMARY_KEYS.get(tool)
    if key and key in arguments:
        return str(arguments[key])[:90]
    if arguments:
        first_key, first_value = next(iter(arguments.items()))
        return f"{first_key}={str(first_value)[:60]}"
    return ""


async def run_turn_rendered(
    runtime: RennewRuntime, session_id: str, request: PromptRequest, *, show_reasoning: bool = False
) -> SessionMessage:
    """Run one agent turn in-process while rendering live events to the terminal."""
    queue = runtime.events.attach()
    task = asyncio.create_task(runtime.agent.run_turn(session_id, request))
    renderer = _Renderer(show_reasoning=show_reasoning)
    try:
        while True:
            if task.done() and queue.empty():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.2)
            except TimeoutError:
                continue
            if event.get("session_id") == session_id:
                renderer.handle(event)
        return await task
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        runtime.events.detach(queue)


async def run_turn_remote(
    base_url: str, session_id: str, request: PromptRequest, *, show_reasoning: bool = False
) -> None:
    """Drive a turn on a running Rennew server and render its SSE events.

    This is the CLI-drives / web-observes mode: the server owns the graph."""
    import json

    import httpx

    from rennew.providers.sse import iter_sse_lines

    renderer = _Renderer(show_reasoning=show_reasoning)
    done = asyncio.Event()
    ready = asyncio.Event()

    async def consume() -> None:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", f"{base_url}/runtime/events") as response:
                response.raise_for_status()
                async for data in iter_sse_lines(response.aiter_lines()):
                    ready.set()
                    if not data or data == "{}":
                        continue
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if event.get("session_id") != session_id:
                        continue
                    renderer.handle(event)
                    if event.get("type") in {"run.finished", "run.error"}:
                        done.set()
                        return

    consumer = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(ready.wait(), timeout=10)
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{base_url}/sessions/{session_id}/prompt", json=request.model_dump()
            )
        if response.status_code != 200:
            detail = response.json().get("detail", response.text)
            raise RuntimeError(str(detail))
        try:
            await asyncio.wait_for(done.wait(), timeout=5)
        except TimeoutError:
            console.print(Text(str(response.json().get("content", ""))))
    finally:
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)


class _Renderer:
    def __init__(self, *, show_reasoning: bool) -> None:
        self.show_reasoning = show_reasoning
        self.streamed_any = False

    def handle(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "run.started":
            console.print(
                Text.assemble(("● ", "cyan"), (f"{event['provider']} / {event['model']}", "dim"))
            )
        elif kind == "message.delta":
            self.streamed_any = True
            console.print(Text(str(event["delta"])), end="")
        elif kind == "reasoning.delta" and self.show_reasoning:
            console.print(str(event["delta"]), end="", style="dim italic")
        elif kind == "tool.started":
            if self.streamed_any:
                console.print()
                self.streamed_any = False
            summary = _summary(str(event["tool"]), dict(event.get("arguments") or {}))
            console.print(
                Text.assemble(("  ▸ ", "dim"), (str(event["tool"]), "bold"), ("  ", ""), (summary, "dim"))
            )
        elif kind == "tool.finished":
            ok = event.get("status") == "completed"
            mark = ("    ✓", "green") if ok else ("    ✗", "red")
            console.print(Text.assemble(mark, (f" {event.get('duration_ms', 0)}ms", "dim")))
            if not ok:
                console.print(Text(str(event.get("preview", ""))[:400], style="red dim"))
        elif kind == "change.created":
            change = event["change"]
            title = Text.assemble(
                (str(change["path"]), "bold"),
                ("  ", ""),
                (f"+{change['additions']}", "green"),
                (" ", ""),
                (f"-{change['deletions']}", "red"),
            )
            console.print(
                Panel(
                    Syntax(str(change["diff"]), "diff", theme="ansi_dark", word_wrap=False),
                    title=title,
                    title_align="left",
                    border_style="dim",
                    padding=(0, 1),
                )
            )
        elif kind == "memory.created":
            console.print(
                Text.assemble(("  ◆ remembered ", "yellow"), (str(event["memory"]["content"])[:100], "dim"))
            )
        elif kind == "run.notice":
            console.print(Text(str(event["notice"]), style="yellow"))
        elif kind == "run.error":
            console.print(Text(f"error: {event['error']}", style="red"))
        elif kind == "run.finished":
            if self.streamed_any:
                console.print()
            usage = event.get("usage") or {}
            console.print(
                Text(
                    f"  {usage.get('input_tokens', 0)} in · {usage.get('output_tokens', 0)} out · "
                    f"{usage.get('steps', 0)} steps",
                    style="dim",
                )
            )
