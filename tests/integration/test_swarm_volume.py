"""Volume 创建 + 容器挂载测试."""

from unittest.mock import MagicMock, patch

import docker.errors

from app.swarm.volume import VolumeManager


def test_create_workspace_volume_existing():
    """已存在的 volume 直接返回名称."""
    mock_client = MagicMock()
    mock_client.volumes.get.return_value = MagicMock()

    with patch("app.swarm.volume.docker.from_env", return_value=mock_client):
        vm = VolumeManager()
        volume_name = vm.create_workspace_volume("test-ws-id")

    assert volume_name == "agentswarm-ws-test-ws-id"
    mock_client.volumes.get.assert_called_once_with("agentswarm-ws-test-ws-id")
    mock_client.volumes.create.assert_not_called()


def test_create_workspace_volume_creates_new():
    """不存在的 volume 创建后返回名称."""
    mock_client = MagicMock()
    mock_client.volumes.get.side_effect = docker.errors.NotFound("not found")
    mock_client.volumes.create.return_value = MagicMock()

    with patch("app.swarm.volume.docker.from_env", return_value=mock_client):
        vm = VolumeManager()
        volume_name = vm.create_workspace_volume("new-ws")

    assert volume_name == "agentswarm-ws-new-ws"
    mock_client.volumes.create.assert_called_once_with(name="agentswarm-ws-new-ws")


def test_volume_exists_true():
    """volume_exists 对存在的 volume 返回 True."""
    mock_client = MagicMock()
    mock_client.volumes.get.return_value = MagicMock()

    with patch("app.swarm.volume.docker.from_env", return_value=mock_client):
        vm = VolumeManager()
        assert vm.volume_exists("agentswarm-ws-test") is True


def test_volume_exists_false():
    """volume_exists 对不存在的 volume 返回 False."""
    mock_client = MagicMock()
    mock_client.volumes.get.side_effect = docker.errors.NotFound("not found")

    with patch("app.swarm.volume.docker.from_env", return_value=mock_client):
        vm = VolumeManager()
        assert vm.volume_exists("agentswarm-ws-missing") is False
