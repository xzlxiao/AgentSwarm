from typing import Any

from app.models.agent_node import CreateAgentNodeRequest, WorkerRegisterRequest
from app.services.agent_service import AgentService


async def test_create_agent(mock_db: Any) -> None:
    service = AgentService(mock_db)
    request = CreateAgentNodeRequest(name="writer-1", role="writer", workspace_id="ws-001")
    result = await service.create(request)

    assert result.node_id != ""
    assert result.name == "writer-1"
    assert result.role == "writer"
    assert result.status == "pending"
    assert result.workspace_id == "ws-001"


async def test_get_by_node_id(mock_db: Any) -> None:
    service = AgentService(mock_db)
    request = CreateAgentNodeRequest(name="reviewer-1", role="reviewer", workspace_id="ws-001")
    created = await service.create(request)

    found = await service.get_by_node_id(created.node_id)
    assert found is not None
    assert found.node_id == created.node_id
    assert found.name == "reviewer-1"


async def test_get_by_node_id_not_found(mock_db: Any) -> None:
    service = AgentService(mock_db)
    result = await service.get_by_node_id("nonexistent")
    assert result is None


async def test_list_by_workspace(mock_db: Any) -> None:
    service = AgentService(mock_db)
    await service.create(CreateAgentNodeRequest(name="a1", role="writer", workspace_id="ws-001"))
    await service.create(CreateAgentNodeRequest(name="a2", role="reviewer", workspace_id="ws-001"))
    await service.create(CreateAgentNodeRequest(name="a3", role="coordinator", workspace_id="ws-002"))

    results = await service.list_by_workspace("ws-001")
    assert len(results) == 2


async def test_update_status(mock_db: Any) -> None:
    service = AgentService(mock_db)
    created = await service.create(CreateAgentNodeRequest(name="a1", role="writer", workspace_id="ws-001"))

    updated = await service.update_status(created.node_id, "running")
    assert updated.status == "running"


async def test_destroy(mock_db: Any) -> None:
    service = AgentService(mock_db)
    created = await service.create(CreateAgentNodeRequest(name="a1", role="writer", workspace_id="ws-001"))

    destroyed = await service.destroy(created.node_id)
    assert destroyed.status == "destroyed"


async def test_register_worker(mock_db: Any) -> None:
    service = AgentService(mock_db)
    created = await service.create(CreateAgentNodeRequest(name="a1", role="writer", workspace_id="ws-001"))

    register_req = WorkerRegisterRequest(
        container_id="cid-123",
        container_ip="172.18.0.4",
        container_port=3000,
    )
    registered = await service.register_worker(created.node_id, register_req)

    assert registered.status == "running"
    assert registered.container_id == "cid-123"
    assert registered.container_ip == "172.18.0.4"
