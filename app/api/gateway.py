from fastapi import APIRouter, Depends, Request

from app.models.task import ChatCompletionRequest, ChatCompletionResponse
from app.services.gateway_service import GatewayService

router = APIRouter(prefix="/api/v1/gateway", tags=["gateway"])


def _get_gateway_service(request: Request) -> GatewayService:
    return request.app.state.gateway_service


@router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    service: GatewayService = Depends(_get_gateway_service),
) -> ChatCompletionResponse:
    return await service.proxy_chat_completion(body)
