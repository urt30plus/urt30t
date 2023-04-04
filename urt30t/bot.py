import abc
import asyncio
import importlib.util
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
    LogEvent,
)

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], Awaitable[None]]


class BotPlugin(abc.ABC):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    @abc.abstractmethod
    async def on_load(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def on_unload(self) -> None:
        raise NotImplementedError


class Bot:
    def __init__(self) -> None:
        self.start_time = time.time()
        self.game = Game()
        self.scheduler = aiojobs.Scheduler()
        self.events_queue = asyncio.Queue[LogEvent](settings.bot.event_queue_max_size)
        self._plugins: list["BotPlugin"] = []
        self._event_handlers: dict[EventType, list[EventHandler]] = defaultdict(list)

    def register_event_handler(
        self, event_type: EventType, event_handler: EventHandler
    ) -> None:
        handlers = self._event_handlers[event_type]
        if event_handler in handlers:
            raise BotError
        handlers.append(event_handler)

    async def load_plugins(self) -> None:
        plugins_specs = ["urt30t.plugins.core.CorePlugin", *settings.bot.plugins]
        logger.info("attempting to load plugin classes: %s", plugins_specs)
        plugin_classes: list[type[BotPlugin]] = []
        for spec in plugins_specs:
            mod_path, class_name = spec.rsplit(".", maxsplit=1)
            mod = importlib.import_module(mod_path)
            plugin_class = getattr(mod, class_name)
            if not issubclass(plugin_class, BotPlugin):
                logger.error("%s is not a BotPlugin subclass")
            else:
                plugin_classes.append(plugin_class)

        # TODO: topo sort based on deps

        for cls in plugin_classes:
            obj = cls(bot=self)
            await obj.on_load()
            self._plugins.append(obj)

    async def event_dispatcher(self) -> Never:
        while log_event := await self.events_queue.get():
            if handlers := self._event_handlers.get(log_event.type):
                event = parser.parse_from_log_event(log_event)
                for handler in handlers:
                    # TODO: handle regular and async functions as handlers
                    await handler(event)
            else:
                logger.debug("no handler registered for event: %r", log_event)

        raise BotError

    async def run(self) -> Never:
        logger.info("Bot v%s running", __version__)
        await self.scheduler.spawn(
            parser.tail_log_events(settings.bot.games_log, self.events_queue)
        )
        await self.load_plugins()
        await self.event_dispatcher()
