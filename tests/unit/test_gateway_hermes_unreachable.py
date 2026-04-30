# pyright: reportPrivateUsage=none
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from app.core.exceptions import HermesAPIError
from app.models.agent_node import CreateAgentNodeRequest
from app.models.task import ChatCompletionRequest
from app.services.agent_service import AgentService
from app.services.gateway_service import GatewayService


async def test_hermes_unreachable_returns_502(mock_db: Any, mock_settings: Any) -> None:
    agent_service = AgentService(mock_db)
    await agent_service.create(CreateAgentNodeRequest(name="a1", role="writer", workspace_id="ws-001"))
    agents = await agent_service.list_by_workspace("ws-001")
    node_id = agents[0].node_id
    await agent_service.update_status(node_id, "running")

    gateway_service = GatewayService(mock_db, mock_settings)

    with patch.object(gateway_service._client, "post", side_effect=httpx.ConnectError("connection refused")):
        request = ChatCompletionRequest(
            agent_node_id=node_id,
            workspace_id="ws-001",
            messages=[{"role": "user", "content": "hi"}],
        )
        with pytest.raises(HermesAPIError):
            await gateway_service.proxy_chat_completion(request)

    agent = await agent_service.get_by_node_id(node_id)
    assert agent is not None
    assert agent.status == "running"

    token_doc = await mock_db["token_usage"].find_one({"agent_node_id": node_id})
    assert token_doc is None

    await gateway_service.close()
