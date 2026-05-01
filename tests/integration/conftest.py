from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast
from unittest.mock import MagicMock
import tempfile

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import AgentSwarmError, agentswarm_error_handler
from app.core.logging import configure_logging
from app.api.router import router
from app.api.workspaces import _get_workspace_service, WorkspaceService  # pyright: ignore[reportPrivateUsage]
from app.services.gateway_service import GatewayService
from app.swarm.volume import VolumeManager
from tests.conftest import AsyncMockDatabase


class _MockHermesResponse:
    def __init__(self, data: dict[str, object]) -> None:
        self._data = data

    def json(self) -> dict[str, object]:
        return self._data

    def raise_for_status(self) -> None:
        pass


class _MockHttpxClient:
    def __init__(self, response_data: dict[str, object]) -> None:
        self._response_data = response_data

    async def post(self, url: str, **kwargs: Any) -> _MockHermesResponse:
        return _MockHermesResponse(self._response_data)

    async def aclose(self) -> None:
        pass


@pytest.fixture
def mock_hermes_data() -> dict[str, object]:
    return {
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "choices": [{"message": {"content": "test response"}}],
    }


@pytest.fixture
def gateway_client(mock_db: AsyncMockDatabase, mock_settings: Settings, mock_hermes_data: dict[str, object]):
    configure_logging("warning")

    mock_vm = MagicMock(spec=VolumeManager)
    mock_vm.create_workspace_volume.return_value = "agentswarm-ws-test"

    gw = GatewayService(cast(Any, mock_db), mock_settings)
    cast(Any, gw)._client = _MockHttpxClient(mock_hermes_data)

    @asynccontextmanager
    async def test_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        app.state.db = mock_db
        app.state.gateway_service = gw
        app.state.swarm_manager = None
        yield

    test_app = FastAPI(lifespan=test_lifespan)
    test_app.add_exception_handler(AgentSwarmError, agentswarm_error_handler)  # type: ignore[arg-type]
    test_app.include_router(router)

    def _mock_ws(request: Request) -> WorkspaceService:
        return WorkspaceService(request.app.state.db, mock_vm)

    test_app.dependency_overrides[_get_workspace_service] = _mock_ws

    with TestClient(test_app) as client:
        yield client


@pytest.fixture
def worker_client():
    from worker.config import WorkerSettings
    from worker.runner import TaskRunner
    from worker.main import health_check, receive_task, get_status

    with tempfile.TemporaryDirectory() as tmpdir:
        settings = WorkerSettings(
            gateway_url="http://localhost:8000",
            agent_node_id="test-worker-node",
        )
        runner = TaskRunner(workspace_path=tmpdir)

        @asynccontextmanager
        async def test_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            app.state.settings = settings
            app.state.runner = runner
            yield

        test_app = FastAPI(lifespan=test_lifespan)
        test_app.add_api_route("/health", health_check, methods=["GET"])
        test_app.add_api_route("/task", receive_task, methods=["POST"])
        test_app.add_api_route("/status", get_status, methods=["GET"])

        with TestClient(test_app) as client:
            yield client
