from typing import cast
from uuid import uuid4

import httpx
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.core.exceptions import AgentNotFoundError, HermesAPIError
from app.core.logging import get_logger
from app.models.base import model_to_mongo_doc
from app.models.task import ChatCompletionRequest, ChatCompletionResponse
from app.models.token_usage import TokenUsageDoc, TokenUsageInfo

logger = get_logger(__name__)

_COLLECTION = "token_usage"


class GatewayService:
    def __init__(self, db: AsyncDatabase[dict[str, object]], settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._client = httpx.AsyncClient(timeout=60.0)

    async def proxy_chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        await self._find_running_agent(request.agent_node_id)
        model = request.model or self._settings.hermes_model
        payload = self._build_hermes_payload(request, model)

        try:
            response = await self._client.post(
                f"{self._settings.hermes_api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._settings.hermes_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("hermes_api_error", error=str(e))
            raise HermesAPIError() from e

        result, usage_doc = self._parse_hermes_response(response.json(), request, model)
        await self._record_token_usage(usage_doc)
        return result

    async def _find_running_agent(self, agent_node_id: str) -> dict[str, object]:
        agent_raw = await self._db["agent_nodes"].find_one({"node_id": agent_node_id})
        if agent_raw is None or agent_raw.get("status") != "running":
            raise AgentNotFoundError()
        return agent_raw

    def _build_hermes_payload(self, request: ChatCompletionRequest, model: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": model,
            "messages": request.messages,
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.tools is not None:
            payload["tools"] = request.tools
        return payload

    def _parse_hermes_response(
        self,
        data: dict[str, object],
        request: ChatCompletionRequest,
        model: str,
    ) -> tuple[ChatCompletionResponse, TokenUsageDoc]:
        request_id = str(uuid4())

        raw_usage = data.get("usage")
        usage_dict = cast(dict[str, int], raw_usage) if raw_usage else {}
        usage = TokenUsageInfo(
            prompt_tokens=usage_dict.get("prompt_tokens", 0),
            completion_tokens=usage_dict.get("completion_tokens", 0),
            total_tokens=usage_dict.get("total_tokens", 0),
        )

        raw_choices = data.get("choices", [])
        choices = cast(list[dict[str, object]], raw_choices)
        content: str | None = None
        tool_calls: list[dict[str, object]] | None = None
        if choices:
            message = cast(dict[str, object], choices[0].get("message", {}))
            content = cast(str | None, message.get("content"))
            tool_calls = cast(list[dict[str, object]] | None, message.get("tool_calls"))

        api_key_suffix = self._settings.hermes_api_key[-4:] if len(self._settings.hermes_api_key) >= 4 else "****"

        usage_doc = TokenUsageDoc(
            request_id=request_id,
            agent_node_id=request.agent_node_id,
            workspace_id=request.workspace_id,
            model=model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            api_key_suffix=api_key_suffix,
        )

        return ChatCompletionResponse(
            request_id=request_id,
            content=content,
            tool_calls=tool_calls,
            usage=usage,
        ), usage_doc

    async def _record_token_usage(self, doc: TokenUsageDoc) -> None:
        mongo_doc = model_to_mongo_doc(doc)
        await self._db[_COLLECTION].insert_one(mongo_doc)
        logger.info(
            "token_usage_recorded",
            request_id=doc.request_id,
            total_tokens=doc.total_tokens,
        )

    async def close(self) -> None:
        await self._client.aclose()
