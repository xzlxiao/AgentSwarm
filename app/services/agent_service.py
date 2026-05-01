from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.core.exceptions import AgentNotFoundError, InvalidStatusTransition
from app.core.logging import get_logger
from app.models.agent_node import AgentNodeDoc, CreateAgentNodeRequest, WorkerRegisterRequest
from app.models.base import mongo_doc_to_model, model_to_mongo_doc
from app.swarm.manager import SwarmManager

logger = get_logger(__name__)

_COLLECTION = "agent_nodes"


class AgentService:
    VALID_TRANSITIONS: dict[str, set[str]] = {
        "pending": {"running", "destroyed"},
        "running": {"paused", "destroyed"},
        "paused": {"running", "destroyed"},
        "destroyed": set(),
    }

    def __init__(self, db: AsyncDatabase[dict[str, object]], swarm_manager: SwarmManager | None = None) -> None:
        self._db = db
        self._swarm_manager = swarm_manager

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

    async def _update_and_return(self, filter: dict[str, object], update: dict[str, object]) -> AgentNodeDoc:
        result = await self._db[_COLLECTION].find_one_and_update(
            filter, update, return_document=ReturnDocument.AFTER,
        )
        if result is None:
            raise AgentNotFoundError()
        return mongo_doc_to_model(result, AgentNodeDoc)  # type: ignore[return-value]

    async def update_status(self, node_id: str, new_status: str) -> AgentNodeDoc:
        current = await self._db[_COLLECTION].find_one({"node_id": node_id})
        if current is None:
            raise AgentNotFoundError()

        current_status = cast(str, current.get("status", "pending"))
        allowed = self.VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise InvalidStatusTransition(
                f"Cannot transition from '{current_status}' to '{new_status}'"
            )

        container_id = cast(str | None, current.get("container_id"))

        if self._swarm_manager is not None and container_id is not None:
            if new_status == "paused":
                self._swarm_manager.pause_agent(container_id)
            elif new_status == "running" and current_status == "paused":
                self._swarm_manager.resume_agent(container_id)
            elif new_status == "destroyed":
                self._swarm_manager.destroy_agent(container_id)

        return await self._update_and_return(
            {"node_id": node_id},
            {"$set": {"status": new_status, "updated_at": datetime.now(UTC)}},
        )

    async def destroy(self, node_id: str) -> AgentNodeDoc:
        return await self.update_status(node_id, "destroyed")

    async def register_worker(self, node_id: str, request: WorkerRegisterRequest) -> AgentNodeDoc:
        result = await self._update_and_return(
            {"node_id": node_id, "status": "pending"},
            {"$set": {
                "container_id": request.container_id,
                "container_ip": request.container_ip,
                "container_hostname": request.container_hostname,
                "container_port": request.container_port,
                "status": "running",
                "updated_at": datetime.now(UTC),
            }},
        )
        logger.info("worker_registered", node_id=node_id, container_ip=request.container_ip)
        return result
