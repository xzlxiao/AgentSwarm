from datetime import UTC, datetime

from pydantic import Field

from app.models.base import MongoModel


class AgentNodeDoc(MongoModel):
    node_id: str = Field(..., description="业务唯一 ID (UUID4)")
    name: str = Field(..., description="Agent 显示名称")
    role: str = Field(..., description="Agent 角色")
    status: str = "pending"
    workspace_id: str = Field(..., description="关联的 ProjectWorkspace ID")
    container_id: str | None = None
    container_ip: str | None = None
    container_port: int | None = None
    volume_mount_path: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CreateAgentNodeRequest(MongoModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., pattern=r"^(coordinator|writer|reviewer|custom)$")
    workspace_id: str


class WorkerRegisterRequest(MongoModel):
    container_id: str = Field(..., description="Docker 容器 ID")
    container_ip: str = Field(..., description="Worker 容器 IP")
    container_port: int = 3000
