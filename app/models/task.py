from typing import Annotated

from pydantic import BaseModel, Field

from app.models.token_usage import TokenUsageInfo


class ChatCompletionRequest(BaseModel):
    agent_node_id: str = Field(..., description="发起请求的 Agent ID")
    workspace_id: str = Field(..., description="所属工作空间 ID")
    messages: list[dict[str, object]] = Field(..., description="对话消息列表")
    model: Annotated[str | None, Field(description="模型名称")] = None
    temperature: Annotated[float, Field(ge=0.0, le=2.0, description="温度")] = 0.7
    max_tokens: Annotated[int | None, Field(ge=1, description="最大 Token 数")] = None
    tools: Annotated[list[dict[str, object]] | None, Field(description="Tool Calling Schema 列表")] = None


class ChatCompletionResponse(BaseModel):
    request_id: str
    content: str | None = None
    tool_calls: list[dict[str, object]] | None = None
    usage: TokenUsageInfo
