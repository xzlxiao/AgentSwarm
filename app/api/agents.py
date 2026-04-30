from fastapi import APIRouter, Depends, Request

from app.core.exceptions import AgentNotFoundError, AgentSwarmError
from app.models.agent_node import AgentNodeDoc, CreateAgentNodeRequest, WorkerRegisterRequest
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


def _get_agent_service(request: Request) -> AgentService:
    return AgentService(request.app.state.db)


@router.post("", status_code=201)
async def create_agent(
    body: CreateAgentNodeRequest,
    service: AgentService = Depends(_get_agent_service),
) -> AgentNodeDoc:
    return await service.create(body)


@router.get("/{node_id}")
async def get_agent(
    node_id: str,
    service: AgentService = Depends(_get_agent_service),
) -> AgentNodeDoc:
    result = await service.get_by_node_id(node_id)
    if result is None:
        raise AgentNotFoundError()
    return result


@router.get("")
async def list_agents(
    workspace_id: str | None = None,
    service: AgentService = Depends(_get_agent_service),
) -> list[AgentNodeDoc]:
    if workspace_id is not None:
        return await service.list_by_workspace(workspace_id)
    return []


@router.patch("/{node_id}")
async def update_agent_status(
    node_id: str,
    body: dict[str, object],
    service: AgentService = Depends(_get_agent_service),
) -> AgentNodeDoc:
    status = body.get("status")
    if not isinstance(status, str):
        raise AgentSwarmError()
    return await service.update_status(node_id, status)


@router.delete("/{node_id}")
async def delete_agent(
    node_id: str,
    service: AgentService = Depends(_get_agent_service),
) -> AgentNodeDoc:
    return await service.destroy(node_id)


@router.post("/{node_id}/register")
async def register_worker(
    node_id: str,
    body: WorkerRegisterRequest,
    service: AgentService = Depends(_get_agent_service),
) -> AgentNodeDoc:
    return await service.register_worker(node_id, body)
