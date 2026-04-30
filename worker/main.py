import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request

from worker.config import WorkerSettings
from worker.models import WorkerTaskPayload
from worker.runner import TaskRunner

logger = structlog.get_logger("worker")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = WorkerSettings()
    runner = TaskRunner()
    app.state.settings = settings
    app.state.runner = runner
    asyncio.create_task(_register_with_gateway(app))
    yield


async def _register_with_gateway(app: FastAPI) -> None:
    settings: WorkerSettings = app.state.settings
    register_url = f"{settings.gateway_url}/api/v1/agents/{settings.agent_node_id}/register"
    delays = [2, 4, 8]

    async with httpx.AsyncClient() as client:
        for delay in delays:
            try:
                resp = await client.post(
                    register_url,
                    json={
                        "container_id": "local",
                        "container_ip": "127.0.0.1",
                        "container_port": 3000,
                    },
                )
                if resp.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(delay)

    logger.error("registration_failed", agent_node_id=settings.agent_node_id)


app = FastAPI(title="AgentSwarm Worker", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health_check(request: Request) -> dict[str, str]:
    settings: WorkerSettings = request.app.state.settings
    return {"status": "ok", "agent_node_id": settings.agent_node_id}


@app.post("/task")
async def receive_task(payload: WorkerTaskPayload, request: Request) -> dict[str, str]:
    runner: TaskRunner = request.app.state.runner
    asyncio.create_task(runner.execute(payload))
    return {"status": "accepted", "task_id": payload.task_id}


@app.get("/status")
async def get_status(request: Request) -> dict[str, object]:
    runner: TaskRunner = request.app.state.runner
    settings: WorkerSettings = request.app.state.settings
    return {
        "agent_node_id": settings.agent_node_id,
        "status": runner.status,
        "current_task_id": runner.current_task_id,
        "execution_summary": runner.execution_summary,
    }
