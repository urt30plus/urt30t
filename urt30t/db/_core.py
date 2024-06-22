import asyncio
import logging

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from .. import settings
from ..models import Group, Player
from ._models import Alias, Connection, Guid, IPAddress
from ._models import Player as DBPlayer

logger = logging.getLogger(__name__)

engine = create_async_engine(
    url=settings.bot.db_url,
    echo=settings.bot.db_debug,
    echo_pool=settings.bot.db_debug,
)

session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def sync_player(player: Player) -> None:
    if db_player := await _find_player(player):
        if not player.db_id:
            await _sync_player_connections(db_player.pid)
        _sync_player_attrs(db_player, player)
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_sync_player_guids(db_player, player))
            tg.create_task(_sync_player_aliases(db_player, player))
            tg.create_task(_sync_player_ip_addresses(db_player, player))
    else:
        db_player = await _create_player(player)
        await _sync_player_connections(db_player.pid)
        _sync_player_attrs(db_player, player)


async def _find_player(player: Player) -> DBPlayer | None:
    async with session_maker() as session:
        if player.db_id:
            rv = await session.get(DBPlayer, player.db_id)
            logger.info("db_id lookup returned: %r [%s]", rv, type(rv))
            return rv
        if player.auth:
            stmt1 = sa.select(DBPlayer).where(DBPlayer.auth == player.auth)
            result1 = await session.execute(stmt1)
            # TODO: lookup guid if not set on player
            return result1.scalar_one_or_none()
        if player.guid:
            stmt2 = sa.select(Guid).where(Guid.guid == player.guid)
            result2 = await session.execute(stmt2)
            if db_guid := result2.scalar_one_or_none():
                player.auth = db_guid.player.auth
                return db_guid.player
    return None


def _sync_player_attrs(db_player: DBPlayer, player: Player) -> None:
    player.db_id = db_player.pid
    player.group = Group(db_player.group)
    player.xp = db_player.xp


async def _sync_player_guids(db_player: DBPlayer, player: Player) -> None:
    if not player.guid:
        return
    async with session_maker.begin() as session:
        stmt = sa.select(Guid).where(
            Guid.pid == db_player.pid, Guid.guid == player.guid
        )
        result = await session.execute(stmt)
        if db_guid := result.scalar_one_or_none():
            db_guid.use_count += 1
        else:
            session.add(Guid(pid=db_player.pid, guid=player.guid))


async def _sync_player_aliases(db_player: DBPlayer, player: Player) -> None:
    async with session_maker.begin() as session:
        stmt = sa.select(Alias).where(
            Alias.pid == db_player.pid, Alias.alias == player.name
        )
        result = await session.execute(stmt)
        if db_alias := result.scalar_one_or_none():
            db_alias.use_count += 1
        else:
            session.add(Alias(pid=db_player.pid, alias=player.name))


async def _sync_player_ip_addresses(db_player: DBPlayer, player: Player) -> None:
    if player.ip_address is None:
        return
    stmt = sa.select(IPAddress).where(
        IPAddress.pid == db_player.pid, IPAddress.address == player.ip_address
    )
    async with session_maker.begin() as session:
        result = await session.execute(stmt)
        if db_ip_address := result.scalar_one_or_none():
            db_ip_address.use_count += 1
        else:
            session.add(IPAddress(pid=db_player.pid, address=player.ip_address))


async def _sync_player_connections(pid: int) -> None:
    async with session_maker.begin() as session:
        session.add(Connection(pid=pid))


async def _create_player(player: Player) -> DBPlayer:
    db_player = DBPlayer(
        auth=player.auth,
        guid=player.guid,
        name=player.name,
        ip_address=player.ip_address,
    )
    db_player.aliases = [Alias(alias=player.name)]
    if player.guid is not None:
        db_player.guids = [Guid(guid=player.guid)]
    if player.ip_address is not None:
        db_player.ip_addresses = [IPAddress(address=player.ip_address)]
    async with session_maker.begin() as session:
        session.add(db_player)
        await session.flush()
        return db_player
