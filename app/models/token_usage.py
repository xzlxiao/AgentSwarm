from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.models.base import MongoModel


class TokenUsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class TokenUsageDoc(MongoModel):
    request_id: str = Field(..., description="请求唯一 ID (UUID4)")
    agent_node_id: str = Field(..., description="发起请求的 Agent ID")
    workspace_id: str = Field(..., description="所属工作空间")
    model: str = Field(..., description="使用的模型名称")
    prompt_tokens: int = Field(..., description="输入 Token 数")
    completion_tokens: int = Field(..., description="输出 Token 数")
    total_tokens: int = Field(..., description="总 Token 数")
    api_key_suffix: str = Field(..., description="API Key 后四位")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
