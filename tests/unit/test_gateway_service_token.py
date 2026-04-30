# pyright: reportPrivateUsage=none
from typing import Any
from unittest.mock import MagicMock, patch

from app.models.agent_node import CreateAgentNodeRequest
from app.models.task import ChatCompletionRequest
from app.services.agent_service import AgentService
from app.services.gateway_service import GatewayService


async def test_token_usage_recorded_on_success(mock_db: Any, mock_settings: Any) -> None:
    agent_service = AgentService(mock_db)
    await agent_service.create(CreateAgentNodeRequest(name="a1", role="writer", workspace_id="ws-001"))
    agents = await agent_service.list_by_workspace("ws-001")
    node_id = agents[0].node_id
    await agent_service.update_status(node_id, "running")

    gateway_service = GatewayService(mock_db, mock_settings)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "result"}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
    }

    with patch.object(gateway_service._client, "post", return_value=mock_response):
        request = ChatCompletionRequest(
            agent_node_id=node_id,
            workspace_id="ws-001",
            messages=[{"role": "user", "content": "hi"}],
            model=None,
            temperature=0.7,
            max_tokens=None,
            tools=None,
        )
        result = await gateway_service.proxy_chat_completion(request)

        assert result.usage.total_tokens == 30
        assert result.usage.prompt_tokens == 20
        assert result.usage.completion_tokens == 10

        token_doc = await mock_db["token_usage"].find_one({"agent_node_id": node_id})
        assert token_doc is not None
        assert token_doc["total_tokens"] == 30
        assert token_doc["api_key_suffix"] == "3456"

    await gateway_service.close()
