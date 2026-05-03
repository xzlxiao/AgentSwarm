from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.services.reject_service import RejectService

router = APIRouter(prefix="/api/v1/internal", tags=["reject"])


def _get_settings_dep() -> Settings:
    return get_settings()


def _verify_agent_key(
    x_agent_key: str = Header(..., alias="X-Agent-Key"),
    settings: Settings = Depends(_get_settings_dep),
) -> None:
    import hmac

    if not hmac.compare_digest(x_agent_key.encode(), settings.agent_internal_key.encode()):
        raise HTTPException(status_code=401, detail="Invalid agent key")


def _get_reject_service(request: Request) -> RejectService:
    try:
        service: RejectService = request.app.state.reject_service
    except AttributeError:
        raise HTTPException(status_code=503, detail="Reject service not initialized")
    return service


class RejectBody(BaseModel):
    workspace_id: str = Field(..., description="Workspace ID")
    reviewer_node_id: str = Field(..., description="Reviewer agent node_id")
    reason: str = Field(..., description="Rejection reason")
    max_rejects: int = Field(default=3, description="Max reject count")


class GetFeedbackBody(BaseModel):
    workspace_id: str = Field(..., description="Workspace ID")
    node_id: str = Field(..., description="Agent node_id")


@router.post("/reject")
async def reject(
    body: RejectBody,
    request: Request,
    _auth: None = Depends(_verify_agent_key),
) -> dict[str, object]:
    service = _get_reject_service(request)
    record = await service.reject(
        workspace_id=body.workspace_id,
        reviewer_node_id=body.reviewer_node_id,
        reason=body.reason,
        max_rejects=body.max_rejects,
    )
    return {
        "reject_id": record.reject_id,
        "target_node_id": record.target_node_id,
        "reject_count": record.reject_count,
        "status": record.status,
    }


@router.post("/feedback")
async def get_feedback(
    body: GetFeedbackBody,
    request: Request,
    _auth: None = Depends(_verify_agent_key),
) -> dict[str, object | None]:
    service = _get_reject_service(request)
    result = await service.get_feedback_for_agent(
        workspace_id=body.workspace_id,
        node_id=body.node_id,
    )
    if result is None:
        return {"feedback": None}
    return {"feedback": result}
