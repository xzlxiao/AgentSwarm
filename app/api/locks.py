from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.config import Settings, get_settings
from app.core.exceptions import LockNotFoundError
from app.core.logging import get_logger
from app.models.workspace_lock import AcquireLockRequest, HeartbeatRequest, ReleaseLockRequest
from app.services.lock_service import LockService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/internal/locks", tags=["locks"])


def _get_settings_dep() -> Settings:
    return get_settings()


def _verify_agent_key(
    x_agent_key: str = Header(..., alias="X-Agent-Key"),
    settings: Settings = Depends(_get_settings_dep),
) -> None:
    import hmac

    if not hmac.compare_digest(x_agent_key.encode(), settings.agent_internal_key.encode()):
        raise HTTPException(status_code=401, detail="Invalid agent key")


def _get_lock_service(request: Request) -> LockService:
    try:
        service: LockService = request.app.state.lock_service
    except AttributeError:
        raise HTTPException(status_code=503, detail="Lock service not initialized")
    return service


@router.post("/acquire")
async def acquire_lock(
    body: AcquireLockRequest,
    request: Request,
    _auth: None = Depends(_verify_agent_key),
) -> dict[str, object]:
    service = _get_lock_service(request)
    result = await service.acquire_lock(
        workspace_id=body.workspace_id,
        node_id=body.node_id,
        container_id=body.container_id,
        timeout_seconds=body.timeout_seconds,
    )
    from typing import cast

    holder_node_id = result.get("holder_node_id")
    is_holder = holder_node_id == body.node_id
    wait_queue = cast(list[object], result.get("wait_queue", []))
    return {
        "status": "locked" if is_holder else "queued",
        "workspace_id": result.get("workspace_id"),
        "holder_node_id": holder_node_id,
        "position": len(wait_queue) if not is_holder else None,
    }


@router.post("/release")
async def release_lock(
    body: ReleaseLockRequest,
    request: Request,
    _auth: None = Depends(_verify_agent_key),
) -> dict[str, object]:
    service = _get_lock_service(request)
    result = await service.release_lock(
        workspace_id=body.workspace_id,
        node_id=body.node_id,
    )
    return {
        "status": "released",
        "snapshot_id": result.get("snapshot_id"),
        "next_holder": result.get("holder_node_id"),
    }


@router.post("/heartbeat")
async def heartbeat(
    body: HeartbeatRequest,
    request: Request,
    _auth: None = Depends(_verify_agent_key),
) -> dict[str, str]:
    service = _get_lock_service(request)
    await service.heartbeat(workspace_id=body.workspace_id, node_id=body.node_id)
    return {"status": "ok"}


@router.get("/{workspace_id}")
async def get_lock_status(
    workspace_id: str,
    request: Request,
    _auth: None = Depends(_verify_agent_key),
) -> dict[str, object]:
    service = _get_lock_service(request)
    try:
        result = await service.get_lock_status(workspace_id)
    except LockNotFoundError:
        return {"status": "free", "workspace_id": workspace_id}

    return result
