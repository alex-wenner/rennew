from dataclasses import dataclass

from rennew.config.models import RennewSettings
from rennew.graph.ladybug import LadybugGraphStore
from rennew.sessions.service import SessionService


@dataclass(slots=True)
class RennewRuntime:
    settings: RennewSettings
    graph: LadybugGraphStore
    sessions: SessionService

    @classmethod
    def open(cls, settings: RennewSettings) -> "RennewRuntime":
        graph = LadybugGraphStore(settings.storage.path)
        graph.initialize()
        return cls(settings=settings, graph=graph, sessions=SessionService(graph))

    def close(self) -> None:
        self.graph.close()
