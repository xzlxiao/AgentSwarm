"""Internal API 端点测试"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

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
def mock_snapshot_service() -> Generator[MagicMock, None, None]:
    with patch("app.api.internal.SnapshotService") as mock_cls:
        mock_svc = MagicMock()
        mock_cls.return_value = mock_svc
        yield mock_svc


def test_create_snapshot_success(client: TestClient, auth_headers: dict[str, str], mock_snapshot_service: MagicMock) -> None:
    mock_snapshot_service.create_snapshot.return_value = "snap-uuid-123"

    resp = client.post(
        "/api/v1/internal/snapshots/create",
        json={"workspace_id": "ws-001", "volume_name": "vol-001", "name": "test-snap"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["snapshot_id"] == "snap-uuid-123"


def test_restore_snapshot_success(client: TestClient, auth_headers: dict[str, str], mock_snapshot_service: MagicMock) -> None:
    mock_snapshot_service.restore_snapshot.return_value = None

    resp = client.post(
        "/api/v1/internal/snapshots/restore",
        json={"workspace_id": "ws-001", "snapshot_id": "snap-123", "volume_name": "vol-001"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_snapshot_unauthorized(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/internal/snapshots/create",
        json={"workspace_id": "ws-001", "volume_name": "vol-001", "name": "test-snap"},
        headers={"X-Agent-Key": "wrong-key"},
    )
    assert resp.status_code == 401


def test_restore_snapshot_unauthorized(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/internal/snapshots/restore",
        json={"workspace_id": "ws-001", "snapshot_id": "snap-123", "volume_name": "vol-001"},
        headers={"X-Agent-Key": "wrong-key"},
    )
    assert resp.status_code == 401


def test_create_snapshot_no_key(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/internal/snapshots/create",
        json={"workspace_id": "ws-001", "volume_name": "vol-001", "name": "test-snap"},
    )
    assert resp.status_code == 422
