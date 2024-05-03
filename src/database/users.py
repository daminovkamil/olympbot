from sqlalchemy import not_, select
from .models import User, Activity, Event, Subject
from .connection import async_session


async def create(user_id: int) -> User:
    async with async_session() as session:
        user = User(id=user_id)
        session.add(user)
        await session.commit()
        return user


async def exists(user_id: int) -> bool:
    async with async_session() as session:
        return (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none() is not None


async def get(user_id: int) -> User:
    async with async_session() as session:
        if await exists(user_id):
            return (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        else:
            return await create(user_id)


async def event_filter(event: Event):
    async with async_session() as session:
        return (await session.execute(select(User).filter(
            User.activities.any(Activity.id == event.activity_id)
        ))).scalars()


async def news_filter(post):
    async with async_session() as session:
        activities = [activity.id for activity in post.activities]
        subjects = [subject.id for subject in post.subjects]
        return (await session.execute(select(User).filter(
            User.news_enabled &
            (not_(User.subjects_filter) | (User.subjects.any(Subject.id.in_(subjects)))) &
            (not_(User.olympiads_filter) | (User.activities.any(Activity.id.in_(activities))))
        ))).scalars()


async def get_events(user: User):
    async with async_session() as session:
        activities = [activity.id for activity in user.activities]
        return (await session.execute(select(Event).filter(
            Event.activity_id.in_(activities)
        ))).scalars()
