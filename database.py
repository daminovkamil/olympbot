"""Файл отвечает за запросы к базе данных"""
import asyncpg
import asyncio
import atexit

from config import database_url


# исполняет асинхронную функцию
def run(future):
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(future)
    return result


connection: asyncpg.Connection = run(asyncpg.connect(database_url))


def close_connection():
    run(connection.close())


# закрывает соединение перед завершением работы файла
atexit.register(close_connection)


async def execute(*args, **kwargs):
    await connection.execute(*args, **kwargs)


async def fetch(*args, **kwargs):
    return await connection.fetch(*args, **kwargs)


async def fetchrow(*args, **kwargs):
    return await connection.fetchrow(*args, **kwargs)


async def user_exists(user_id: int) -> bool:
    return await connection.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id) is not None


async def get_user_tags(user_id: int) -> int:
    record = await connection.fetchrow("SELECT tags FROM users WHERE user_id = $1", user_id)
    return record["tags"]
