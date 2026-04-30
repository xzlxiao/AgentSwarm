import docker

from app.core.logging import get_logger

logger = get_logger(__name__)


class VolumeManager:
    def __init__(self) -> None:
        self._client = docker.from_env()

    def create_workspace_volume(self, workspace_id: str) -> str:
        volume_name = f"agentswarm-ws-{workspace_id}"
        try:
            self._client.volumes.get(volume_name)
            logger.info("volume_exists", volume_name=volume_name)
        except docker.errors.NotFound:  # type: ignore[union-attr]
            self._client.volumes.create(name=volume_name)
            logger.info("volume_created", volume_name=volume_name)
        return volume_name

    def volume_exists(self, volume_name: str) -> bool:
        try:
            self._client.volumes.get(volume_name)
            return True
        except (docker.errors.APIError, docker.errors.NotFound):  # type: ignore[union-attr]
            return False
