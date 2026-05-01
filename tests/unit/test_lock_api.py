"""Lock API 端点测试"""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app


@pytest.fixture
def client(mock_settings: Settings) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_settings] = lambda: mock_settings
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(mock_settings: Settings) -> dict[str, str]:
    return {"X-Agent-Key": mock_settings.agent_internal_key}


@pytest.fixture
def mock_lock_service() -> Generator[MagicMock, None, None]:
    with patch("app.api.locks._get_lock_service") as mock_get:
        svc = MagicMock()
        svc.acquire_lock = AsyncMock()
        svc.release_lock = AsyncMock()
        svc.heartbeat = AsyncMock()
        svc.get_lock_status = AsyncMock()
        mock_get.return_value = svc
        yield svc


def _make_lock_doc(
    workspace_id: str = "ws-1",
    status: str = "locked",
    holder_node_id: str = "node-a",
    holder_container_id: str = "cid-a",
    wait_queue: list[dict[str, object]] | None = None,
    snapshot_id: str | None = None,
) -> dict[str, object]:
    return {
        "workspace_id": workspace_id,
        "status": status,
        "holder_node_id": holder_node_id,
        "holder_container_id": holder_container_id,
        "wait_queue": wait_queue or [],
        "snapshot_id": snapshot_id,
        "acquired_at": "2026-05-01T00:00:00Z",
        "last_heartbeat_at": "2026-05-01T00:00:00Z",
        "timeout_seconds": 600,
        "created_at": "2026-05-01T00:00:00Z",
        "updated_at": "2026-05-01T00:00:00Z",
    }


def test_acquire_success_200(
    client: TestClient, auth_headers: dict[str, str], mock_lock_service: MagicMock,
) -> None:
    mock_lock_service.acquire_lock.return_value = _make_lock_doc()

    resp = client.post(
        "/api/v1/internal/locks/acquire",
        json={"workspace_id": "ws-1", "node_id": "node-a", "container_id": "cid-a"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "locked"
    assert data["holder_node_id"] == "node-a"


def test_acquire_queued_200(
    client: TestClient, auth_headers: dict[str, str], mock_lock_service: MagicMock,
) -> None:
    mock_lock_service.acquire_lock.return_value = _make_lock_doc(
        holder_node_id="node-b", wait_queue=[{"node_id": "node-a", "container_id": "cid-a"}],
    )

    resp = client.post(
        "/api/v1/internal/locks/acquire",
        json={"workspace_id": "ws-1", "node_id": "node-a", "container_id": "cid-a"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_release_success_200(
    client: TestClient, auth_headers: dict[str, str], mock_lock_service: MagicMock,
) -> None:
    mock_lock_service.release_lock.return_value = _make_lock_doc(
        status="free", holder_node_id=None, snapshot_id="snap-001",
    )

    resp = client.post(
        "/api/v1/internal/locks/release",
        json={"workspace_id": "ws-1", "node_id": "node-a"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "released"
    assert data["snapshot_id"] == "snap-001"


def test_release_not_holder_403(
    client: TestClient, auth_headers: dict[str, str], mock_lock_service: MagicMock,
) -> None:
    from app.core.exceptions import NotLockHolderError

    mock_lock_service.release_lock.side_effect = NotLockHolderError()

    resp = client.post(
        "/api/v1/internal/locks/release",
        json={"workspace_id": "ws-1", "node_id": "node-b"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


def test_heartbeat_success_200(
    client: TestClient, auth_headers: dict[str, str], mock_lock_service: MagicMock,
) -> None:
    mock_lock_service.heartbeat.return_value = None

    resp = client.post(
        "/api/v1/internal/locks/heartbeat",
        json={"workspace_id": "ws-1", "node_id": "node-a"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_get_lock_status(
    client: TestClient, auth_headers: dict[str, str], mock_lock_service: MagicMock,
) -> None:
    mock_lock_service.get_lock_status.return_value = _make_lock_doc()

    resp = client.get("/api/v1/internal/locks/ws-1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["workspace_id"] == "ws-1"


def test_get_lock_status_free(
    client: TestClient, auth_headers: dict[str, str], mock_lock_service: MagicMock,
) -> None:
    from app.core.exceptions import LockNotFoundError

    mock_lock_service.get_lock_status.side_effect = LockNotFoundError()

    resp = client.get("/api/v1/internal/locks/ws-1", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "free"


def test_unauthorized_401(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/internal/locks/acquire",
        json={"workspace_id": "ws-1", "node_id": "node-a", "container_id": "cid-a"},
        headers={"X-Agent-Key": "wrong-key"},
    )
    assert resp.status_code == 401
