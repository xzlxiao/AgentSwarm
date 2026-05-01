import docker
from docker.models.containers import Container

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.agent_node import AgentNodeDoc
from app.models.workspace import ProjectWorkspaceDoc

logger = get_logger(__name__)


class SwarmManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = docker.from_env()

    def spawn_agent(self, node: AgentNodeDoc, workspace: ProjectWorkspaceDoc) -> str:
        container_name = f"worker-{node.node_id[:8]}"
        environment = {
            "GATEWAY_URL": f"http://gateway:{self._settings.gateway_port}",
            "AGENT_NODE_ID": node.node_id,
            "AGENT_INTERNAL_KEY": self._settings.agent_internal_key,
            "CONTAINER_NAME": container_name,
        }
        volumes = {workspace.volume_name: {"bind": "/workspace", "mode": "rw"}}

        container: Container = self._client.containers.run(
            image="hermes-worker:latest",
            name=container_name,
            environment=environment,
            volumes=volumes,
            network=self._settings.swarm_network_name,
            detach=True,
        )
        container_id: str = container.id or ""
        logger.info(
            "agent_spawned",
            node_id=node.node_id,
            container_id=container_id,
            container_name=container_name,
        )
        return container_id

    def pause_agent(self, container_id: str) -> None:
        container = self._client.containers.get(container_id)
        container.pause()
        logger.info("agent_paused", container_id=container_id)

    def resume_agent(self, container_id: str) -> None:
        container = self._client.containers.get(container_id)
        container.unpause()
        logger.info("agent_resumed", container_id=container_id)

    def destroy_agent(self, container_id: str) -> None:
        container = self._client.containers.get(container_id)
        container.remove(force=True)
        logger.info("agent_destroyed", container_id=container_id)
