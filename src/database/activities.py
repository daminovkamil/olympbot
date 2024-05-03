from .models import Activity
from .connection import async_session
from sqlalchemy import select


async def all_activities():
    async with async_session() as session:
        return (await session.execute(select(Activity))).scalars()
