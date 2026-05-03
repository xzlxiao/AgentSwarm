import asyncio
from datetime import UTC, datetime
from typing import cast

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.core.exceptions import LockNotFoundError, NotLockHolderError
from app.core.logging import get_logger
from app.models.base import model_to_mongo_doc
from app.models.workspace_lock import LockHistoryEntry, WaitQueueEntry, WorkspaceLockDoc
from app.services.snapshot_service import SnapshotService
from app.swarm.manager import SwarmManager

logger = get_logger(__name__)

_COLLECTION = "workspace_locks"
_MAX_QUEUE_DEPTH = 10


class LockService:
    def __init__(
        self,
        db: AsyncDatabase[dict[str, object]],
        snapshot_service: SnapshotService,
        settings: Settings,
        swarm_manager: SwarmManager | None = None,
    ) -> None:
        self._db = db
        self._snapshot_service = snapshot_service
        self._settings = settings
        self._swarm_manager = swarm_manager

    async def acquire_lock(
        self,
        workspace_id: str,
        node_id: str,
        container_id: str,
        timeout_seconds: int | None = None,
    ) -> dict[str, object]:
        timeout = timeout_seconds or self._settings.default_lock_timeout_seconds

        # 尝试原子获取：status == "free" → "locked"
        result = await self._db[_COLLECTION].find_one_and_update(
            {"workspace_id": workspace_id, "status": "free"},
            {
                "$set": {
                    "status": "locked",
                    "holder_node_id": node_id,
                    "holder_container_id": container_id,
                    "acquired_at": datetime.now(UTC),
                    "last_heartbeat_at": datetime.now(UTC),
                    "timeout_seconds": timeout,
                    "updated_at": datetime.now(UTC),
                },
            },
            return_document=ReturnDocument.AFTER,
        )

        if result is not None:
            return result

        # 文档不存在 → upsert 一条 free 文档后重试
        existing = await self._db[_COLLECTION].find_one({"workspace_id": workspace_id})
        if existing is None:
            doc = WorkspaceLockDoc(workspace_id=workspace_id)
            await self._db[_COLLECTION].insert_one(model_to_mongo_doc(doc))
            # 重试 acquire
            retry = await self._db[_COLLECTION].find_one_and_update(
                {"workspace_id": workspace_id, "status": "free"},
                {
                    "$set": {
                        "status": "locked",
                        "holder_node_id": node_id,
                        "holder_container_id": container_id,
                        "acquired_at": datetime.now(UTC),
                        "last_heartbeat_at": datetime.now(UTC),
                        "timeout_seconds": timeout,
                        "updated_at": datetime.now(UTC),
                    },
                },
                return_document=ReturnDocument.AFTER,
            )
            if retry is not None:
                return retry

        # 锁被占用 → 加入等待队列（防重复 + 深度限制）
        current = await self._db[_COLLECTION].find_one({"workspace_id": workspace_id})
        if current is None:
            raise LockNotFoundError(f"No lock document for workspace {workspace_id}")

        # 已是持锁者 → 直接返回
        if cast(str | None, current.get("holder_node_id")) == node_id:
            return current

        queue = cast(list[dict[str, object]], current.get("wait_queue", []))
        if len(queue) >= _MAX_QUEUE_DEPTH:
            from app.core.exceptions import LockNotAvailableError
            raise LockNotAvailableError("Wait queue is full")

        # 防止重复入队
        for entry in queue:
            entry_node_id = cast(str, entry.get("node_id"))
            if entry_node_id == node_id:
                return current

        new_entry = WaitQueueEntry(node_id=node_id, container_id=container_id)

        updated = await self._db[_COLLECTION].find_one_and_update(
            {"workspace_id": workspace_id},
            {
                "$push": {"wait_queue": new_entry.model_dump()},
                "$set": {"updated_at": datetime.now(UTC)},
            },
            return_document=ReturnDocument.AFTER,
        )

        if updated is None:
            raise LockNotFoundError(f"Lock document lost for workspace {workspace_id}")

        return updated

    async def release_lock(self, workspace_id: str, node_id: str) -> dict[str, object]:
        current = await self._db[_COLLECTION].find_one({"workspace_id": workspace_id})
        if current is None:
            raise LockNotFoundError(f"No lock document for workspace {workspace_id}")

        holder = cast(str | None, current.get("holder_node_id"))
        if holder != node_id:
            raise NotLockHolderError(f"Node {node_id} is not the lock holder")

        # 查询 workspace 获取 volume_name
        ws_doc = await self._db["project_workspaces"].find_one({"workspace_id": workspace_id})
        volume_name: str | None = None
        if ws_doc is not None:
            volume_name = cast(str | None, ws_doc.get("volume_name"))

        # Best-effort 快照
        snapshot_id: str | None = None
        if volume_name is not None:
            try:
                snapshot_id = await asyncio.to_thread(
                    self._snapshot_service.create_snapshot,
                    workspace_id,
                    volume_name,
                    f"lock-release-{node_id[:8]}",
                )
                logger.info("lock_snapshot_created", workspace_id=workspace_id, snapshot_id=snapshot_id)
            except Exception:
                logger.error("snapshot_failed", workspace_id=workspace_id, node_id=node_id, exc_info=True)
        else:
            logger.warning("workspace_not_found_for_snapshot", workspace_id=workspace_id)

        # 从 wait_queue 取下一个或设为 free
        queue = cast(list[dict[str, object]], current.get("wait_queue", []))
        now = datetime.now(UTC)

        # 构建锁历史条目
        history_entry = LockHistoryEntry(
            node_id=node_id,
            container_id=cast(str | None, current.get("holder_container_id")) or "",
            acquired_at=cast(datetime, current.get("acquired_at")),
            released_at=now,
            snapshot_id=snapshot_id,
        )

        if queue:
            next_entry = queue[0]
            next_node_id = cast(str, next_entry.get("node_id"))
            next_container_id = cast(str, next_entry.get("container_id"))

            updated = await self._db[_COLLECTION].find_one_and_update(
                {"workspace_id": workspace_id},
                {
                    "$set": {
                        "holder_node_id": next_node_id,
                        "holder_container_id": next_container_id,
                        "acquired_at": now,
                        "last_heartbeat_at": now,
                        "snapshot_id": snapshot_id,
                        "updated_at": now,
                    },
                    "$pop": {"wait_queue": -1},
                    "$push": {"lock_history": {"$each": [history_entry.model_dump()], "$slice": -50}},
                },
                return_document=ReturnDocument.AFTER,
            )
        else:
            updated = await self._db[_COLLECTION].find_one_and_update(
                {"workspace_id": workspace_id},
                {
                    "$set": {
                        "status": "free",
                        "holder_node_id": None,
                        "holder_container_id": None,
                        "acquired_at": None,
                        "last_heartbeat_at": None,
                        "snapshot_id": snapshot_id,
                        "updated_at": now,
                    },
                    "$push": {"lock_history": {"$each": [history_entry.model_dump()], "$slice": -50}},
                },
                return_document=ReturnDocument.AFTER,
            )

        if updated is None:
            raise LockNotFoundError(f"Lock document lost during release for workspace {workspace_id}")

        logger.info("lock_released", workspace_id=workspace_id, node_id=node_id, snapshot_id=snapshot_id)
        return updated

    async def heartbeat(self, workspace_id: str, node_id: str) -> None:
        result = await self._db[_COLLECTION].find_one_and_update(
            {"workspace_id": workspace_id, "holder_node_id": node_id, "status": "locked"},
            {"$set": {"last_heartbeat_at": datetime.now(UTC), "updated_at": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            raise NotLockHolderError(f"Node {node_id} is not the lock holder for workspace {workspace_id}")

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    async def reclaim_expired_locks(self) -> int:
        now = datetime.now(UTC)
        reclaimed = 0

        async for doc in self._db[_COLLECTION].find({"status": "locked"}):
            # 操作守卫：reject 等操作期间禁止 reclaim
            if doc.get("locked_by_operation") is not None:
                continue

            timeout = cast(int, doc.get("timeout_seconds", self._settings.default_lock_timeout_seconds))
            last_hb = cast(datetime | None, doc.get("last_heartbeat_at"))
            if last_hb is None:
                last_hb = cast(datetime | None, doc.get("acquired_at"))
            if last_hb is None:
                continue

            elapsed = (now - self._ensure_utc(last_hb)).total_seconds()
            if elapsed < timeout:
                continue

            # 超时 → 检查容器是否存活
            container_id = cast(str | None, doc.get("holder_container_id"))
            container_alive = False
            if container_id is not None and self._swarm_manager is not None:
                try:
                    client = self._swarm_manager.client
                    container = client.containers.get(container_id)
                    container_alive = container.status == "running"
                except Exception:
                    container_alive = False

            if container_alive:
                continue

            workspace_id = cast(str, doc.get("workspace_id"))
            node_id = cast(str | None, doc.get("holder_node_id"))

            # Best-effort 快照
            ws_doc = await self._db["project_workspaces"].find_one({"workspace_id": workspace_id})
            volume_name = cast(str | None, ws_doc.get("volume_name")) if ws_doc else None
            if volume_name is not None and node_id is not None:
                try:
                    await asyncio.to_thread(
                        self._snapshot_service.create_snapshot,
                        workspace_id,
                        volume_name,
                        f"reclaim-{node_id[:8]}",
                    )
                except Exception:
                    logger.error("reclaim_snapshot_failed", workspace_id=workspace_id, exc_info=True)

            # 回收锁 + 清理过期队列
            queue = cast(list[dict[str, object]], doc.get("wait_queue", []))
            fresh_queue: list[dict[str, object]] = []
            for entry in queue:
                entry_time = cast(datetime, entry.get("enqueued_at"))
                if (now - entry_time).total_seconds() < timeout * 2:
                    fresh_queue.append(entry)

            now_dt = datetime.now(UTC)
            if fresh_queue:
                next_entry = fresh_queue[0]
                next_node_id = cast(str, next_entry.get("node_id"))
                next_container_id = cast(str, next_entry.get("container_id"))

                await self._db[_COLLECTION].find_one_and_update(
                    {"workspace_id": workspace_id},
                    {
                        "$set": {
                            "holder_node_id": next_node_id,
                            "holder_container_id": next_container_id,
                            "acquired_at": now_dt,
                            "last_heartbeat_at": now_dt,
                            "wait_queue": fresh_queue[1:],
                            "updated_at": now_dt,
                        },
                        "$pop": {"wait_queue": -1},
                    },
                )
            else:
                await self._db[_COLLECTION].find_one_and_update(
                    {"workspace_id": workspace_id},
                    {
                        "$set": {
                            "status": "free",
                            "holder_node_id": None,
                            "holder_container_id": None,
                            "acquired_at": None,
                            "last_heartbeat_at": None,
                            "wait_queue": [],
                            "updated_at": now_dt,
                        },
                    },
                )

            reclaimed += 1
            logger.info("lock_reclaimed", workspace_id=workspace_id, expired_node=node_id)

        return reclaimed

    async def get_previous_holder(self, workspace_id: str, current_node_id: str) -> dict[str, object] | None:
        """通过 lock_history 动态追溯上一个持锁 Agent（排除自身）。"""
        doc = await self._db[_COLLECTION].find_one({"workspace_id": workspace_id})
        if doc is None:
            return None
        history = cast(list[dict[str, object]], doc.get("lock_history", []))
        for entry in reversed(history):
            entry_node = cast(str, entry.get("node_id"))
            if entry_node != current_node_id:
                return entry
        return None

    async def get_lock_status(self, workspace_id: str) -> dict[str, object]:
        raw = await self._db[_COLLECTION].find_one({"workspace_id": workspace_id})
        if raw is None:
            raise LockNotFoundError(f"No lock document for workspace {workspace_id}")
        return raw
