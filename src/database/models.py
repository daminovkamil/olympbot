import asyncio
import datetime
from .connection import Base, engine, async_session
from sqlalchemy import Table
from sqlalchemy import select
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import BigInteger, JSON, Column, TEXT, String, DateTime, Date
from typing import Set

users_to_activities_table = Table(
    "users_to_activities_table",
    Base.metadata,
    Column("user_id", ForeignKey("users.id")),
    Column("activity_id", ForeignKey("activities.id")),
)

users_to_subjects_table = Table(
    "users_to_subjects_table",
    Base.metadata,
    Column("user_id", ForeignKey("users.id")),
    Column("subject_id", ForeignKey("subjects.id")),
)


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    subjects_filter: Mapped[bool] = mapped_column(nullable=False, default=False)
    olympiads_filter: Mapped[bool] = mapped_column(nullable=False, default=False)
    notifications_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    news_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)

    activities: Mapped[Set["Activity"]] = relationship(
        secondary=users_to_activities_table,
        back_populates="users",
        lazy="selectin",
    )
    subjects: Mapped[Set["Subject"]] = relationship(
        secondary=users_to_subjects_table,
        back_populates="users",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<User(id={self.id})>"


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name = Column(TEXT, nullable=False)
    data = Column(JSON, default={}, nullable=False)

    users: Mapped[Set["User"]] = relationship(
        secondary=users_to_activities_table,
        back_populates="activities",
        lazy="selectin",
    )

    @property
    def top_level(self) -> bool:
        if "top_level" in self.data:
            return self.data["top_level"]
        return False

    @property
    def parent(self):
        if "parent" in self.data:
            return self.data["parent"]
        return None

    @property
    async def children(self):
        if "children" in self.data:
            async with async_session() as session:
                result = await session.execute(select(Activity).filter(Activity.id.in_(self.data["children"])))
                return set(result.scalars())
        return set()

    def __repr__(self):
        return f"<Activity(id={self.id})>"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[int] = mapped_column(String(64), nullable=False, unique=True)

    users: Mapped[Set["User"]] = relationship(
        secondary=users_to_subjects_table,
        back_populates="subjects",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Subject(id={self.id}, name={self.name})>"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(nullable=False)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    first_date: Mapped[datetime.date] = mapped_column(nullable=True, default=None)
    second_date: Mapped[datetime.date] = mapped_column(nullable=True, default=None)

    def __repr__(self):
        return (f"<Event(id={self.id}, event_id={self.event_id}, activity_id={self.activity_id}, "
                f"name={self.name}, first_date={self.first_date}, second_date={self.second_date})>")


class EventScheduler(Base):
    __tablename__ = "event_scheduler"

    id: Mapped[int] = mapped_column(primary_key=True)
    date = Column(Date, nullable=False)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)

    def __repr__(self):
        return f"<EventScheduler(id={self.id}, date={self.date}, event_id={self.event_id})>"


class PageArchive(Base):
    __tablename__ = "pages"

    url: Mapped[str] = mapped_column(String(256), primary_key=True)
    html = Column(TEXT, nullable=False)
    loaded = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"PageArchive(url={self.url})"


class LastPost(Base):
    __tablename__ = "last_post"

    post_id: Mapped[int] = mapped_column(primary_key=True)


async def create_table():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
