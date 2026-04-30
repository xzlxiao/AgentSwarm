from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentSwarmError(Exception):
    status_code: int = 500
    detail: str = "Internal server error"


class AgentNotFoundError(AgentSwarmError):
    status_code = 404
    detail = "Agent node not found"


class WorkspaceNotFoundError(AgentSwarmError):
    status_code = 404
    detail = "Workspace not found"


class HermesAPIError(AgentSwarmError):
    status_code = 502
    detail = "Hermes API request failed"


class ContainerError(AgentSwarmError):
    status_code = 500
    detail = "Container operation failed"


class WorkerRegistrationError(AgentSwarmError):
    status_code = 503
    detail = "Worker registration failed"


async def agentswarm_error_handler(request: Request, exc: AgentSwarmError) -> JSONResponse:
    logger.error("request_error", error=exc.detail, status_code=exc.status_code, path=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )
