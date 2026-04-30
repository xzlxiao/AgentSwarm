from typing import Any

from app.models.workspace import CreateWorkspaceRequest
from app.services.workspace_service import WorkspaceService


async def test_create_workspace(mock_db: Any, mock_volume_manager: Any) -> None:
    service = WorkspaceService(mock_db, mock_volume_manager)
    request = CreateWorkspaceRequest(name="project-alpha")
    result = await service.create(request)

    assert result.workspace_id != ""
    assert result.name == "project-alpha"
    assert result.status == "active"
    assert result.volume_name == "agentswarm-ws-test-ws-id"
    mock_volume_manager.create_workspace_volume.assert_called_once_with(result.workspace_id)


async def test_get_by_workspace_id(mock_db: Any, mock_volume_manager: Any) -> None:
    service = WorkspaceService(mock_db, mock_volume_manager)
    created = await service.create(CreateWorkspaceRequest(name="project-beta"))

    found = await service.get_by_workspace_id(created.workspace_id)
    assert found is not None
    assert found.name == "project-beta"


async def test_get_by_workspace_id_not_found(mock_db: Any, mock_volume_manager: Any) -> None:
    service = WorkspaceService(mock_db, mock_volume_manager)
    result = await service.get_by_workspace_id("nonexistent")
    assert result is None


async def test_list_all(mock_db: Any, mock_volume_manager: Any) -> None:
    service = WorkspaceService(mock_db, mock_volume_manager)
    await service.create(CreateWorkspaceRequest(name="ws1"))
    await service.create(CreateWorkspaceRequest(name="ws2"))

    results = await service.list_all()
    assert len(results) == 2


async def test_archive(mock_db: Any, mock_volume_manager: Any) -> None:
    service = WorkspaceService(mock_db, mock_volume_manager)
    created = await service.create(CreateWorkspaceRequest(name="to-archive"))

    archived = await service.archive(created.workspace_id)
    assert archived.status == "archived"
