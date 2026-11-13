import difflib
import hashlib


def unified_diff(path: str, before: str, after: str) -> str:
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    if before_lines and not before_lines[-1].endswith("\n"):
        before_lines[-1] += "\n"
    if after_lines and not after_lines[-1].endswith("\n"):
        after_lines[-1] += "\n"
    header = f"diff --git a/{path} b/{path}\n"
    if not before_lines:
        header += "new file mode 100644\n"
    body = "".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{path}" if before_lines else "/dev/null",
            tofile=f"b/{path}",
            n=3,
        )
    )
    return header + body


def diff_stats(diff: str) -> tuple[int, int]:
    additions = 0
    deletions = 0
    for line in diff.splitlines():
        if line.startswith(("+++", "---", "diff --git", "new file", "index ")):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    return additions, deletions


def content_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:12]
