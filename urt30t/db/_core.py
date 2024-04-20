import asyncio
import logging

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .. import settings
from ..models import Group, Player
from ._models import Alias, Client, Guid, IPAddress

logger = logging.getLogger(__name__)

engine = create_async_engine(
    url=settings.bot.db_url,
    echo=settings.bot.db_debug,
    echo_pool=settings.bot.db_debug,
)

session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def sync_player(player: Player) -> None:
    async with session_maker.begin() as session:
        if client := await _find_client(session, player):
            player.db_id = client.cid
            player.group = Group(client.level)
            player.xp = client.xp
            async with asyncio.TaskGroup() as tg:
                tg.create_task(_sync_client_guids(session, client, player))
                tg.create_task(_sync_client_aliases(session, client, player))
                tg.create_task(_sync_client_ip_addresses(session, client, player))
        else:
            client = await _create_client(session, player)
            player.db_id = client.cid
            player.group = Group(client.level)
            player.xp = client.xp


async def _find_client(session: AsyncSession, player: Player) -> Client | None:
    if player.auth:
        stmt1 = sa.select(Client).where(Client.authl == player.auth)
        result1 = await session.execute(stmt1)
        return result1.scalar_one_or_none()
    if player.guid:
        stmt2 = sa.select(Guid).where(Guid.cl_guid == player.guid)
        result2 = await session.execute(stmt2)
        if db_guid := result2.scalar_one_or_none():
            return db_guid.client
        return None
    return None


async def _sync_client_guids(
    session: AsyncSession, client: Client, player: Player
) -> None:
    if not player.guid:
        return
    stmt = sa.select(Guid).where(Guid.cid == client.cid, Guid.cl_guid == player.guid)
    result = await session.execute(stmt)
    if client_guid := result.scalar_one_or_none():
        logger.error("Client %s has guid %s", client.cid, player.guid)
        client_guid.use_count += 1
    else:
        session.add(Guid(cid=client.cid, cl_guid=player.guid))


async def _sync_client_aliases(
    session: AsyncSession, client: Client, player: Player
) -> None:
    stmt = sa.select(Alias).where(Alias.cid == client.cid, Alias.alias == player.name)
    result = await session.execute(stmt)
    if client_alias := result.scalar_one_or_none():
        logger.error("Client %s has alias %s", client.cid, player.name)
        client_alias.use_count += 1
    else:
        session.add(Alias(cid=client.cid, alias=player.name))


async def _sync_client_ip_addresses(
    session: AsyncSession, client: Client, player: Player
) -> None:
    if player.ip_address is None:
        return
    stmt = sa.select(IPAddress).where(
        IPAddress.cid == client.cid, IPAddress.ip_address == player.ip_address
    )
    result = await session.execute(stmt)
    if client_ip_address := result.scalar_one_or_none():
        logger.error("Client %s has IP address %s", client.cid, player.ip_address)
        client_ip_address.use_count += 1
    else:
        session.add(IPAddress(cid=client.cid, ip_address=player.ip_address))


async def _create_client(session: AsyncSession, player: Player) -> Client:
    client = Client(authl=player.auth)
    client.aliases = [Alias(alias=player.name)]
    if player.guid is not None:
        client.cl_guids = [Guid(cl_guid=player.guid)]
    if player.ip_address is not None:
        client.ip_addresses = [IPAddress(ip_address=player.ip_address)]
    session.add(client)
    await session.flush()
    return client
