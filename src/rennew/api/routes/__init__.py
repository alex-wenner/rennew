from fastapi import APIRouter

from rennew.api.routes.graph import router as graph_router
from rennew.api.routes.health import router as health_router
from rennew.api.routes.runtime import router as runtime_router
from rennew.api.routes.sessions import router as sessions_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(sessions_router)
router.include_router(graph_router)
router.include_router(runtime_router)
