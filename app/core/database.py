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


@asynccontextmanager
async def mongo_lifespan(settings: Settings) -> AsyncGenerator[AsyncMongoClient[_DocType], None]:
    client = create_mongo_client(settings)
    try:
        yield client
    finally:
        await client.close()
