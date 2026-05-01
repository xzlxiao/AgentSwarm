import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import ensure_indexes, get_database, mongo_lifespan
from app.core.exceptions import AgentSwarmError, agentswarm_error_handler
from app.core.logging import configure_logging, get_logger
from app.api.router import router
from app.services.gateway_service import GatewayService
from app.services.lock_service import LockService
from app.services.snapshot_service import SnapshotService
from app.swarm.manager import SwarmManager

logger = get_logger(__name__)


async def _reclaim_loop(lock_service: LockService, interval: int) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            reclaimed = await lock_service.reclaim_expired_locks()
            if reclaimed > 0:
                logger.info("locks_reclaimed", count=reclaimed)
        except Exception:
            logger.error("reclaim_loop_error", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    async with mongo_lifespan(settings) as client:
        db = get_database(client, settings)
        await ensure_indexes(db)
        app.state.mongo_client = client
        app.state.db = db
        app.state.gateway_service = GatewayService(db, settings)
        app.state.swarm_manager = SwarmManager(settings)

        snapshot_service = SnapshotService(settings)
        lock_service = LockService(db, snapshot_service, settings, app.state.swarm_manager)
        app.state.lock_service = lock_service

        reclaim_task = asyncio.create_task(
            _reclaim_loop(lock_service, settings.lock_reclaim_interval_seconds)
        )

        if settings.agent_internal_key == "default-internal-key":
            logger.warning(
                "security_warning",
                message="Using default agent_internal_key — set AGENT_INTERNAL_KEY env var in production",
            )
        yield
        reclaim_task.cancel()
        try:
            await reclaim_task
        except asyncio.CancelledError:
            pass
        await app.state.gateway_service.close()


app = FastAPI(title="AgentSwarm Gateway", version="0.1.0", lifespan=lifespan)

app.add_exception_handler(AgentSwarmError, agentswarm_error_handler)  # type: ignore[arg-type]
app.include_router(router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
