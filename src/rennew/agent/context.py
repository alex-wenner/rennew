from pathlib import Path

from rennew.agent.memory import MemoryEntry
from rennew.agent.skills import SkillCatalog
from rennew.sessions.models import Compaction, SessionMessage

TOOL_OUTPUT_PRUNE_CHARS = 1200


def build_system_prompt(
    workspace: Path,
    skills: SkillCatalog,
    memories: list[MemoryEntry],
    *,
    mode: str = "solo",
) -> str:
    parts = [
        "You are Rennew, a local-first coding agent. You work inside a session graph that "
        "records your decisions, tool activity, and handoffs. Be concise, verify claims by "
        "reading files or running commands, and prefer small verifiable steps.",
        f"Workspace root: {workspace}",
        f"Session mode: {mode}",
    ]
    skill_listing = skills.prompt_listing()
    if skill_listing:
        parts.append(skill_listing)
    if memories:
        memory_lines = ["Relevant memories from prior sessions:"]
        memory_lines.extend(f"- {memory.content}" for memory in memories[:8])
        parts.append("\n".join(memory_lines))
    parts.append(
        "Use tools to inspect and modify the workspace. Record durable facts with the "
        "`remember` tool when they will matter in future sessions."
    )
    return "\n\n".join(parts)


def prune_tool_output(output: str) -> str:
    if len(output) <= TOOL_OUTPUT_PRUNE_CHARS:
        return output
    head = output[:800]
    tail = output[-300:]
    omitted = len(output) - len(head) - len(tail)
    return f"{head}\n... [{omitted} characters omitted] ...\n{tail}"


def history_to_provider_messages(
    messages: list[SessionMessage],
    latest_compaction: Compaction | None,
    *,
    max_messages: int = 24,
) -> list[dict[str, object]]:
    """Convert stored graph messages into provider messages.

    Token efficiency: if a compaction checkpoint exists, only messages after it
    are replayed; the checkpoint summary stands in for everything older. Large
    tool outputs are pruned.
    """
    cutoff = latest_compaction.created_at if latest_compaction else None
    recent = [m for m in messages if cutoff is None or m.created_at >= cutoff][-max_messages:]

    provider_messages: list[dict[str, object]] = []
    if latest_compaction:
        summary = (
            f"[Context checkpoint] Objective: {latest_compaction.objective}\n"
            f"Completed: {latest_compaction.completed}\n"
            f"Active: {latest_compaction.active}\n"
            f"Blocked: {latest_compaction.blocked}\n"
            f"Next move: {latest_compaction.next_move}\n"
            f"Relevant files: {latest_compaction.relevant_files}"
        )
        provider_messages.append({"role": "user", "content": summary})
        provider_messages.append(
            {"role": "assistant", "content": "Understood. Continuing from the checkpoint."}
        )

    for message in recent:
        if message.role == "user":
            provider_messages.append({"role": "user", "content": message.content})
            continue
        tool_calls = [
            {
                "id": tool.id,
                "type": "function",
                "function": {"name": tool.name, "arguments": _json_dumps(tool.input)},
            }
            for tool in message.tool_calls
        ]
        provider_messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": tool_calls,
            }
        )
        for tool in message.tool_calls:
            output_text = _json_dumps(tool.output) if tool.output is not None else ""
            provider_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool.id,
                    "content": prune_tool_output(output_text),
                }
            )
    return provider_messages


def _json_dumps(value: object) -> str:
    import json

    return json.dumps(value, default=str)
