from collections.abc import AsyncIterator
from pathlib import Path

from rennew.agent.events import EventBus
from rennew.agent.loop import AgentLoop
from rennew.graph.ladybug import LadybugGraphStore
from rennew.providers.catalog import ProviderCatalog, ProviderSpec
from rennew.providers.contracts import ChatRequest, ProviderCapabilities, StreamDelta
from rennew.providers.registry import ProviderRegistry
from rennew.sessions.models import PromptRequest, SessionCreate
from rennew.sessions.service import SessionService


class FakeProvider:
    name = "fake"
    _api_key = "test"

    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True, tool_calling=True)

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        self.requests.append(request)
        yield StreamDelta(kind="text", text="Workspace inspected.")
        yield StreamDelta(kind="usage", usage={"input": 12, "output": 8, "reasoning": 0})
        yield StreamDelta(kind="finish", finish_reason="stop")


def test_agent_loop_runs_a_real_turn(tmp_path: Path) -> None:
    store = LadybugGraphStore(tmp_path / "graph.lbdb")
    store.initialize()
    service = SessionService(store)
    session = service.create(SessionCreate(title="Loop test", provider="fake", model="fake-1"))
    registry = ProviderRegistry()
    provider = FakeProvider()
    registry.register(provider)
    catalog = ProviderCatalog(
        providers={"fake": ProviderSpec(id="fake", models=["fake-1"])},
        default_provider="fake",
        default_model="fake-1",
    )
    loop = AgentLoop(
        graph=store,
        registry=registry,
        catalog=catalog,
        events=EventBus(),
        workspace=tmp_path,
        max_steps=2,
    )
    import asyncio

    message = asyncio.run(
        loop.run_turn(session.id, PromptRequest(prompt="Look around.", provider="fake", model="fake-1"))
    )
    assert message.role == "assistant"
    assert "inspected" in message.content.lower()
    stored = store.list_messages(session.id)
    assert stored[0].role == "user"
    assert stored[-1].role == "assistant"
    assert message.id == stored[-1].id
    assert provider.requests[0].messages[-1].content == "Look around."
    assert loop.running_sessions == []
    store.close()
