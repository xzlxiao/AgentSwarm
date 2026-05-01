from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.models.base import MongoModel


class WaitQueueEntry(BaseModel):
    """等待队列中的条目。"""

    node_id: str = Field(..., description="等待中的 Agent node_id")
    container_id: str = Field(..., description="Agent 容器 ID")
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkspaceLockDoc(MongoModel):
    """Workspace 独占锁文档，每个 workspace 一条。"""

    workspace_id: str = Field(..., description="关联的 Workspace ID")
    status: str = Field(default="free", description="枚举: free | locked")
    holder_node_id: str | None = Field(default=None, description="当前持锁 Agent node_id")
    holder_container_id: str | None = Field(default=None, description="持锁 Agent 容器 ID")
    acquired_at: datetime | None = Field(default=None, description="锁获取时间")
    last_heartbeat_at: datetime | None = Field(default=None, description="最近心跳时间")
    timeout_seconds: int = Field(default=600, description="锁超时阈值（秒）")
    wait_queue: list[WaitQueueEntry] = Field(default_factory=list, description="等待队列")
    snapshot_id: str | None = Field(default=None, description="最近一次快照 ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AcquireLockRequest(BaseModel):
    """获取锁请求。"""

    workspace_id: str = Field(..., description="Workspace ID")
    node_id: str = Field(..., description="请求锁的 Agent node_id")
    container_id: str = Field(..., description="Agent 容器 ID")
    timeout_seconds: int = Field(default=600, description="锁超时阈值（秒）")


class ReleaseLockRequest(BaseModel):
    """释放锁请求。"""

    workspace_id: str = Field(..., description="Workspace ID")
    node_id: str = Field(..., description="释放锁的 Agent node_id")


class HeartbeatRequest(BaseModel):
    """锁心跳请求。"""

    workspace_id: str = Field(..., description="Workspace ID")
    node_id: str = Field(..., description="发送心跳的 Agent node_id")
