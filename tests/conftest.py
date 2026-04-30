from typing import Any
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

    async def find_one(self, filter: Any = None) -> dict[str, object] | None:
        return self._sync.find_one(filter)

    async def insert_one(self, document: dict[str, object]) -> Any:
        return self._sync.insert_one(document)

    def find(self, filter: Any = None) -> _AsyncMockCursor:
        docs: list[dict[str, object]] = list(self._sync.find(filter))
        return _AsyncMockCursor(docs)

    async def find_one_and_update(self, filter: Any, update: Any, **kwargs: Any) -> dict[str, object] | None:
        return self._sync.find_one_and_update(filter, update, **kwargs)

    async def count_documents(self, filter: Any) -> int:
        return self._sync.count_documents(filter)


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
