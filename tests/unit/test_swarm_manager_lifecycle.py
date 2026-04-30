from unittest.mock import MagicMock, patch

from app.models.agent_node import AgentNodeDoc
from app.models.workspace import ProjectWorkspaceDoc
from app.swarm.manager import SwarmManager


def _make_node() -> AgentNodeDoc:
    return AgentNodeDoc(node_id="abcd1234-5678-9012-abcd-123456789012", name="test", role="writer", workspace_id="ws-001")


def _make_workspace() -> ProjectWorkspaceDoc:
    return ProjectWorkspaceDoc(workspace_id="ws-001", name="test-ws", volume_name="agentswarm-ws-ws-001")


def test_spawn_agent_injects_env_vars() -> None:
    with patch("app.swarm.manager.docker") as mock_docker:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_container = MagicMock()
        mock_container.id = "container-123"
        mock_client.containers.run.return_value = mock_container

        from app.core.config import Settings
        settings = Settings(hermes_api_base="http://test", hermes_api_key="sk-test")
        manager = SwarmManager(settings)

        node = _make_node()
        workspace = _make_workspace()
        result = manager.spawn_agent(node, workspace)

        assert result == "container-123"
        call_kwargs = mock_client.containers.run.call_args.kwargs
        assert call_kwargs["environment"]["GATEWAY_URL"] == "http://gateway:8000"
        assert call_kwargs["environment"]["AGENT_NODE_ID"] == node.node_id
        assert call_kwargs["network"] == "agentswarm-net"


def test_destroy_agent() -> None:
    with patch("app.swarm.manager.docker") as mock_docker:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container

        from app.core.config import Settings
        settings = Settings(hermes_api_base="http://test", hermes_api_key="sk-test")
        manager = SwarmManager(settings)

        manager.destroy_agent("container-123")
        mock_container.remove.assert_called_once_with(force=True)
