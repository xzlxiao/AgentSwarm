"""RejectService 单元测试：4 个验收场景 + 3 个补充测试。"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.core.exceptions import (
    NoPreviousNodeError,
    NotLockHolderError,
    RejectCountExceededError,
)
from app.models.base import model_to_mongo_doc
from app.models.workspace_lock import WorkspaceLockDoc
from app.services.reject_service import RejectService


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WS_ID = "ws-reject-test"
_REVIEWER = "node-reviewer"
_WRITER = "node-writer"
_CONTAINER_ID = "cid-writer"


# ---------------------------------------------------------------------------
# Async seed helpers
# ---------------------------------------------------------------------------


async def _seed_lock(mock_db: Any, *, history: list[dict[str, Any]] | None = None) -> None:
    lock = WorkspaceLockDoc(workspace_id=_WS_ID)
    doc = model_to_mongo_doc(lock)
    doc["status"] = "locked"
    doc["holder_node_id"] = _REVIEWER
    doc["holder_container_id"] = "cid-reviewer"
    doc["acquired_at"] = datetime.now(UTC)
    if history is not None:
        doc["lock_history"] = history
    else:
        doc["lock_history"] = [
            {
                "node_id": _WRITER,
                "container_id": _CONTAINER_ID,
                "acquired_at": datetime.now(UTC),
                "released_at": datetime.now(UTC),
                "snapshot_id": "snap-writer-001",
            }
        ]
    await mock_db["workspace_locks"].insert_one(doc)


async def _seed_workspace(mock_db: Any) -> None:
    await mock_db["project_workspaces"].insert_one({
        "workspace_id": _WS_ID,
        "name": "test-ws",
        "volume_name": "vol-test",
        "status": "active",
        "agent_node_ids": [_REVIEWER, _WRITER],
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    })


async def _seed_agent(mock_db: Any, status: str = "paused", container_id: str | None = _CONTAINER_ID) -> None:
    await mock_db["agent_nodes"].insert_one({
        "node_id": _WRITER,
        "name": "writer-agent",
        "role": "writer",
        "status": status,
        "workspace_id": _WS_ID,
        "container_id": container_id,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    })


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_snapshot_service() -> MagicMock:
    svc = MagicMock()
    svc.create_snapshot.return_value = "snap-pre-reject-001"
    svc.restore_snapshot.return_value = None
    return svc


@pytest.fixture
def mock_swarm() -> MagicMock:
    mgr = MagicMock()
    mgr.resume_agent.return_value = None
    mgr.spawn_agent.return_value = "cid-new-spawn"
    return mgr


@pytest.fixture
def reject_service(
    mock_db: Any,
    mock_snapshot_service: MagicMock,
    mock_swarm: MagicMock,
    mock_settings: Settings,
) -> RejectService:
    from app.services.agent_service import AgentService
    from app.services.lock_service import LockService

    lock_svc = LockService(mock_db, mock_snapshot_service, mock_settings, mock_swarm)
    agent_svc = AgentService(mock_db, mock_swarm)
    return RejectService(
        mock_db, lock_svc, mock_snapshot_service, agent_svc, mock_swarm, mock_settings,
    )


# ---------------------------------------------------------------------------
# S1: 正常驳回 → 重执行 → 通过
# ---------------------------------------------------------------------------


async def test_s1_normal_reject_and_pass(
    mock_db: Any,
    reject_service: RejectService,
) -> None:
    await _seed_lock(mock_db)
    await _seed_workspace(mock_db)
    await _seed_agent(mock_db, status="paused")

    record = await reject_service.reject(
        workspace_id=_WS_ID,
        reviewer_node_id=_REVIEWER,
        reason="输出格式不正确",
    )

    assert record.target_node_id == _WRITER
    assert record.reject_count == 1
    assert record.status == "pending"
    assert "输出格式不正确" in record.feedback_content

    # 模拟重执行通过
    await reject_service.mark_feedback_passed(_WS_ID, _WRITER)

    fb = await reject_service.get_feedback_for_agent(_WS_ID, _WRITER)
    assert fb is None  # 已标记 passed，不再返回


# ---------------------------------------------------------------------------
# S2: 驳回次数耗尽 → failed
# ---------------------------------------------------------------------------


async def test_s2_reject_count_exceeded(
    mock_db: Any,
    reject_service: RejectService,
) -> None:
    await _seed_lock(mock_db)
    await _seed_workspace(mock_db)
    await _seed_agent(mock_db, status="paused")

    # 预插入 2 条 pending 记录，下次 reject 是第 3 次，max_rejects=2 → 超限
    for i in range(2):
        await mock_db["feedback_records"].insert_one({
            "reject_id": f"existing-{i}",
            "workspace_id": _WS_ID,
            "reviewer_node_id": _REVIEWER,
            "target_node_id": _WRITER,
            "reason": f"reason-{i}",
            "feedback_content": f"feedback-{i}",
            "status": "pending",
            "reject_count": i + 1,
            "created_at": datetime.now(UTC),
        })

    with pytest.raises(RejectCountExceededError):
        await reject_service.reject(
            workspace_id=_WS_ID,
            reviewer_node_id=_REVIEWER,
            reason="还是不对",
            max_rejects=2,
        )


# ---------------------------------------------------------------------------
# S3: 容器已销毁 → spawn
# ---------------------------------------------------------------------------


async def test_s3_container_destroyed_spawn(
    mock_db: Any,
    reject_service: RejectService,
    mock_swarm: MagicMock,
) -> None:
    await _seed_lock(mock_db)
    await _seed_workspace(mock_db)
    await _seed_agent(mock_db, status="destroyed", container_id=None)

    record = await reject_service.reject(
        workspace_id=_WS_ID,
        reviewer_node_id=_REVIEWER,
        reason="需要重做",
    )

    assert record.target_node_id == _WRITER
    mock_swarm.spawn_agent.assert_called_once()

    # 验证 agent_nodes 中状态更新为 pending
    agent_doc = await mock_db["agent_nodes"].find_one({"node_id": _WRITER})
    assert agent_doc["status"] == "pending"
    assert agent_doc["container_id"] == "cid-new-spawn"


# ---------------------------------------------------------------------------
# S4: 容器 paused → resume
# ---------------------------------------------------------------------------


async def test_s4_container_paused_resume(
    mock_db: Any,
    reject_service: RejectService,
    mock_swarm: MagicMock,
) -> None:
    await _seed_lock(mock_db)
    await _seed_workspace(mock_db)
    await _seed_agent(mock_db, status="paused")

    record = await reject_service.reject(
        workspace_id=_WS_ID,
        reviewer_node_id=_REVIEWER,
        reason="格式问题",
    )

    assert record.target_node_id == _WRITER
    mock_swarm.resume_agent.assert_called_once_with(_CONTAINER_ID)
    mock_swarm.spawn_agent.assert_not_called()


# ---------------------------------------------------------------------------
# 补充：非持锁者无法驳回
# ---------------------------------------------------------------------------


async def test_reject_non_holder_rejected(
    mock_db: Any,
    reject_service: RejectService,
) -> None:
    await _seed_lock(mock_db)
    await _seed_workspace(mock_db)
    await _seed_agent(mock_db)

    with pytest.raises(NotLockHolderError):
        await reject_service.reject(
            workspace_id=_WS_ID,
            reviewer_node_id="node-stranger",
            reason="无权操作",
        )


# ---------------------------------------------------------------------------
# 补充：无前驱节点时驳回
# ---------------------------------------------------------------------------


async def test_reject_no_previous_node(
    mock_db: Any,
    reject_service: RejectService,
) -> None:
    await _seed_lock(mock_db, history=[])
    await _seed_workspace(mock_db)
    await _seed_agent(mock_db)

    with pytest.raises(NoPreviousNodeError):
        await reject_service.reject(
            workspace_id=_WS_ID,
            reviewer_node_id=_REVIEWER,
            reason="没有前驱",
        )


# ---------------------------------------------------------------------------
# 补充：get_feedback 返回最新 pending 记录
# ---------------------------------------------------------------------------


async def test_get_feedback_returns_latest(
    mock_db: Any,
    reject_service: RejectService,
) -> None:
    await mock_db["feedback_records"].insert_one({
        "reject_id": "old-fb",
        "workspace_id": _WS_ID,
        "reviewer_node_id": _REVIEWER,
        "target_node_id": _WRITER,
        "reason": "旧反馈",
        "feedback_content": "旧内容",
        "status": "passed",
        "reject_count": 1,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    })
    await mock_db["feedback_records"].insert_one({
        "reject_id": "new-fb",
        "workspace_id": _WS_ID,
        "reviewer_node_id": _REVIEWER,
        "target_node_id": _WRITER,
        "reason": "新反馈",
        "feedback_content": "新内容",
        "status": "pending",
        "reject_count": 2,
        "created_at": datetime(2026, 5, 1, tzinfo=UTC),
    })

    result = await reject_service.get_feedback_for_agent(_WS_ID, _WRITER)
    assert result is not None
    assert result["reject_id"] == "new-fb"
