from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentSwarmError(Exception):
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.detail
        super().__init__(self.detail)


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


class InvalidStatusTransition(AgentSwarmError):
    status_code = 400
    detail = "Invalid status transition"


class LockNotAvailableError(AgentSwarmError):
    status_code = 409
    detail = "Lock is not available"


class NotLockHolderError(AgentSwarmError):
    status_code = 403
    detail = "Not the lock holder"


class LockNotFoundError(AgentSwarmError):
    status_code = 404
    detail = "Lock not found"


async def agentswarm_error_handler(request: Request, exc: AgentSwarmError) -> JSONResponse:
    logger.error("request_error", error=exc.detail, status_code=exc.status_code, path=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )
