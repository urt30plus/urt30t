import asyncio
import logging

import aiojobs

from . import __version__, parser, settings

logger = logging.getLogger(__name__)


async def run() -> None:
    logger.info("Bot v%s running", __version__)

    scheduler = aiojobs.Scheduler()
    await scheduler.spawn(parser.parse_log_events(settings.bot.games_log))

    while True:
        await asyncio.sleep(0.5)
