import datetime

import sqlalchemy as sa
import sqlalchemy.ext.asyncio
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)

from . import models, settings

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
    level: Mapped[int] = mapped_column(default=models.Group.GUEST.value)
    xp: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=sa.func.now(), onupdate=sa.func.now()
    )

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(id={self.id}, auth={self.auth})"


class Guid(Base):
    __tablename__ = "urt30t_guids"

    pid: Mapped[int] = mapped_column(
        sa.ForeignKey(Player.id), primary_key=True, autoincrement=False
    )
    guid: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    use_count: Mapped[int]
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(pid={self.pid}, guid={self.guid})"


class Alias(Base):
    __tablename__ = "urt30t_aliases"

    pid: Mapped[int] = mapped_column(
        sa.ForeignKey(Player.id), primary_key=True, autoincrement=False
    )
    alias: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    use_count: Mapped[int]
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(pid={self.pid}, alias={self.alias})"


class Address(Base):
    __tablename__ = "urt30t_addressses"

    pid: Mapped[int] = mapped_column(
        sa.ForeignKey(Player.id), primary_key=True, autoincrement=False
    )
    address: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    use_count: Mapped[int]
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(pid={self.pid}, address={self.address})"


class Connection(Base):
    __tablename__ = "urt30t_connections"

    pid: Mapped[int] = mapped_column(
        sa.ForeignKey(Player.id), primary_key=True, autoincrement=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=sa.func.now(), primary_key=True
    )

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(pid={self.pid}@{self.created_at})"


class Penalty(Base):
    __tablename__ = "urt30t_penalties"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pid: Mapped[int] = mapped_column(sa.ForeignKey(Player.id))
    kind: Mapped[models.Penalty] = mapped_column(sa.Enum(models.Penalty, length=20))
    reason: Mapped[str | None] = mapped_column(sa.String(255))
    duration: Mapped[int | None]
    expires_at: Mapped[datetime.datetime | None]
    created_by: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=sa.func.now(), onupdate=sa.func.now()
    )

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(id={self.id}, kind={self.kind})"
