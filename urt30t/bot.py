import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Never

import aiojobs

from . import __version__, parser, settings
from .models import Event, EventType, Game, LogEvent

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], Awaitable[None] | None]


class Bot:
    def __init__(self) -> None:
        self.start_time = time.time()
        self.game = Game()
        self.scheduler = aiojobs.Scheduler()
        self.events_queue = asyncio.Queue[LogEvent](settings.bot.event_queue_max_size)
        self.event_handlers: dict[EventType, list[EventHandler]] = defaultdict(list)

    async def event_dispatcher(self) -> None:
        while log_event := await self.events_queue.get():
            if handlers := self.event_handlers.get(log_event.type):
                event = parser.parse_from_log_event(log_event)
                for handler in handlers:
                    handler(event)
            else:
                logger.debug("no handler registered for event: %r", log_event)

    async def run(self) -> Never:
        logger.info("Bot v%s running", __version__)
        await self.scheduler.spawn(
            parser.tail_log_events(settings.bot.games_log, self.events_queue)
        )
        await self.scheduler.spawn(self.event_dispatcher())

        while True:
            await asyncio.sleep(0.5)
