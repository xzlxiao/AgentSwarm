from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.core.exceptions import LockNotAvailableError, LockNotFoundError, NotLockHolderError
from app.services.lock_service import LockService


@pytest.fixture
def mock_snapshot_service() -> MagicMock:
    svc = MagicMock()
    svc.create_snapshot.return_value = "snap-001"
    return svc


@pytest.fixture
def lock_service(mock_db: Any, mock_snapshot_service: MagicMock, mock_settings: Settings) -> LockService:
    return LockService(mock_db, mock_snapshot_service, mock_settings)


async def test_acquire_free_to_locked(mock_db: Any, lock_service: LockService) -> None:
    result = await lock_service.acquire_lock("ws-1", "node-a", "cid-a")

    assert result["status"] == "locked"
    assert result["holder_node_id"] == "node-a"
    assert result["holder_container_id"] == "cid-a"


async def test_acquire_locked_to_queued(mock_db: Any, lock_service: LockService) -> None:
    await lock_service.acquire_lock("ws-1", "node-a", "cid-a")
    result = await lock_service.acquire_lock("ws-1", "node-b", "cid-b")

    assert result["status"] == "locked"
    assert result["holder_node_id"] == "node-a"
    assert len(result["wait_queue"]) == 1
    assert result["wait_queue"][0]["node_id"] == "node-b"


async def test_acquire_duplicate_node_rejected(mock_db: Any, lock_service: LockService) -> None:
    await lock_service.acquire_lock("ws-1", "node-a", "cid-a")
    result = await lock_service.acquire_lock("ws-1", "node-a", "cid-a")

    assert len(result["wait_queue"]) == 0
    assert result["holder_node_id"] == "node-a"


async def test_acquire_queue_depth_limit(mock_db: Any, lock_service: LockService) -> None:
    await lock_service.acquire_lock("ws-1", "node-a", "cid-a")
    for i in range(10):
        await lock_service.acquire_lock("ws-1", f"node-q{i}", f"cid-q{i}")

    with pytest.raises(LockNotAvailableError):
        await lock_service.acquire_lock("ws-1", "node-overflow", "cid-overflow")


async def test_acquire_upsert_new_doc(mock_db: Any, lock_service: LockService) -> None:
    result = await lock_service.acquire_lock("ws-new", "node-a", "cid-a")

    assert result["status"] == "locked"
    assert result["holder_node_id"] == "node-a"


async def test_release_with_snapshot(mock_db: Any, lock_service: LockService, mock_snapshot_service: MagicMock) -> None:
    await mock_db["project_workspaces"].insert_one({"workspace_id": "ws-1", "volume_name": "vol-1"})
    await lock_service.acquire_lock("ws-1", "node-a", "cid-a")

    result = await lock_service.release_lock("ws-1", "node-a")

    assert result["status"] == "free"
    assert result["snapshot_id"] == "snap-001"
    mock_snapshot_service.create_snapshot.assert_called_once()


async def test_release_snapshot_fails(mock_db: Any, lock_service: LockService, mock_snapshot_service: MagicMock) -> None:
    await mock_db["project_workspaces"].insert_one({"workspace_id": "ws-1", "volume_name": "vol-1"})
    mock_snapshot_service.create_snapshot.side_effect = RuntimeError("disk full")
    await lock_service.acquire_lock("ws-1", "node-a", "cid-a")

    result = await lock_service.release_lock("ws-1", "node-a")

    assert result["status"] == "free"
    assert result["snapshot_id"] is None


async def test_release_workspace_not_found(mock_db: Any, lock_service: LockService) -> None:
    await lock_service.acquire_lock("ws-1", "node-a", "cid-a")

    result = await lock_service.release_lock("ws-1", "node-a")

    assert result["status"] == "free"
    assert result["snapshot_id"] is None


async def test_release_not_holder(mock_db: Any, lock_service: LockService) -> None:
    await lock_service.acquire_lock("ws-1", "node-a", "cid-a")

    with pytest.raises(NotLockHolderError):
        await lock_service.release_lock("ws-1", "node-b")


async def test_release_empty_queue(mock_db: Any, lock_service: LockService) -> None:
    await lock_service.acquire_lock("ws-1", "node-a", "cid-a")

    result = await lock_service.release_lock("ws-1", "node-a")

    assert result["status"] == "free"
    assert result["holder_node_id"] is None


async def test_release_with_wait_queue(mock_db: Any, lock_service: LockService) -> None:
    await lock_service.acquire_lock("ws-1", "node-a", "cid-a")
    await lock_service.acquire_lock("ws-1", "node-b", "cid-b")

    result = await lock_service.release_lock("ws-1", "node-a")

    assert result["holder_node_id"] == "node-b"
    assert result["holder_container_id"] == "cid-b"


async def test_heartbeat_updates(mock_db: Any, lock_service: LockService) -> None:
    await lock_service.acquire_lock("ws-1", "node-a", "cid-a")

    await lock_service.heartbeat("ws-1", "node-a")

    doc = await lock_service.get_lock_status("ws-1")
    assert doc["holder_node_id"] == "node-a"


async def test_heartbeat_not_holder(mock_db: Any, lock_service: LockService) -> None:
    await lock_service.acquire_lock("ws-1", "node-a", "cid-a")

    with pytest.raises(NotLockHolderError):
        await lock_service.heartbeat("ws-1", "node-b")


async def test_reclaim_expired(mock_db: Any, lock_service: LockService, mock_settings: Settings) -> None:
    await mock_db["project_workspaces"].insert_one({"workspace_id": "ws-1", "volume_name": "vol-1"})
    await lock_service.acquire_lock("ws-1", "node-a", "cid-a")

    old_hb = datetime.now(UTC) - timedelta(seconds=mock_settings.default_lock_timeout_seconds + 60)
    await mock_db["workspace_locks"].find_one_and_update(
        {"workspace_id": "ws-1"},
        {"$set": {"last_heartbeat_at": old_hb}},
    )

    reclaimed = await lock_service.reclaim_expired_locks()
    assert reclaimed == 1

    doc = await lock_service.get_lock_status("ws-1")
    assert doc["status"] == "free"


async def test_reclaim_container_alive(mock_db: Any, mock_snapshot_service: MagicMock, mock_settings: Settings) -> None:
    swarm = MagicMock()
    container_mock = MagicMock()
    container_mock.status = "running"
    swarm.client.containers.get.return_value = container_mock

    svc = LockService(
        mock_db, mock_snapshot_service, mock_settings, swarm_manager=swarm,
    )
    await svc.acquire_lock("ws-1", "node-a", "cid-a")

    old_hb = datetime.now(UTC) - timedelta(seconds=mock_settings.default_lock_timeout_seconds + 60)
    await mock_db["workspace_locks"].find_one_and_update(
        {"workspace_id": "ws-1"},
        {"$set": {"last_heartbeat_at": old_hb}},
    )

    reclaimed = await svc.reclaim_expired_locks()
    assert reclaimed == 0


async def test_get_lock_status_not_found(mock_db: Any, lock_service: LockService) -> None:
    with pytest.raises(LockNotFoundError):
        await lock_service.get_lock_status("nonexistent")
