from fastapi import APIRouter, Depends, Request

from app.core.exceptions import WorkspaceNotFoundError
from app.models.workspace import CreateWorkspaceRequest, ProjectWorkspaceDoc
from app.services.workspace_service import WorkspaceService
from app.swarm.volume import VolumeManager

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


def _get_workspace_service(request: Request) -> WorkspaceService:
    return WorkspaceService(request.app.state.db, VolumeManager())


@router.post("", status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest,
    service: WorkspaceService = Depends(_get_workspace_service),
) -> ProjectWorkspaceDoc:
    return await service.create(body)


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    service: WorkspaceService = Depends(_get_workspace_service),
) -> ProjectWorkspaceDoc:
    result = await service.get_by_workspace_id(workspace_id)
    if result is None:
        raise WorkspaceNotFoundError()
    return result


@router.get("")
async def list_workspaces(
    service: WorkspaceService = Depends(_get_workspace_service),
) -> list[ProjectWorkspaceDoc]:
    return await service.list_all()


@router.delete("/{workspace_id}")
async def archive_workspace(
    workspace_id: str,
    service: WorkspaceService = Depends(_get_workspace_service),
) -> ProjectWorkspaceDoc:
    return await service.archive(workspace_id)
