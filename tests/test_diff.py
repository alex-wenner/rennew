from pathlib import Path

from rennew.agent.diff import diff_stats, unified_diff
from rennew.agent.tools import ChangeRecord, WorkspaceTools


def test_unified_diff_has_git_header_and_stats() -> None:
    diff = unified_diff("src/app.py", "a\nb\n", "a\nc\nd\n")
    assert diff.startswith("diff --git a/src/app.py b/src/app.py")
    assert "--- a/src/app.py" in diff and "+++ b/src/app.py" in diff
    assert diff_stats(diff) == (2, 1)


def test_workspace_tools_record_changes(tmp_path: Path) -> None:
    recorded: list[ChangeRecord] = []
    tools = WorkspaceTools(tmp_path, on_change=recorded.append)

    created = tools.execute("write_file", {"path": "notes.md", "content": "one\n"})
    assert "+1" in created
    edited = tools.execute("edit_file", {"path": "notes.md", "old_string": "one", "new_string": "two"})
    assert "+1 -1" in edited

    assert [c.kind for c in recorded] == ["create", "edit"]
    assert recorded[0].diff.startswith("diff --git a/notes.md b/notes.md\nnew file mode")
    assert recorded[1].before_hash != recorded[1].after_hash
