"""SnapshotService 单元测试"""

import io
import os
import tarfile
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.snapshot_service import SnapshotService


@pytest.fixture
def snapshot_dir(tmp_path: Any) -> str:
    return str(tmp_path / "snapshots")


@pytest.fixture
def settings(snapshot_dir: str) -> Settings:
    return Settings(snapshot_base_dir=snapshot_dir)


def _make_tar_bytes() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name="test.txt")
        data = b"hello world"
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


@pytest.fixture
def docker_mocks(settings: Settings) -> Generator[tuple[SnapshotService, MagicMock, MagicMock], None, None]:
    """创建 SnapshotService 及其 Docker mock，返回 (service, mock_container, mock_client)"""
    with patch("app.services.snapshot_service.DockerClient") as mock_cls:
        mock_container = MagicMock()
        mock_container.get_archive.return_value = (iter([_make_tar_bytes()]), None)
        mock_client = MagicMock()
        mock_client.containers.create.return_value = mock_container
        mock_cls.from_env.return_value = mock_client
        yield SnapshotService(settings), mock_container, mock_client


def test_create_snapshot(docker_mocks: tuple[SnapshotService, MagicMock, MagicMock], settings: Settings) -> None:
    service, mock_container, _ = docker_mocks
    snapshot_id = service.create_snapshot("ws-001", "vol-001", "test-snap")

    assert snapshot_id != ""
    snap_dir = os.path.join(settings.snapshot_base_dir, "ws-001")
    files = os.listdir(snap_dir)
    assert len(files) == 1
    assert files[0].startswith("test-snap_")
    assert files[0].endswith(".tar.gz")
    mock_container.remove.assert_called_once_with(force=True)


def test_restore_snapshot(docker_mocks: tuple[SnapshotService, MagicMock, MagicMock]) -> None:
    service, _, mock_client = docker_mocks
    snapshot_id = service.create_snapshot("ws-001", "vol-001", "restore-test")

    mock_container2 = MagicMock()
    mock_client.containers.create.return_value = mock_container2
    service.restore_snapshot("ws-001", snapshot_id, "vol-001")

    mock_container2.exec_run.assert_called_once()
    mock_container2.put_archive.assert_called_once()
    mock_container2.remove.assert_called_once_with(force=True)


def test_restore_snapshot_not_found(settings: Settings) -> None:
    with patch("app.services.snapshot_service.DockerClient"):
        service = SnapshotService(settings)
    os.makedirs(os.path.join(settings.snapshot_base_dir, "ws-001"), exist_ok=True)
    with pytest.raises(FileNotFoundError, match="Snapshot .* not found"):
        service.restore_snapshot("ws-001", "nonexistent-id", "vol-001")


def test_restore_snapshot_dir_not_found(settings: Settings) -> None:
    with patch("app.services.snapshot_service.DockerClient"):
        service = SnapshotService(settings)
    with pytest.raises(FileNotFoundError, match="No snapshots directory"):
        service.restore_snapshot("ws-001", "some-id", "vol-001")


def test_list_snapshots_empty(settings: Settings) -> None:
    with patch("app.services.snapshot_service.DockerClient"):
        service = SnapshotService(settings)
    result = service.list_snapshots("ws-001")
    assert result == []


def test_list_snapshots_returns_entries(docker_mocks: tuple[SnapshotService, MagicMock, MagicMock]) -> None:
    service, _, _ = docker_mocks
    service.create_snapshot("ws-002", "vol-002", "list-test")

    result = service.list_snapshots("ws-002")
    assert len(result) == 1
    assert "filename" in result[0]
    assert "size_bytes" in result[0]
    assert "created_at" in result[0]
