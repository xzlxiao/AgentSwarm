"""AgentService 状态机校验测试"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import InvalidStatusTransition
from app.models.agent_node import CreateAgentNodeRequest, WorkerRegisterRequest
from app.services.agent_service import AgentService
from app.swarm.manager import SwarmManager


@pytest.fixture
def swarm_manager() -> MagicMock:
    return MagicMock(spec=SwarmManager)


async def _create_and_register(
    service: AgentService, name: str = "test-agent", workspace_id: str = "ws-001"
) -> str:
    created = await service.create(
        CreateAgentNodeRequest(name=name, role="writer", workspace_id=workspace_id)
    )
    # Register worker to move to "running" with container_id
    await service.register_worker(
        created.node_id,
        WorkerRegisterRequest(
            container_id="cid-123", container_ip="172.18.0.4", container_port=3000
        ),
    )
    return created.node_id


async def test_pending_to_running(mock_db: Any) -> None:
    service = AgentService(mock_db)
    created = await service.create(
        CreateAgentNodeRequest(name="a1", role="writer", workspace_id="ws-001")
    )
    updated = await service.update_status(created.node_id, "running")
    assert updated.status == "running"


async def test_pending_to_destroyed(mock_db: Any) -> None:
    service = AgentService(mock_db)
    created = await service.create(
        CreateAgentNodeRequest(name="a1", role="writer", workspace_id="ws-001")
    )
    updated = await service.update_status(created.node_id, "destroyed")
    assert updated.status == "destroyed"


async def test_running_to_paused(mock_db: Any) -> None:
    service = AgentService(mock_db)
    node_id = await _create_and_register(service)
    updated = await service.update_status(node_id, "paused")
    assert updated.status == "paused"


async def test_running_to_destroyed(mock_db: Any) -> None:
    service = AgentService(mock_db)
    node_id = await _create_and_register(service)
    updated = await service.update_status(node_id, "destroyed")
    assert updated.status == "destroyed"


async def test_paused_to_running(mock_db: Any) -> None:
    service = AgentService(mock_db)
    node_id = await _create_and_register(service)
    await service.update_status(node_id, "paused")
    updated = await service.update_status(node_id, "running")
    assert updated.status == "running"


async def test_paused_to_destroyed(mock_db: Any) -> None:
    service = AgentService(mock_db)
    node_id = await _create_and_register(service)
    await service.update_status(node_id, "paused")
    updated = await service.update_status(node_id, "destroyed")
    assert updated.status == "destroyed"


async def test_invalid_pending_to_paused(mock_db: Any) -> None:
    service = AgentService(mock_db)
    created = await service.create(
        CreateAgentNodeRequest(name="a1", role="writer", workspace_id="ws-001")
    )
    with pytest.raises(InvalidStatusTransition):
        await service.update_status(created.node_id, "paused")


async def test_invalid_destroyed_to_running(mock_db: Any) -> None:
    service = AgentService(mock_db)
    node_id = await _create_and_register(service)
    await service.update_status(node_id, "destroyed")
    with pytest.raises(InvalidStatusTransition):
        await service.update_status(node_id, "running")


async def test_invalid_running_to_running(mock_db: Any) -> None:
    service = AgentService(mock_db)
    node_id = await _create_and_register(service)
    with pytest.raises(InvalidStatusTransition):
        await service.update_status(node_id, "running")


async def test_swarm_manager_pause_called(mock_db: Any, swarm_manager: MagicMock) -> None:
    service = AgentService(mock_db, swarm_manager=swarm_manager)
    node_id = await _create_and_register(service)
    await service.update_status(node_id, "paused")
    swarm_manager.pause_agent.assert_called_once_with("cid-123")


async def test_swarm_manager_resume_called(mock_db: Any, swarm_manager: MagicMock) -> None:
    service = AgentService(mock_db, swarm_manager=swarm_manager)
    node_id = await _create_and_register(service)
    await service.update_status(node_id, "paused")
    await service.update_status(node_id, "running")
    swarm_manager.resume_agent.assert_called_once_with("cid-123")


async def test_swarm_manager_destroy_called_on_update(mock_db: Any, swarm_manager: MagicMock) -> None:
    service = AgentService(mock_db, swarm_manager=swarm_manager)
    node_id = await _create_and_register(service)
    await service.update_status(node_id, "destroyed")
    swarm_manager.destroy_agent.assert_called_once_with("cid-123")


async def test_swarm_manager_destroy_called(mock_db: Any, swarm_manager: MagicMock) -> None:
    service = AgentService(mock_db, swarm_manager=swarm_manager)
    node_id = await _create_and_register(service)
    await service.destroy(node_id)
    swarm_manager.destroy_agent.assert_called_once_with("cid-123")


async def test_no_swarm_manager_still_updates_status(mock_db: Any) -> None:
    service = AgentService(mock_db)
    node_id = await _create_and_register(service)
    updated = await service.update_status(node_id, "paused")
    assert updated.status == "paused"
