import gzip
import io
import os
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime

from docker import DockerClient
from docker.models.containers import Container

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SnapshotService:
    _SHORT_ID_LEN = 8

    def __init__(self, settings: Settings) -> None:
        self._base_dir = settings.snapshot_base_dir
        self._client = DockerClient.from_env()

    @contextmanager
    def _run_temp_container(self, volume_name: str, mode: str = "ro") -> Generator[Container, None, None]:
        container = self._client.containers.create(
            image="busybox:latest",
            volumes={volume_name: {"bind": "/data", "mode": mode}},
            command="tail -f /dev/null",
        )
        container.start()
        try:
            yield container
        finally:
            container.remove(force=True)

    def create_snapshot(self, workspace_id: str, volume_name: str, name: str) -> str:
        snapshot_id = str(uuid.uuid4())
        snap_dir = os.path.join(self._base_dir, workspace_id)
        os.makedirs(snap_dir, exist_ok=True)

        filename = f"{name}_{snapshot_id[:self._SHORT_ID_LEN]}.tar.gz"
        filepath = os.path.join(snap_dir, filename)

        with self._run_temp_container(volume_name, "ro") as container:
            stream, _ = container.get_archive("/data")
            with gzip.open(filepath, "wb") as gz:
                for chunk in stream:
                    gz.write(chunk)

        logger.info("snapshot_created", workspace_id=workspace_id, snapshot_id=snapshot_id, filename=filename)
        return snapshot_id

    def restore_snapshot(self, workspace_id: str, snapshot_id: str, volume_name: str) -> None:
        snap_dir = os.path.join(self._base_dir, workspace_id)
        if not os.path.isdir(snap_dir):
            raise FileNotFoundError(f"No snapshots directory for workspace {workspace_id}")
        target_file: str | None = None
        for f in os.listdir(snap_dir):
            if snapshot_id[:self._SHORT_ID_LEN] in f and f.endswith(".tar.gz"):
                target_file = os.path.join(snap_dir, f)
                break

        if target_file is None:
            raise FileNotFoundError(f"Snapshot {snapshot_id} not found")

        with self._run_temp_container(volume_name, "rw") as container:
            container.exec_run("sh -c 'rm -rf /data/..?* /data/.[!.]* /data/*'")
            with gzip.open(target_file, "rb") as gz:
                tar_bytes = gz.read()
            container.put_archive("/data/", io.BytesIO(tar_bytes))

        logger.info("snapshot_restored", snapshot_id=snapshot_id, workspace_id=workspace_id)

    def list_snapshots(self, workspace_id: str) -> list[dict[str, str | int]]:
        snap_dir = os.path.join(self._base_dir, workspace_id)
        if not os.path.isdir(snap_dir):
            return []

        results: list[dict[str, str | int]] = []
        for f in os.listdir(snap_dir):
            if not f.endswith(".tar.gz"):
                continue
            path = os.path.join(snap_dir, f)
            stat = os.stat(path)
            results.append({
                "filename": f,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime, tz=UTC).isoformat(),
            })
        return results
