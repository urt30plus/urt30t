import asyncio
import logging
import time
from typing import Never

import aiojobs

from . import __version__, parser, settings
from .models import Game, LogEvent

logger = logging.getLogger(__name__)


class Bot:
    def __init__(self) -> None:
        self.scheduler = aiojobs.Scheduler()
        self.events_queue = asyncio.Queue[LogEvent](settings.bot.event_queue_max_size)
        self.game = Game()
        self.start_time = time.time()

    async def event_dispatcher(self) -> None:
        q = self.events_queue
        while event := await q.get():
            logger.debug(event)

    async def run(self) -> Never:
        logger.info("Bot v%s running", __version__)
        await self.scheduler.spawn(
            parser.parse_log_events(settings.bot.games_log, self.events_queue)
        )
        await self.scheduler.spawn(self.event_dispatcher())

        while True:
            await asyncio.sleep(0.5)
