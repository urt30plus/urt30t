import logging

from .. import rcon, settings, tasks
from . import gameinfo, mapcycle
from .client import DiscordClient

logger = logging.getLogger(__name__)

__all__ = [
    "DiscordClient",
    "start_jobs",
]


async def start_jobs(
    discord_client: DiscordClient, rcon_client: rcon.RconClient
) -> None:
    try:
        await discord_client.login(settings.discord.token)
    except Exception:
        logger.exception("Discord login failed")
        return

    tasks.background(gameinfo.run(discord_client, rcon_client))
    tasks.background(mapcycle.run(discord_client, rcon_client))
