# pyright: reportPrivateUsage=none
from typing import Any
from unittest.mock import MagicMock, patch

from app.models.agent_node import CreateAgentNodeRequest
from app.models.task import ChatCompletionRequest
from app.services.agent_service import AgentService
from app.services.gateway_service import GatewayService


async def test_proxy_builds_correct_request(mock_db: Any, mock_settings: Any) -> None:
    agent_service = AgentService(mock_db)
    await agent_service.create(CreateAgentNodeRequest(name="a1", role="writer", workspace_id="ws-001"))
    agents = await agent_service.list_by_workspace("ws-001")
    await agent_service.update_status(agents[0].node_id, "running")

    gateway_service = GatewayService(mock_db, mock_settings)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "hello", "tool_calls": None}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    with patch.object(gateway_service._client, "post", return_value=mock_response) as mock_post:
        request = ChatCompletionRequest(
            agent_node_id=agents[0].node_id,
            workspace_id="ws-001",
            messages=[{"role": "user", "content": "hi"}],
        )
        result = await gateway_service.proxy_chat_completion(request)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer sk-test-key-123456"
        assert call_args.kwargs["json"]["model"] == "test-model"
        assert result.content == "hello"
        assert result.usage.total_tokens == 15

    await gateway_service.close()


async def test_proxy_uses_custom_model(mock_db: Any, mock_settings: Any) -> None:
    agent_service = AgentService(mock_db)
    await agent_service.create(CreateAgentNodeRequest(name="a1", role="writer", workspace_id="ws-001"))
    agents = await agent_service.list_by_workspace("ws-001")
    await agent_service.update_status(agents[0].node_id, "running")

    gateway_service = GatewayService(mock_db, mock_settings)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }

    with patch.object(gateway_service._client, "post", return_value=mock_response) as mock_post:
        request = ChatCompletionRequest(
            agent_node_id=agents[0].node_id,
            workspace_id="ws-001",
            messages=[{"role": "user", "content": "hi"}],
            model="custom-model",
        )
        await gateway_service.proxy_chat_completion(request)

        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["model"] == "custom-model"

    await gateway_service.close()
