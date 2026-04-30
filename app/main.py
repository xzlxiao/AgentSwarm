from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import get_database, mongo_lifespan
from app.core.exceptions import AgentSwarmError, agentswarm_error_handler
from app.core.logging import configure_logging
from app.api.router import router
from app.services.gateway_service import GatewayService
from app.swarm.manager import SwarmManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    async with mongo_lifespan(settings) as client:
        db = get_database(client, settings)
        app.state.mongo_client = client
        app.state.db = db
        app.state.gateway_service = GatewayService(db, settings)
        app.state.swarm_manager = SwarmManager(settings)
        if settings.agent_internal_key == "default-internal-key":
            from app.core.logging import get_logger
            get_logger(__name__).warning(
                "security_warning",
                message="Using default agent_internal_key — set AGENT_INTERNAL_KEY env var in production",
            )
        yield
        await app.state.gateway_service.close()


app = FastAPI(title="AgentSwarm Gateway", version="0.1.0", lifespan=lifespan)

app.add_exception_handler(AgentSwarmError, agentswarm_error_handler)  # type: ignore[arg-type]
app.include_router(router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
