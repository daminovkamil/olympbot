import dataclasses

from .connection import db
import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class Event:
    event_id: int
    activity_id: int
    name: str
    first_date: Optional[datetime.date]
    second_date: Optional[datetime.date]
    id: Optional[int] = None

    def dates(self) -> list[datetime.date]:
        today = datetime.date.today()

        first_date = self.first_date
        second_date = self.second_date

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

        return [item for item in result if item > today]


def get_event(**kwargs) -> Optional[Event]:
    cursor = db.cursor()

    fields = dataclasses.fields(Event)
    columns = ', '.join([field.name for field in fields])

    if kwargs.keys() == {"id"}:
        cursor.execute(f"SELECT {columns} FROM events WHERE id = ?", (kwargs["id"],))
    elif kwargs.keys() == {"event_id", "activity_id"}:
        event_id = kwargs["event_id"]
        activity_id = kwargs["activity_id"]
        cursor.execute(f"SELECT {columns} FROM events WHERE event_id = ? AND activity_id = ?", (event_id, activity_id))
    else:
        return None

    result = cursor.fetchone()
    if result is not None:
        return Event(*result)
    else:
        return None


def save_event(event: Event) -> None:
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO events (event_id, activity_id, name, first_date, second_date) VALUES (?, ?, ?, ?, ?)",
        (event.event_id, event.activity_id, event.name, event.first_date, event.second_date)
    )
    db.commit()
    event.id = cursor.lastrowid
    for date in event.dates():
        cursor.execute(
            "INSERT INTO event_scheduler (date, event_id) VALUES (?, ?)",
            (date, event.id)
        )
    db.commit()


def delete_event(event_id: int) -> None:
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM events WHERE id = ?",
        (event_id,)
    )
    db.commit()


def current_events() -> list[Event]:
    cursor = db.cursor()
    cursor.execute(
        "SELECT event_id FROM event_scheduler WHERE date <= ?",
        (datetime.date.today(), ),
    )
    result = []
    for item in cursor.fetchall():
        event_id = item[0]
        result.append(get_event(id=event_id))
    return result


def delete_current() -> None:
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM event_scheduler WHERE date <= ?",
        (datetime.date.today(), )
    )
    db.commit()
