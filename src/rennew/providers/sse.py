from collections.abc import AsyncIterator


async def iter_sse_lines(lines: AsyncIterator[str]) -> AsyncIterator[str]:
    """Yield the `data:` payloads of a Server-Sent-Events stream, one per event."""
    buffer: list[str] = []
    async for line in lines:
        stripped = line.rstrip("\r\n")
        if stripped == "":
            if buffer:
                yield "\n".join(buffer)
                buffer = []
            continue
        if stripped.startswith(":"):
            continue
        if stripped.startswith("data:"):
            buffer.append(stripped[5:].lstrip())
    if buffer:
        yield "\n".join(buffer)
