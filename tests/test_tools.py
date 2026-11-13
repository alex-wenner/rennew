from pathlib import Path

import pytest

from rennew.tools.builtins import (
    edit_file_tool,
    glob_files_tool,
    grep_files_tool,
    read_file_tool,
    register_builtin_tools,
    run_command_tool,
    write_file_tool,
)
from rennew.tools.models import ToolContext
from rennew.tools.registry import ToolRegistry


@pytest.mark.anyio
async def test_file_tools_roundtrip(tmp_path: Path) -> None:
    ctx = ToolContext(session_id="ses_test", repository_path=str(tmp_path))

    # Write file
    write_res = await write_file_tool(
        ctx,
        {"path": "src/main.py", "content": "def hello():\n    return 'world'\n"},
    )
    assert write_res["success"] is True

    # Read file
    read_res = await read_file_tool(ctx, {"path": "src/main.py"})
    assert "1: def hello():" in read_res["content"]

    # Edit file
    edit_res = await edit_file_tool(
        ctx,
        {"path": "src/main.py", "old_string": "'world'", "new_string": "'rennew'"},
    )
    assert edit_res["success"] is True

    # Glob files
    glob_res = await glob_files_tool(ctx, {"pattern": "**/*.py"})
    assert "src/main.py" in [p.replace("\\", "/") for p in glob_res["matches"]]

    # Grep files
    grep_res = await grep_files_tool(ctx, {"pattern": "rennew"})
    assert len(grep_res["matches"]) == 1
    assert "src/main.py" in grep_res["matches"][0]["file"].replace("\\", "/")

    # Run command
    cmd_res = await run_command_tool(ctx, {"command": 'python -c "print(1+1)"'})
    assert cmd_res["exit_code"] == 0
    assert "2" in cmd_res["stdout"]


def test_tool_registry_registration() -> None:
    registry = ToolRegistry()
    register_builtin_tools(registry)
    defs = registry.definitions()
    tool_names = {d.name for d in defs}
    expected = {
        "read_file",
        "write_file",
        "edit_file",
        "glob_files",
        "grep_files",
        "run_command",
    }
    assert expected.issubset(tool_names)
