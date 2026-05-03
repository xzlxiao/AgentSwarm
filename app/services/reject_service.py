import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.core.exceptions import (
    NoPreviousNodeError,
    NotLockHolderError,
    RejectCountExceededError,
    RejectTargetNotFoundError,
)
from app.core.logging import get_logger
from app.models.agent_node import AgentNodeDoc
from app.models.base import model_to_mongo_doc, mongo_doc_to_model
from app.models.feedback_record import FeedbackRecordDoc
from app.models.workspace import ProjectWorkspaceDoc
from app.services.agent_service import AgentService
from app.services.lock_service import LockService
from app.services.snapshot_service import SnapshotService
from app.swarm.manager import SwarmManager

logger = get_logger(__name__)

_COLLECTION = "feedback_records"


class RejectService:
    def __init__(
        self,
        db: AsyncDatabase[dict[str, object]],
        lock_service: LockService,
        snapshot_service: SnapshotService,
        agent_service: AgentService,
        swarm_manager: SwarmManager,
        settings: Settings,
    ) -> None:
        self._db = db
        self._lock_service = lock_service
        self._snapshot_service = snapshot_service
        self._agent_service = agent_service
        self._swarm_manager = swarm_manager
        self._settings = settings

    async def reject(
        self,
        workspace_id: str,
        reviewer_node_id: str,
        reason: str,
        max_rejects: int = 3,
    ) -> FeedbackRecordDoc:
        """执行驳回：回滚快照 + 注入反馈 + 自适应容器管理。"""
        # 1. 验证 reviewer 持有锁
        lock_status = await self._lock_service.get_lock_status(workspace_id)
        holder = cast(str | None, lock_status.get("holder_node_id"))
        if holder != reviewer_node_id:
            raise NotLockHolderError(f"Node {reviewer_node_id} does not hold the lock")

        # 2. 设置操作守卫
        await self._db["workspace_locks"].find_one_and_update(
            {"workspace_id": workspace_id},
            {"$set": {"locked_by_operation": "reject"}},
        )

        feedback_record: FeedbackRecordDoc | None = None
        try:
            # 3. 动态追溯前驱 Agent
            prev_holder = await self._lock_service.get_previous_holder(workspace_id, reviewer_node_id)
            if prev_holder is None:
                raise NoPreviousNodeError("No previous node in lock history")

            target_node_id = cast(str, prev_holder.get("node_id"))
            prev_snapshot_id = cast(str | None, prev_holder.get("snapshot_id"))

            # 4. 查找目标 Agent
            target_agent = await self._agent_service.get_by_node_id(target_node_id)
            if target_agent is None:
                raise RejectTargetNotFoundError(f"Target agent {target_node_id} not found")

            # 5. 检查驳回计数
            reject_count = await self._db[_COLLECTION].count_documents({
                "workspace_id": workspace_id,
                "target_node_id": target_node_id,
                "status": {"$in": ["pending", "re_executing", "failed"]},
            }) + 1

            if reject_count > max_rejects:
                # 标记所有 pending 记录为 failed
                await self._db[_COLLECTION].update_many(
                    {"workspace_id": workspace_id, "target_node_id": target_node_id, "status": "pending"},
                    {"$set": {"status": "failed"}},
                )
                raise RejectCountExceededError(
                    f"Reject count ({reject_count}) exceeds max ({max_rejects})"
                )

            # 6. 获取 workspace volume_name
            ws_doc = await self._db["project_workspaces"].find_one({"workspace_id": workspace_id})
            if ws_doc is None:
                raise RejectTargetNotFoundError(f"Workspace {workspace_id} not found")
            volume_name = cast(str, ws_doc.get("volume_name"))

            # 7. M1: 创建驳回前安全快照
            pre_reject_snapshot_id: str | None = None
            try:
                pre_reject_snapshot_id = await asyncio.to_thread(
                    self._snapshot_service.create_snapshot,
                    workspace_id,
                    volume_name,
                    f"pre-reject-{target_node_id[:8]}",
                )
            except Exception:
                logger.error("pre_reject_snapshot_failed", workspace_id=workspace_id, exc_info=True)

            # 8. 回滚快照
            if prev_snapshot_id is not None:
                await asyncio.to_thread(
                    self._snapshot_service.restore_snapshot,
                    workspace_id,
                    prev_snapshot_id,
                    volume_name,
                )

            # 9. 创建反馈记录
            reject_id = str(uuid4())
            feedback_content = self._build_feedback_content(reason, reject_count, max_rejects)
            feedback_record = FeedbackRecordDoc(
                reject_id=reject_id,
                workspace_id=workspace_id,
                reviewer_node_id=reviewer_node_id,
                target_node_id=target_node_id,
                reason=reason,
                feedback_content=feedback_content,
                snapshot_id=prev_snapshot_id,
                pre_reject_snapshot_id=pre_reject_snapshot_id,
                reject_count=reject_count,
                status="pending",
            )
            await self._db[_COLLECTION].insert_one(model_to_mongo_doc(feedback_record))

            # 10. 自适应容器管理
            workspace = cast(ProjectWorkspaceDoc, mongo_doc_to_model(ws_doc, ProjectWorkspaceDoc))
            await self._adapt_container(target_agent, workspace)

            logger.info(
                "reject_completed",
                workspace_id=workspace_id,
                target_node_id=target_node_id,
                reject_count=reject_count,
            )
            return feedback_record

        except Exception:
            # 部分失败：设置反馈记录状态为 failed
            if feedback_record is not None:
                await self._db[_COLLECTION].update_one(
                    {"reject_id": feedback_record.reject_id},
                    {"$set": {"status": "failed"}},
                )
            raise

        finally:
            # 始终清除操作守卫
            await self._db["workspace_locks"].find_one_and_update(
                {"workspace_id": workspace_id},
                {"$set": {"locked_by_operation": None}},
            )

    async def get_feedback_for_agent(self, workspace_id: str, node_id: str) -> dict[str, object] | None:
        """获取 Agent 待处理的反馈记录。"""
        doc = await self._db[_COLLECTION].find_one(
            {"workspace_id": workspace_id, "target_node_id": node_id, "status": "pending"},
            sort=[("created_at", -1)],
        )
        return doc

    async def mark_feedback_passed(self, workspace_id: str, target_node_id: str) -> None:
        """标记反馈为已通过。"""
        await self._db[_COLLECTION].update_one(
            {"workspace_id": workspace_id, "target_node_id": target_node_id, "status": "pending"},
            {"$set": {"status": "passed"}},
        )

    def _build_feedback_content(self, reason: str, reject_count: int, max_rejects: int) -> str:
        """组装反馈内容。"""
        return (
            f"[CRITICAL SYSTEM FEEDBACK] Your previous output was rejected (attempt {reject_count}/{max_rejects}).\n"
            f"Reason: {reason}\n"
            "Please revise your output addressing the issues above."
        )

    async def _adapt_container(self, target_agent: AgentNodeDoc, workspace: ProjectWorkspaceDoc) -> None:
        """自适应容器管理：paused → resume, destroyed → spawn。"""
        agent_status = target_agent.status

        if agent_status == "paused" and target_agent.container_id is not None:
            # S4: resume paused container — update_status 内部会调用 swarm_manager.resume_agent
            await self._agent_service.update_status(target_agent.node_id, "running")
            logger.info("reject_resumed_agent", node_id=target_agent.node_id)

        elif agent_status == "destroyed" or target_agent.container_id is None:
            # S3: spawn new container
            new_container_id = self._swarm_manager.spawn_agent(target_agent, workspace)
            # 更新容器信息，状态设为 pending（等待 worker self-register）
            await self._db["agent_nodes"].find_one_and_update(
                {"node_id": target_agent.node_id},
                {"$set": {
                    "container_id": new_container_id,
                    "status": "pending",
                    "updated_at": datetime.now(UTC),
                }},
            )
            logger.info("reject_spawned_agent", node_id=target_agent.node_id, container_id=new_container_id)

        else:
            logger.info("reject_agent_alive", node_id=target_agent.node_id, status=agent_status)
