"""Файл отвечает за запросы к базе данных"""
from postgres import Postgres
from config import database_url

db = Postgres(database_url)


async def execute(*args, **kwargs):
    db.run(*args, **kwargs)


async def fetch(*args, **kwargs):
    return db.all(*args, **kwargs)


async def fetchrow(*args, **kwargs):
    return db.one(*args, **kwargs)


async def user_exists(user_id: int) -> bool:
    return await fetchrow(f"SELECT user_id FROM users WHERE user_id = {user_id}") is not None


async def get_user_tags(user_id: int) -> int:
    return await fetchrow(f"SELECT tags FROM users WHERE user_id = {user_id}")
