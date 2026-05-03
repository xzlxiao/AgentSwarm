from typing import Any, cast
from unittest.mock import MagicMock

import mongomock
import pytest

from app.core.config import Settings
from app.swarm.volume import VolumeManager


class _AsyncMockCursor:
    def __init__(self, docs: list[dict[str, object]]) -> None:
        self._docs = iter(docs)

    def __aiter__(self) -> "_AsyncMockCursor":
        return self

    async def __anext__(self) -> dict[str, object]:
        try:
            return next(self._docs)
        except StopIteration:
            raise StopAsyncIteration


class _AsyncMockCollection:
    def __init__(self, sync_collection: Any) -> None:
        self._sync = sync_collection

    async def find_one(self, filter: Any = None, **kwargs: Any) -> dict[str, object] | None:
        return self._sync.find_one(filter)

    async def insert_one(self, document: dict[str, object]) -> Any:
        return self._sync.insert_one(document)

    def find(self, filter: Any = None) -> _AsyncMockCursor:
        docs: list[dict[str, object]] = list(self._sync.find(filter))
        return _AsyncMockCursor(docs)

    async def find_one_and_update(self, filter: Any, update: Any, **kwargs: Any) -> dict[str, object] | None:
        # mongomock 不支持 $push + $slice，需要手动处理
        push_ops = update.get("$push")
        if push_ops:
            for field, op in push_ops.items():
                if isinstance(op, dict) and "$each" in op and "$slice" in op:
                    doc = self._sync.find_one(filter)
                    if doc is None:
                        return None
                    arr: list[Any] = doc.get(field, [])
                    items: list[Any] = cast(list[Any], op["$each"])
                    arr.extend(items)
                    slice_val: int = cast(int, op["$slice"])
                    if slice_val < 0:
                        arr = arr[slice_val:]
                    elif slice_val > 0:
                        arr = arr[:slice_val]
                    else:
                        arr = []
                    self._sync.update_one(filter, {"$set": {field: arr}})
                    # 移除已手动处理的字段，剩余操作交给 mongomock
                    remaining_push: dict[str, Any] = {k: v for k, v in push_ops.items() if not (isinstance(v, dict) and "$each" in v and "$slice" in v)}
                    if remaining_push:
                        update = dict(update)
                        update["$push"] = remaining_push
                    else:
                        update = {k: v for k, v in update.items() if k != "$push"}
                    break
        return self._sync.find_one_and_update(filter, update, **kwargs)

    async def count_documents(self, filter: Any) -> int:
        return self._sync.count_documents(filter)

    async def create_index(self, *args: Any, **kwargs: Any) -> None:
        pass


class AsyncMockDatabase:
    def __init__(self, sync_db: Any) -> None:
        self._sync = sync_db
        self._collections: dict[str, _AsyncMockCollection] = {}

    def __getitem__(self, name: str) -> _AsyncMockCollection:
        if name not in self._collections:
            self._collections[name] = _AsyncMockCollection(self._sync[name])
        return self._collections[name]


@pytest.fixture
def mock_db() -> AsyncMockDatabase:
    return AsyncMockDatabase(mongomock.MongoClient()["agentswarm_test"])


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        hermes_api_base="https://hermes.test/v1",
        hermes_api_key="sk-test-key-123456",
        hermes_model="test-model",
        mongo_uri="mongodb://localhost:27017",
        mongo_db_name="agentswarm_test",
    )


@pytest.fixture
def mock_volume_manager() -> VolumeManager:
    manager = MagicMock(spec=VolumeManager)
    manager.create_workspace_volume.return_value = "agentswarm-ws-test-ws-id"
    manager.volume_exists.return_value = True
    return manager  # type: ignore[return-value]
