import datetime

import sqlalchemy as sa
import sqlalchemy.ext.asyncio
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)

from . import settings

engine = sqlalchemy.ext.asyncio.create_async_engine(
    url=settings.bot.db_url,
    echo=settings.bot.db_debug,
    echo_pool=settings.bot.db_debug,
)

async_session = sqlalchemy.ext.asyncio.async_sessionmaker(
    engine, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    auth: Mapped[str] = mapped_column(sa.String(32))
    level: Mapped[int]
    xp: Mapped[float]
    guid: Mapped[str] = mapped_column(sa.String(32))
    name: Mapped[str] = mapped_column(sa.String(32))
    ip_address: Mapped[str] = mapped_column(sa.String(48))
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=sa.func.now(), onupdate=sa.func.now()
    )
