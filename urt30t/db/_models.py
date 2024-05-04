import datetime

import sqlalchemy as sa
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from .. import models


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "urt30t_players"

    pid: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    auth: Mapped[str] = mapped_column(sa.String(32), index=True, unique=True)
    guid: Mapped[str] = mapped_column(sa.String(32), index=True, unique=True)
    name: Mapped[str] = mapped_column(sa.String(32))
    ip_address: Mapped[str] = mapped_column(sa.String(64))
    group: Mapped[int] = mapped_column(default=models.Group.GUEST.value)
    xp: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=sa.func.now(), onupdate=sa.func.now()
    )

    guids: Mapped[list["Guid"]] = relationship(back_populates="player")
    aliases: Mapped[list["Alias"]] = relationship(back_populates="player")
    ip_addresses: Mapped[list["IPAddress"]] = relationship(back_populates="player")

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(pid={self.pid}, auth={self.auth})"


class Guid(Base):
    __tablename__ = "urt30t_guids"

    pid: Mapped[int] = mapped_column(sa.ForeignKey(Player.pid), primary_key=True)
    guid: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    use_count: Mapped[int] = mapped_column(sa.Integer(), insert_default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=sa.func.now(), onupdate=sa.func.now()
    )

    player: Mapped[Player] = relationship(back_populates="guids")

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(pid={self.pid}, guid={self.guid})"


class Alias(Base):
    __tablename__ = "urt30t_aliases"

    pid: Mapped[int] = mapped_column(sa.ForeignKey(Player.pid), primary_key=True)
    alias: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    use_count: Mapped[int] = mapped_column(sa.Integer(), insert_default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=sa.func.now(), onupdate=sa.func.now()
    )

    player: Mapped[Player] = relationship(back_populates="aliases")

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(pid={self.pid}, alias={self.alias})"


class IPAddress(Base):
    __tablename__ = "urt30t_ip_addresses"

    pid: Mapped[int] = mapped_column(sa.ForeignKey(Player.pid), primary_key=True)
    address: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    use_count: Mapped[int] = mapped_column(sa.Integer(), insert_default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=sa.func.now(), onupdate=sa.func.now()
    )

    player: Mapped[Player] = relationship(back_populates="ip_addresses")

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}" f"(cid={self.pid}, ip={self.address})"


class Connection(Base):
    __tablename__ = "urt30t_connections"

    pid: Mapped[int] = mapped_column(sa.ForeignKey(Player.pid), primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=sa.func.now(), primary_key=True
    )

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}({self.pid}@{self.created_at})"


class Penalty(Base):
    __tablename__ = "urt30t_penalties"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pid: Mapped[int] = mapped_column(sa.ForeignKey(Player.pid))
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
        return (
            f"{self.__class__.__qualname__}"
            f"(id={self.id}, pid={self.pid}, kind={self.kind})"
        )
