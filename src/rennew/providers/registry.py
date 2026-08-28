from rennew.providers.contracts import CodingAgentBackend, ModelBackend


class ProviderRegistry:
    def __init__(self) -> None:
        self._models: dict[str, ModelBackend] = {}
        self._agents: dict[str, CodingAgentBackend] = {}

    def register_model(self, backend: ModelBackend) -> None:
        self._register(self._models, backend.name, backend)

    def register_agent(self, backend: CodingAgentBackend) -> None:
        self._register(self._agents, backend.name, backend)

    def model(self, name: str) -> ModelBackend:
        return self._models[name]

    def agent(self, name: str) -> CodingAgentBackend:
        return self._agents[name]

    def names(self) -> dict[str, list[str]]:
        return {
            "models": sorted(self._models),
            "agents": sorted(self._agents),
        }

    @staticmethod
    def _register[T](registry: dict[str, T], name: str, backend: T) -> None:
        if name in registry:
            raise ValueError(f"Provider backend already registered: {name}")
        registry[name] = backend
