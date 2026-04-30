from typing import Any

import pytest

from app.core.exceptions import AgentNotFoundError
from app.models.agent_node import WorkerRegisterRequest
from app.services.agent_service import AgentService


async def test_register_nonexistent_node_returns_404(mock_db: Any) -> None:
    service = AgentService(mock_db)

    register_req = WorkerRegisterRequest(
        container_id="cid-999",
        container_ip="172.18.0.99",
        container_port=3000,
    )
    with pytest.raises(AgentNotFoundError):
        await service.register_worker("nonexistent-node-id", register_req)

    count = await mock_db["agent_nodes"].count_documents({})
    assert count == 0
