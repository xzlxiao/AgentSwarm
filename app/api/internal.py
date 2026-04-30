import asyncio
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.snapshot_service import SnapshotService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])


class SnapshotCreateRequest(BaseModel):
    workspace_id: str
    volume_name: str
    name: str


class SnapshotRestoreRequest(BaseModel):
    workspace_id: str
    snapshot_id: str
    volume_name: str


def _get_settings_dep() -> Settings:
    return get_settings()


def _verify_agent_key(
    x_agent_key: str = Header(..., alias="X-Agent-Key"),
    settings: Settings = Depends(_get_settings_dep),
) -> None:
    if not hmac.compare_digest(x_agent_key.encode(), settings.agent_internal_key.encode()):
        raise HTTPException(status_code=401, detail="Invalid agent key")


@router.post("/snapshots/create")
async def create_snapshot(
    body: SnapshotCreateRequest,
    settings: Settings = Depends(_get_settings_dep),
    _auth: None = Depends(_verify_agent_key),
) -> dict[str, str]:
    service = SnapshotService(settings)
    snapshot_id = await asyncio.to_thread(
        service.create_snapshot, body.workspace_id, body.volume_name, body.name
    )
    return {"snapshot_id": snapshot_id}


@router.post("/snapshots/restore")
async def restore_snapshot(
    body: SnapshotRestoreRequest,
    settings: Settings = Depends(_get_settings_dep),
    _auth: None = Depends(_verify_agent_key),
) -> dict[str, str]:
    service = SnapshotService(settings)
    await asyncio.to_thread(
        service.restore_snapshot, body.workspace_id, body.snapshot_id, body.volume_name
    )
    return {"status": "ok"}
