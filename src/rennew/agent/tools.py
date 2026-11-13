import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rennew.agent.diff import content_hash, diff_stats, unified_diff
from rennew.providers.contracts import ToolSchema


class ToolError(RuntimeError):
    pass


@dataclass(slots=True)
class ChangeRecord:
    path: str
    kind: str
    before: str
    after: str
    diff: str
    additions: int
    deletions: int
    before_hash: str
    after_hash: str


ChangeListener = Callable[[ChangeRecord], None]


class WorkspaceTools:
    """Filesystem and shell tools confined to a workspace root."""

    def __init__(
        self,
        root: Path,
        *,
        command_timeout: float = 60.0,
        on_change: ChangeListener | None = None,
    ) -> None:
        self._root = root.resolve()
        self._command_timeout = command_timeout
        self._on_change = on_change

    @property
    def root(self) -> Path:
        return self._root

    def _record_change(self, relative: str, before: str, after: str, kind: str) -> ChangeRecord:
        diff = unified_diff(relative, before, after)
        additions, deletions = diff_stats(diff)
        record = ChangeRecord(
            path=relative,
            kind=kind,
            before=before,
            after=after,
            diff=diff,
            additions=additions,
            deletions=deletions,
            before_hash=content_hash(before),
            after_hash=content_hash(after),
        )
        if self._on_change is not None:
            self._on_change(record)
        return record

    def schemas(self) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="read_file",
                description="Read a text file from the workspace. Returns content with line numbers.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path relative to the workspace root."},
                        "offset": {"type": "integer", "description": "1-based start line.", "default": 1},
                        "limit": {"type": "integer", "description": "Max lines to return.", "default": 400},
                    },
                    "required": ["path"],
                },
            ),
            ToolSchema(
                name="write_file",
                description="Create or overwrite a file inside the workspace.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            ),
            ToolSchema(
                name="edit_file",
                description="Replace an exact string occurrence in a file. Fails unless old_string is unique.",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                    "required": ["path", "old_string", "new_string"],
                },
            ),
            ToolSchema(
                name="list_files",
                description="List files matching a glob pattern under the workspace.",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Glob pattern, e.g. **/*.py"},
                        "limit": {"type": "integer", "default": 200},
                    },
                    "required": ["pattern"],
                },
            ),
            ToolSchema(
                name="grep_files",
                description="Search file contents with a regex. Returns file:line:match rows.",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "glob": {"type": "string", "description": "Optional file glob filter.", "default": "**/*"},
                        "limit": {"type": "integer", "default": 100},
                    },
                    "required": ["pattern"],
                },
            ),
            ToolSchema(
                name="run_command",
                description="Run a shell command inside the workspace root. Use for builds and tests.",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "timeout_seconds": {"type": "number", "default": 60},
                    },
                    "required": ["command"],
                },
            ),
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        handlers = {
            "read_file": self._read_file,
            "write_file": self._write_file,
            "edit_file": self._edit_file,
            "list_files": self._list_files,
            "grep_files": self._grep_files,
            "run_command": self._run_command,
        }
        handler = handlers.get(name)
        if handler is None:
            raise ToolError(f"Unknown tool: {name}")
        return handler(arguments)

    def _resolve(self, path: str) -> Path:
        candidate = (self._root / path).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise ToolError(f"Path escapes the workspace: {path}")
        return candidate

    def _read_file(self, arguments: dict[str, Any]) -> str:
        target = self._resolve(str(arguments["path"]))
        if not target.is_file():
            raise ToolError(f"Not a file: {arguments['path']}")
        offset = max(1, int(arguments.get("offset") or 1))
        limit = max(1, int(arguments.get("limit") or 400))
        text = target.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        window = lines[offset - 1 : offset - 1 + limit]
        numbered = [f"{offset + i}: {line}" for i, line in enumerate(window)]
        truncated = "" if len(lines) <= offset - 1 + limit else f"\n... ({len(lines)} lines total)"
        return "\n".join(numbered) + truncated

    def _write_file(self, arguments: dict[str, Any]) -> str:
        target = self._resolve(str(arguments["path"]))
        relative = str(target.relative_to(self._root)).replace("\\", "/")
        before = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
        after = str(arguments["content"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(after, encoding="utf-8")
        record = self._record_change(relative, before, after, "edit" if before else "create")
        return f"Wrote {relative} (+{record.additions} -{record.deletions})"

    def _edit_file(self, arguments: dict[str, Any]) -> str:
        target = self._resolve(str(arguments["path"]))
        if not target.is_file():
            raise ToolError(f"Not a file: {arguments['path']}")
        relative = str(target.relative_to(self._root)).replace("\\", "/")
        before = target.read_text(encoding="utf-8")
        old = str(arguments["old_string"])
        new = str(arguments["new_string"])
        count = before.count(old)
        if count == 0:
            raise ToolError("old_string not found in file.")
        if count > 1:
            raise ToolError(f"old_string matches {count} times; provide more context.")
        after = before.replace(old, new, 1)
        target.write_text(after, encoding="utf-8")
        record = self._record_change(relative, before, after, "edit")
        return f"Edited {relative} (+{record.additions} -{record.deletions})"

    def _list_files(self, arguments: dict[str, Any]) -> str:
        pattern = str(arguments["pattern"])
        limit = max(1, int(arguments.get("limit") or 200))
        matches: list[str] = []
        for match in sorted(self._root.glob(pattern)):
            if match.is_file():
                matches.append(str(match.relative_to(self._root)))
            if len(matches) >= limit:
                break
        return "\n".join(matches) if matches else "No matches."

    def _grep_files(self, arguments: dict[str, Any]) -> str:
        import re as regex

        pattern = regex.compile(str(arguments["pattern"]))
        glob = str(arguments.get("glob") or "**/*")
        limit = max(1, int(arguments.get("limit") or 100))
        rows: list[str] = []
        for match in sorted(self._root.glob(glob)):
            if not match.is_file():
                continue
            try:
                text = match.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    rows.append(f"{match.relative_to(self._root)}:{line_number}:{line.strip()[:200]}")
                    if len(rows) >= limit:
                        return "\n".join(rows) + "\n(truncated)"
        return "\n".join(rows) if rows else "No matches."

    def _run_command(self, arguments: dict[str, Any]) -> str:
        command = str(arguments["command"])
        timeout = min(float(arguments.get("timeout_seconds") or self._command_timeout), 600.0)
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise ToolError(f"Command timed out after {timeout}s.") from None
        output = completed.stdout.strip()
        errors = completed.stderr.strip()
        parts = [f"exit_code={completed.returncode}"]
        if output:
            parts.append(output[:8000])
        if errors:
            parts.append(f"stderr:\n{errors[:4000]}")
        return "\n".join(parts)


def parse_arguments(raw: str) -> dict[str, Any]:
    if not raw or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ToolError(f"Invalid JSON arguments: {error}") from error
    if not isinstance(parsed, dict):
        raise ToolError("Tool arguments must be a JSON object.")
    return parsed
