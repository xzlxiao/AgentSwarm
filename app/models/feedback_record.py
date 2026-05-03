from datetime import UTC, datetime

from pydantic import Field

from app.models.base import MongoModel


class FeedbackRecordDoc(MongoModel):
    """驳回反馈记录，存储审查 Agent 的驳回意见和重执行上下文。"""

    reject_id: str = Field(..., description="驳回操作唯一 ID")
    workspace_id: str = Field(..., description="关联 Workspace ID")
    reviewer_node_id: str = Field(..., description="发起驳回的审查 Agent node_id")
    target_node_id: str = Field(..., description="被驳回的目标 Agent node_id")
    reason: str = Field(..., description="驳回原因")
    original_instructions: str | None = Field(default=None, description="目标 Agent 原始任务指令")
    feedback_content: str = Field(..., description="组装好的反馈内容（注入重执行上下文）")
    snapshot_id: str | None = Field(default=None, description="回滚到的快照 ID")
    pre_reject_snapshot_id: str | None = Field(default=None, description="驳回前创建的安全快照 ID")
    reject_count: int = Field(default=1, description="同一目标累计被驳回次数")
    status: str = Field(default="pending", description="枚举: pending | re_executing | passed | failed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
