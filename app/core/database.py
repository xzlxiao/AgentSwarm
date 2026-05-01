from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings

_DocType = dict[str, object]


def create_mongo_client(settings: Settings) -> AsyncMongoClient[_DocType]:
    return AsyncMongoClient(settings.mongo_uri)


def get_database(client: AsyncMongoClient[_DocType], settings: Settings) -> AsyncDatabase[_DocType]:
    return client[settings.mongo_db_name]


async def ensure_indexes(db: AsyncDatabase[_DocType]) -> None:
    """创建 MongoDB 索引。幂等操作, 已存在则跳过。"""
    await db["agent_nodes"].create_index("node_id", unique=True)
    await db["agent_nodes"].create_index("workspace_id")
    await db["agent_nodes"].create_index("status")
    await db["project_workspaces"].create_index("workspace_id", unique=True)
    await db["project_workspaces"].create_index("status")
    await db["token_usage"].create_index("agent_node_id")
    await db["token_usage"].create_index("request_id", unique=True)


@asynccontextmanager
async def mongo_lifespan(settings: Settings) -> AsyncGenerator[AsyncMongoClient[_DocType], None]:
    client = create_mongo_client(settings)
    try:
        yield client
    finally:
        await client.close()
