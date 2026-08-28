from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from rennew.api.routes import router
from rennew.config.loader import load_settings
from rennew.config.models import RennewSettings
from rennew.runtime.container import RennewRuntime


def create_app(settings: RennewSettings | None = None) -> FastAPI:
    resolved_settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime = RennewRuntime.open(resolved_settings)
        app.state.runtime = runtime
        try:
            yield
        finally:
            runtime.close()

    app = FastAPI(
        title="Rennew",
        version="0.1.0",
        description="Local API for the Rennew coding-agent runtime.",
        lifespan=lifespan,
    )
    app.include_router(router)
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    static_root = Path(__file__).parents[1] / "web" / "static"
    index = static_root / "index.html"
    assets = static_root / "assets"
    if not index.exists():

        @app.get("/")
        def development_root() -> dict[str, str]:
            return {
                "name": "Rennew API",
                "message": "Build the frontend to install the local web interface.",
            }

        return

    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def single_page_app(path: str) -> FileResponse:
        requested = static_root / path
        if path and requested.is_file() and static_root in requested.parents:
            return FileResponse(requested)
        return FileResponse(index)
