from datetime import UTC, datetime
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.core.exceptions import WorkspaceNotFoundError
from app.core.logging import get_logger
from app.models.base import mongo_doc_to_model, model_to_mongo_doc
from app.models.workspace import CreateWorkspaceRequest, ProjectWorkspaceDoc
from app.swarm.volume import VolumeManager

logger = get_logger(__name__)

_COLLECTION = "project_workspaces"


class WorkspaceService:
    def __init__(self, db: AsyncDatabase[dict[str, object]], volume_manager: VolumeManager) -> None:
        self._db = db
        self._volume_manager = volume_manager

    async def create(self, request: CreateWorkspaceRequest) -> ProjectWorkspaceDoc:
        workspace_id = str(uuid4())
        volume_name = self._volume_manager.create_workspace_volume(workspace_id)
        doc = ProjectWorkspaceDoc(
            workspace_id=workspace_id,
            name=request.name,
            volume_name=volume_name,
        )
        mongo_doc = model_to_mongo_doc(doc)
        await self._db[_COLLECTION].insert_one(mongo_doc)
        logger.info("workspace_created", workspace_id=workspace_id, name=request.name)
        return doc

    async def get_by_workspace_id(self, workspace_id: str) -> ProjectWorkspaceDoc | None:
        raw = await self._db[_COLLECTION].find_one({"workspace_id": workspace_id})
        if raw is None:
            return None
        return mongo_doc_to_model(raw, ProjectWorkspaceDoc)  # type: ignore[return-value]

    async def list_all(self) -> list[ProjectWorkspaceDoc]:
        results: list[ProjectWorkspaceDoc] = []
        async for raw in self._db[_COLLECTION].find({"status": "active"}):
            results.append(mongo_doc_to_model(raw, ProjectWorkspaceDoc))  # type: ignore[arg-type]
        return results

    async def archive(self, workspace_id: str) -> ProjectWorkspaceDoc:
        result = await self._db[_COLLECTION].find_one_and_update(
            {"workspace_id": workspace_id},
            {"$set": {"status": "archived", "updated_at": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            raise WorkspaceNotFoundError()
        logger.info("workspace_archived", workspace_id=workspace_id)
        return mongo_doc_to_model(result, ProjectWorkspaceDoc)  # type: ignore[return-value]
