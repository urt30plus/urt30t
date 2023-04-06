import asyncio
import contextlib
import importlib.util
import inspect
import logging
import os
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, NamedTuple, TypeVar

import aiofiles
import aiofiles.os
import aiojobs

from . import events, rcon, settings
from .models import (
    Game,
    Group,
    Player,
)

__version__ = "30.0.0.rc1"

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

EventHandler = Callable[[events.GameEvent], Awaitable[None]]
CommandHandler = Callable[[Player, str | None], Awaitable[None]]
CommandFunction = Callable[[Any, Player, str | None], Awaitable[None]]

_plugins: list["BotPlugin"] = []
_event_handlers: dict[type[events.GameEvent], list[EventHandler]] = defaultdict(list)
_command_handlers: dict[str, "BotCommandHandler"] = {}

_event_class_by_action: dict[str, type[events.GameEvent]] = {
    x[0].lower(): x[1]
    for x in inspect.getmembers(events, predicate=inspect.isclass)
    if issubclass(x[1], events.GameEvent)
}

_core_plugins = [
    "urt30t.plugins.core.GameStatePlugin",
    "urt30t.plugins.core.CommandsPlugin",
]


class BotError(Exception):
    pass


class BotPlugin:
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    async def plugin_load(self) -> None:
        pass

    async def plugin_unload(self) -> None:
        pass


class BotCommand(NamedTuple):
    name: str
    level: Group = Group.user
    alias: str | None = None


class BotCommandHandler(NamedTuple):
    command: BotCommand
    handler: CommandHandler


class Bot:
    def __init__(self) -> None:
        self.start_time = time.time()
        self.game = Game()
        self.scheduler = aiojobs.Scheduler()
        self.events_queue = asyncio.Queue[events.LogEvent](
            settings.bot.event_queue_max_size
        )
        self.rcon = rcon.client

    @staticmethod
    def find_command(name: str) -> BotCommandHandler | None:
        if handler := _command_handlers.get(name):
            return handler
        for handler in _command_handlers.values():
            if handler.command.alias == name:
                return handler
        return None

    def find_player(self, slot: str) -> Player | None:
        return self.game.players.get(slot)

    async def disconnect_player(self, slot: str) -> None:
        with contextlib.suppress(KeyError):
            del self.game.players[slot]

    async def load_plugins(self) -> None:
        plugins_specs = [*_core_plugins, *settings.bot.plugins]
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
            await obj.plugin_load()
            _plugins.append(obj)
            register_plugin(obj)

    async def event_dispatcher(self) -> None:
        event_queue_get = self.events_queue.get
        event_queue_done = self.events_queue.task_done
        handlers_get = _event_handlers.get
        while log_event := await event_queue_get():
            if log_event.type is None:
                event_queue_done()
                continue
            if not (event_class := _event_class_by_action.get(log_event.type)):
                logger.warning("no event class found: %r", log_event)
                event_queue_done()
                continue
            if handlers := handlers_get(event_class):
                event = event_class.from_log_event(log_event)
                for handler in handlers:
                    try:
                        await handler(event)
                    except Exception:
                        logger.exception("%r failed to handle %r", handler, event)
            else:
                logger.debug("no handler registered for event: %r", log_event)

            event_queue_done()

    async def private_message(self, player: Player, message: str) -> None:
        await self.rcon.send(f'tell {player.id} "{message}"', retries=1)

    async def broadcast(self, message: str) -> None:
        await self.rcon.send(f'"{message}"', retries=1)

    async def message(self, message: str) -> None:
        await self.rcon.send(f'say "{message}"', retries=1)

    async def sync_game(self) -> None:
        old_game = self.game
        new_game = await self.rcon.game_info()
        logger.debug("Game state: %r --> %r", old_game, new_game)
        self.game = new_game

    async def run(self) -> None:
        logger.info("Bot v%s running", __version__)
        await self.scheduler.spawn(
            tail_log_events(settings.bot.games_log, self.events_queue)
        )
        await self.sync_game()
        await self.load_plugins()
        await self.event_dispatcher()


