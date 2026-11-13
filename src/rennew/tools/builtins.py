import asyncio
import os
import re
from pathlib import Path
from typing import Any

from rennew.tools.models import ToolContext, ToolDefinition
from rennew.tools.registry import ToolRegistry


def _resolve_path(ctx: ToolContext, path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (Path(ctx.repository_path) / p).resolve()


async def read_file_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    path_str = str(args.get("path", ""))
    target = _resolve_path(ctx, path_str)
    if not target.exists():
        return {"error": f"File not found: {path_str}"}
    if not target.is_file():
        return {"error": f"Path is not a file: {path_str}"}

    offset = int(args.get("offset", 1))
    limit = int(args.get("limit", 2000))

    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        start_idx = max(0, offset - 1)
        end_idx = start_idx + limit
        selected = lines[start_idx:end_idx]

        content = "".join(f"{i + start_idx + 1}: {line}" for i, line in enumerate(selected))
        return {
            "content": content,
            "total_lines": len(lines),
            "lines_returned": len(selected),
        }
    except Exception as exc:
        return {"error": str(exc)}


async def write_file_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    path_str = str(args.get("path", ""))
    content = str(args.get("content", ""))
    target = _resolve_path(ctx, path_str)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "bytes_written": len(content.encode("utf-8")),
            "path": str(target),
        }
    except Exception as exc:
        return {"error": str(exc)}


async def edit_file_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    path_str = str(args.get("path", ""))
    old_string = str(args.get("old_string", ""))
    new_string = str(args.get("new_string", ""))
    replace_all = bool(args.get("replace_all", False))

    target = _resolve_path(ctx, path_str)
    if not target.exists() or not target.is_file():
        return {"error": f"File not found: {path_str}"}

    try:
        content = target.read_text(encoding="utf-8")
        if old_string not in content:
            return {"error": "old_string not found in file content."}

        count = content.count(old_string)
        if count > 1 and not replace_all:
            return {
                "error": (
                    f"Found {count} occurrences of old_string. "
                    "Specify replace_all=True or add surrounding context."
                )
            }

        if replace_all:
            updated = content.replace(old_string, new_string)
            replacements = count
        else:
            updated = content.replace(old_string, new_string, 1)
            replacements = 1

        target.write_text(updated, encoding="utf-8")
        return {"success": True, "replacements": replacements, "path": str(target)}
    except Exception as exc:
        return {"error": str(exc)}


async def glob_files_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    pattern = str(args.get("pattern", "*"))
    subpath = str(args.get("path", "."))
    root = _resolve_path(ctx, subpath)

    if not root.exists():
        return {"error": f"Directory not found: {subpath}"}

    matches: list[str] = []
    try:
        for p in root.glob(pattern):
            if ".git" in p.parts or "node_modules" in p.parts or ".venv" in p.parts:
                continue
            matches.append(str(p.relative_to(Path(ctx.repository_path))))
        return {"matches": sorted(matches[:200]), "total": len(matches)}
    except Exception as exc:
        return {"error": str(exc)}


async def grep_files_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    pattern = str(args.get("pattern", ""))
    subpath = str(args.get("path", "."))
    root = _resolve_path(ctx, subpath)

    if not root.exists():
        return {"error": f"Directory not found: {subpath}"}

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as err:
        return {"error": f"Invalid regex: {err}"}

    matches: list[dict[str, Any]] = []
    try:
        for root_dir, _, files in os.walk(root):
            if any(part in root_dir for part in [".git", "node_modules", ".venv", "__pycache__"]):
                continue
            for file in files:
                file_path = Path(root_dir) / file
                try:
                    text = file_path.read_text(encoding="utf-8", errors="ignore")
                    for line_no, line in enumerate(text.splitlines(), start=1):
                        if regex.search(line):
                            rel_path = str(file_path.relative_to(Path(ctx.repository_path)))
                            matches.append(
                                {"file": rel_path, "line": line_no, "text": line[:200]}
                            )
                            if len(matches) >= 100:
                                return {"matches": matches, "truncated": True}
                except Exception:
                    continue
        return {"matches": matches, "total": len(matches)}
    except Exception as exc:
        return {"error": str(exc)}


async def run_command_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    command = str(args.get("command", ""))
    timeout = int(args.get("timeout", 60))
    cwd = ctx.repository_path

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }
    except TimeoutError:
        return {"error": f"Command timed out after {timeout} seconds"}
    except Exception as exc:
        return {"error": str(exc)}


def register_builtin_tools(registry: ToolRegistry) -> ToolRegistry:
    registry.register(
        ToolDefinition(
            name="read_file",
            description="Read lines from a file in the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative or absolute file path"},
                    "offset": {
                        "type": "integer",
                        "description": "1-based line start",
                        "default": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum lines to read",
                        "default": 2000,
                    },
                },
                "required": ["path"],
            },
            permission="workspace:read",
        ),
        read_file_tool,
    )

    registry.register(
        ToolDefinition(
            name="write_file",
            description="Create or overwrite a file in the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Full file content"},
                },
                "required": ["path", "content"],
            },
            permission="workspace:write",
        ),
        write_file_tool,
    )

    registry.register(
        ToolDefinition(
            name="edit_file",
            description="Perform exact string replacement in an existing file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "old_string": {"type": "string", "description": "Exact text to replace"},
                    "new_string": {"type": "string", "description": "New text to insert"},
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences",
                        "default": False,
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
            permission="workspace:write",
        ),
        edit_file_tool,
    )

    registry.register(
        ToolDefinition(
            name="glob_files",
            description="Find files in the workspace matching a glob pattern.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. **/*.py)"},
                    "path": {
                        "type": "string",
                        "description": "Subdirectory to search",
                        "default": ".",
                    },
                },
                "required": ["pattern"],
            },
            permission="workspace:read",
        ),
        glob_files_tool,
    )

    registry.register(
        ToolDefinition(
            name="grep_files",
            description="Search for regex patterns in workspace files.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to find"},
                    "path": {
                        "type": "string",
                        "description": "Subdirectory to search",
                        "default": ".",
                    },
                },
                "required": ["pattern"],
            },
            permission="workspace:read",
        ),
        grep_files_tool,
    )

    registry.register(
        ToolDefinition(
            name="run_command",
            description="Run a shell command in the repository workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                        "default": 60,
                    },
                },
                "required": ["command"],
            },
            permission="workspace:execute",
        ),
        run_command_tool,
    )

    return registry
