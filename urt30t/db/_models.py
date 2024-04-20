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


class Client(Base):
    __tablename__ = "urt30t_clients"

    cid: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    authl: Mapped[str] = mapped_column(sa.String(32), index=True, unique=True)
    level: Mapped[int] = mapped_column(default=models.Group.GUEST.value)
    xp: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=sa.func.now(), onupdate=sa.func.now()
    )
    cl_guids: Mapped[list["Guid"]] = relationship(back_populates="client")
    aliases: Mapped[list["Alias"]] = relationship(back_populates="client")
    ip_addresses: Mapped[list["IPAddress"]] = relationship(back_populates="client")

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(cid={self.cid}, authl={self.authl})"


class Guid(Base):
    __tablename__ = "urt30t_guids"

    cid: Mapped[int] = mapped_column(sa.ForeignKey(Client.cid), primary_key=True)
    cl_guid: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    use_count: Mapped[int] = mapped_column(sa.Integer(), insert_default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())
    client: Mapped[Client] = relationship(back_populates="cl_guids")

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(cid={self.cid}, cl_guid={self.cl_guid})"


class Alias(Base):
    __tablename__ = "urt30t_aliases"

    cid: Mapped[int] = mapped_column(sa.ForeignKey(Client.cid), primary_key=True)
    alias: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    use_count: Mapped[int] = mapped_column(sa.Integer(), insert_default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())
    client: Mapped[Client] = relationship(back_populates="aliases")

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(cid={self.cid}, alias={self.alias})"


class IPAddress(Base):
    __tablename__ = "urt30t_ip_addresses"

    cid: Mapped[int] = mapped_column(sa.ForeignKey(Client.cid), primary_key=True)
    ip_address: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    use_count: Mapped[int] = mapped_column(sa.Integer(), insert_default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=sa.func.now())
    client: Mapped[Client] = relationship(back_populates="ip_addresses")

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}"
            f"(cid={self.cid}, ip_address={self.ip_address})"
        )


class Connection(Base):
    __tablename__ = "urt30t_connections"

    cid: Mapped[int] = mapped_column(sa.ForeignKey(Client.cid), primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=sa.func.now(), primary_key=True
    )

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}(cid={self.cid}@{self.created_at})"


class Penalty(Base):
    __tablename__ = "urt30t_penalties"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cid: Mapped[int] = mapped_column(sa.ForeignKey(Client.cid))
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
