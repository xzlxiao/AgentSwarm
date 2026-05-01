"""MCP lock 工具分发测试"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from worker.mcp_server import _handle_acquire_lock, _handle_release_lock


@pytest.fixture
def mock_gateway() -> MagicMock:
    gw = MagicMock()
    gw.acquire_lock = AsyncMock(return_value={"status": "locked", "workspace_id": "ws-1", "holder_node_id": "node-a"})
    gw.release_lock = AsyncMock(return_value={"status": "released", "snapshot_id": "snap-001", "next_holder": None})
    return gw


async def test_acquire_lock_dispatch(mock_gateway: MagicMock) -> None:
    with patch("worker.mcp_server._get_gateway", return_value=mock_gateway):
        result = await _handle_acquire_lock({
            "workspace_id": "ws-1",
            "node_id": "node-a",
            "container_id": "cid-a",
        })

    data = json.loads(result[0].text)
    assert data["status"] == "locked"
    mock_gateway.acquire_lock.assert_awaited_once_with("ws-1", "node-a", "cid-a", None)


async def test_acquire_lock_dispatch_with_timeout(mock_gateway: MagicMock) -> None:
    with patch("worker.mcp_server._get_gateway", return_value=mock_gateway):
        result = await _handle_acquire_lock({
            "workspace_id": "ws-1",
            "node_id": "node-a",
            "container_id": "cid-a",
            "timeout_seconds": 300,
        })

    data = json.loads(result[0].text)
    assert data["status"] == "locked"
    mock_gateway.acquire_lock.assert_awaited_once_with("ws-1", "node-a", "cid-a", 300)


async def test_release_lock_dispatch(mock_gateway: MagicMock) -> None:
    with patch("worker.mcp_server._get_gateway", return_value=mock_gateway):
        result = await _handle_release_lock({
            "workspace_id": "ws-1",
            "node_id": "node-a",
        })

    data = json.loads(result[0].text)
    assert data["status"] == "released"
    mock_gateway.release_lock.assert_awaited_once_with("ws-1", "node-a")
