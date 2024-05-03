from .connection import async_session
from .models import LastPost
from sqlalchemy import select


async def get_last_post_id():
    async with async_session() as session:
        last_post = (await session.execute(select(LastPost))).scalar_one()
        return last_post.post_id


async def update_last_post_id(post_id):
    async with async_session() as session:
        last_post = (await session.execute(select(LastPost))).scalar_one()
        last_post.post_id = post_id
        await session.commit()
