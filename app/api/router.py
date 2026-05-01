from fastapi import APIRouter

from app.api.agents import router as agents_router
from app.api.gateway import router as gateway_router
from app.api.internal import router as internal_router
from app.api.locks import router as locks_router
from app.api.workspaces import router as workspaces_router

router = APIRouter()
router.include_router(agents_router)
router.include_router(workspaces_router)
router.include_router(gateway_router)
router.include_router(internal_router)
router.include_router(locks_router)
