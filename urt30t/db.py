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
    __tablename__ = "urt30t_players"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    auth: Mapped[str] = mapped_column(sa.String(32), index=True, unique=True)
    guid: Mapped[str] = mapped_column(sa.String(32), index=True, unique=True)
    name: Mapped[str] = mapped_column(sa.String(32), index=True)
    level: Mapped[int] = mapped_column(default=0)
    xp: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=sa.func.now(), onupdate=sa.func.now()
    )

    def __repr__(self) -> str:
        return f"Player(id={self.id}, auth={self.auth})"
