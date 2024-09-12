from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from .config import settings

client = AsyncIOMotorClient(settings.MONGODB_URL)
db = client['kopa_db']


async def get_db():
    return db