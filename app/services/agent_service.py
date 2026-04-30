from datetime import UTC, datetime
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.core.exceptions import AgentNotFoundError
from app.core.logging import get_logger
from app.models.agent_node import AgentNodeDoc, CreateAgentNodeRequest, WorkerRegisterRequest
from app.models.base import mongo_doc_to_model, model_to_mongo_doc

logger = get_logger(__name__)

_COLLECTION = "agent_nodes"


class AgentService:
    def __init__(self, db: AsyncDatabase[dict[str, object]]) -> None:
        self._db = db

    async def create(self, request: CreateAgentNodeRequest) -> AgentNodeDoc:
        doc = AgentNodeDoc(
            node_id=str(uuid4()),
            name=request.name,
            role=request.role,
            workspace_id=request.workspace_id,
        )
        mongo_doc = model_to_mongo_doc(doc)
        await self._db[_COLLECTION].insert_one(mongo_doc)
        logger.info("agent_created", node_id=doc.node_id, name=doc.name, role=doc.role)
        return doc

    async def get_by_node_id(self, node_id: str) -> AgentNodeDoc | None:
        raw = await self._db[_COLLECTION].find_one({"node_id": node_id})
        if raw is None:
            return None
        return mongo_doc_to_model(raw, AgentNodeDoc)  # type: ignore[return-value]

    async def list_by_workspace(self, workspace_id: str) -> list[AgentNodeDoc]:
        results: list[AgentNodeDoc] = []
        async for raw in self._db[_COLLECTION].find({"workspace_id": workspace_id}):
            results.append(mongo_doc_to_model(raw, AgentNodeDoc))  # type: ignore[arg-type]
        return results

    async def update_status(self, node_id: str, status: str) -> AgentNodeDoc:
        result = await self._db[_COLLECTION].find_one_and_update(
            {"node_id": node_id},
            {"$set": {"status": status, "updated_at": datetime.now(UTC)}},
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            raise AgentNotFoundError()
        return mongo_doc_to_model(result, AgentNodeDoc)  # type: ignore[return-value]

    async def destroy(self, node_id: str) -> AgentNodeDoc:
        return await self.update_status(node_id, "destroyed")

    async def register_worker(self, node_id: str, request: WorkerRegisterRequest) -> AgentNodeDoc:
        result = await self._db[_COLLECTION].find_one_and_update(
            {"node_id": node_id, "status": "pending"},
            {
                "$set": {
                    "container_id": request.container_id,
                    "container_ip": request.container_ip,
                    "container_port": request.container_port,
                    "status": "running",
                    "updated_at": datetime.now(UTC),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            raise AgentNotFoundError()
        logger.info("worker_registered", node_id=node_id, container_ip=request.container_ip)
        return mongo_doc_to_model(result, AgentNodeDoc)  # type: ignore[return-value]
