import asyncio
import contextlib
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Never

import aiojobs

from . import __version__, parser, settings
from .models import (
    BotError,
    Event,
    EventType,
    Game,
    GameType,
    LogEvent,
    Player,
    PlayerState,
)

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], Awaitable[None] | None]


class Bot:
    def __init__(self) -> None:
        self.start_time = time.time()
        self.game = Game()
        self.scheduler = aiojobs.Scheduler()
        self.events_queue = asyncio.Queue[LogEvent](settings.bot.event_queue_max_size)
        self.event_handlers: dict[EventType, list[EventHandler]] = defaultdict(list)

        self.event_handlers[EventType.init_game].append(self.on_init_game)
        self.event_handlers[EventType.say].append(self.on_say)

    async def event_dispatcher(self) -> Never:
        while log_event := await self.events_queue.get():
            if handlers := self.event_handlers.get(log_event.type):
                event = parser.parse_from_log_event(log_event)
                for handler in handlers:
                    # TODO: handle regular and async functions as handlers
                    await handler(event)  # type: ignore
            else:
                logger.debug("no handler registered for event: %r", log_event)

        raise BotError

    async def on_init_game(self, event: Event) -> None:
        logger.info("on_init_game: %r", event)
        if not event.data:
            logger.error("missing event data")
            raise BotError
        parts = event.data["text"].lstrip("\\").split("\\")
        data = dict(zip(parts[0::2], parts[1::2], strict=True))
        self.game = Game(type=GameType(data["g_gametype"]), map_name=data["mapname"])
        logger.info("updated game: %r", self.game)

    async def on_client_connect(self, event: Event) -> None:
        if event.client:
            with contextlib.suppress(KeyError):
                del self.game.players[event.client]

    async def on_client_disconnect(self, event: Event) -> None:
        if event.client:
            with contextlib.suppress(KeyError):
                del self.game.players[event.client]

    async def on_client_user_info(self, event: Event) -> None:
        if event.client:
            player = Player(id=event.client)
            self.game.players[player.id] = player

    async def on_client_spawn(self, event: Event) -> None:
        if event.client:
            self.game.players[event.client].state = PlayerState.ALIVE

    async def on_say(self, event: Event) -> None:
        logger.info("on_say_team: %r", event)

    async def run(self) -> Never:
        logger.info("Bot v%s running", __version__)
        await self.scheduler.spawn(
            parser.tail_log_events(settings.bot.games_log, self.events_queue)
        )
        await self.scheduler.spawn(self.event_dispatcher())

        while True:
            await asyncio.sleep(0.5)
