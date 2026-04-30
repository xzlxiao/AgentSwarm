from datetime import UTC, datetime

from pydantic import Field

from app.models.base import MongoModel


class ProjectWorkspaceDoc(MongoModel):
    workspace_id: str = Field(..., description="业务唯一 ID (UUID4)")
    name: str = Field(..., description="工作空间名称")
    volume_name: str = Field(..., description="Docker Volume 名称")
    status: str = Field(default="active", description="枚举: active | archived")
    agent_node_ids: list[str] = Field(default_factory=list, description="关联的 AgentNode ID 列表")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CreateWorkspaceRequest(MongoModel):
    name: str = Field(..., min_length=1, max_length=100)
