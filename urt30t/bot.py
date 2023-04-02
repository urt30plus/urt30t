import asyncio
import logging
import time
from collections.abc import Coroutine
from typing import Any

import aiojobs

from . import __version__, parser, settings
from .game import Game

logger = logging.getLogger(__name__)


class BotContext:
    def __init__(self) -> None:
        self.start_time = time.time()
        self._scheduler: aiojobs.Scheduler | None = None
        self.game = Game()

    def uptime(self) -> float:
        return time.time() - self.start_time

    async def run_task(self, task: Coroutine[Any, Any, Any]) -> aiojobs.Job[Any]:
        if self._scheduler is None:
            self._scheduler = aiojobs.Scheduler()
        return await self._scheduler.spawn(task)


context = BotContext()


async def run() -> None:
    logger.info("Bot v%s running", __version__)
    await context.run_task(parser.parse_log_events(settings.bot.games_log))
    while True:
        await asyncio.sleep(0.5)
