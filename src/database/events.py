import datetime
from typing import Optional
from sqlalchemy import select

from .models import Event, EventScheduler
from .connection import async_session


async def get_event(**kwargs) -> Optional[Event]:
    async with async_session() as session:
        return (await session.execute(select(Event).filter_by(**kwargs))).scalar_one_or_none()


async def delete_event(**kwargs):
    async with async_session() as session:
        event = await get_event(**kwargs)
        if event:
            await session.delete(event)
            await session.commit()


async def get_dates(event: Event) -> list[datetime.date]:
    today = datetime.date.today()
    first_date = event.first_date
    second_date = event.second_date
    result = []

    if first_date is None:
        result.extend([second_date - datetime.timedelta(days=delta) for delta in [7, 3, 1]])
    else:
        result.extend([first_date - datetime.timedelta(days=delta) for delta in [7, 3, 1]])

        if second_date:
            duration = second_date - first_date
            if duration >= datetime.timedelta(days=13):
                result.append(second_date - datetime.timedelta(days=7))
            if duration >= datetime.timedelta(days=6):
                result.append(second_date - datetime.timedelta(days=3))
            if duration >= datetime.timedelta(days=3):
                result.append(second_date - datetime.timedelta(days=1))

    return [date for date in result if date > today]


async def save_event(event: Event):
    async with async_session() as session:
        session.add(event)
        await session.flush()

        for date in await get_dates(event):
            scheduler = EventScheduler(date=date, event_id=event.id)
            session.add(scheduler)

        await session.commit()
