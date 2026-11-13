import asyncio
from collections.abc import AsyncIterator
from typing import Any


class EventBus:
    """In-process async pub/sub for execution events (CLI, SSE, projector)."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []

    def publish(self, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        queue = self.attach()

        async def generator() -> AsyncIterator[dict[str, Any]]:
            try:
                while True:
                    yield await queue.get()
            finally:
                self.detach(queue)

        return generator()

    def attach(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._subscribers.append(queue)
        return queue

    def detach(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