def register_plugin(plugin: BotPlugin) -> None:
    for _, meth in inspect.getmembers(plugin, predicate=inspect.iscoroutinefunction):
        if subscription := getattr(meth.__func__, "bot_subscription", None):
            _event_handlers[subscription].append(meth)
            logger.info("add subscription: %s - %s", subscription, meth)

        if cmd := getattr(meth.__func__, "bot_command", None):
            cmd_handler = BotCommandHandler(command=cmd, handler=meth)
            _command_handlers[cmd.name] = cmd_handler
            logger.info("added %r", cmd_handler)


def bot_command(
    level: Group = Group.user, alias: str | None = None
) -> Callable[[CommandFunction], CommandFunction]:
    def inner(f: CommandFunction) -> CommandFunction:
        name = f.__name__.removeprefix("cmd_")
        f.bot_command = BotCommand(  # type: ignore[attr-defined]
            name=name.lower(),
            level=level,
            alias=alias,
        )
        return f

    return inner


def bot_subscribe(
    event_type: type[_T],
) -> Callable[
    [Callable[[Any, _T], Awaitable[None]]], Callable[[Any, _T], Awaitable[None]]
]:
    def inner(
        f: Callable[[Any, _T], Awaitable[None]]
    ) -> Callable[[Any, _T], Awaitable[None]]:
        f.bot_subscription = event_type  # type: ignore[attr-defined]
        return f

    return inner


async def tail_log_events(log_file: Path, q: asyncio.Queue[events.LogEvent]) -> None:
    logger.info("Parsing game log file %s", log_file)
    async with aiofiles.open(log_file, encoding="utf-8") as fp:
        cur_pos = await fp.seek(0, os.SEEK_END)
        logger.info("Log file current position: %s", cur_pos)
        # signal that we are ready and wait for the event dispatcher to start
        await q.put(events.LogEvent())
        await q.join()
        while await asyncio.sleep(0.250, result=True):
            if not (lines := await fp.readlines()):
                # No lines found so check to see if we need to reset our position.
                # Compare the current cursor position against the current file size,
                # if the cursor is at a number higher than the game log size, then
                # there's a problem
                stats = await aiofiles.os.stat(fp.fileno())
                cur_pos = await fp.tell()
                if cur_pos > stats.st_size:
                    logger.warning(
                        "Detected a change in size of the log file, "
                        f"before ({cur_pos} bytes, now {stats.st_size}). "
                        "The log was either rotated or emptied."
                    )
                    await fp.seek(0, os.SEEK_END)
                    lines = await fp.readlines()

            for line in lines:
                await q.put(parse_log_line(line))


def parse_log_line(line: str) -> events.LogEvent:
    """Creates a LogEvent from a raw log entry.

    A typical log entry usually starts with the time (MMM:SS) left padded
    with spaces, the event followed by a colon and then the even data. Ex.

    This function main purpose is to perform a first pass parsing of the data
    in order to determine basic information about the log entry, such as
    the type of event.
    """
    game_time, _, rest = line.strip().partition(" ")
    event_name, sep, data = rest.partition(":")
    if sep:
        event_type = event_name.lower().replace(" ", "")
        data = data.lstrip()
    elif event_name.startswith("Bombholder is "):
        event_type = "bombholder"
        data = event_name[14:]
    elif event_name.startswith("Bomb was "):
        event_type = "bomb"
        data = event_name[9:]
    elif event_name.startswith("Bomb has been "):
        event_type = "bomb"
        data = event_name[14:]
    elif event_name.startswith("Session data initialised for client on slot "):
        event_type = "sessiondatainitialised"
        data = event_name[44:]
    elif not event_name.strip("-"):
        event_type = None
        data = ""
    else:
        logger.warning("event type not in log line: [%s]", line)
        event_type = None
        data = event_name

    event = events.LogEvent(type=event_type, game_time=game_time, data=data)
    logger.debug(event)
    return event
