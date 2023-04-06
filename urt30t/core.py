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
from typing import Any, NamedTuple

import aiofiles
import aiofiles.os
import aiojobs

from . import rcon, settings
from .models import (
    Event,
    EventType,
    Game,
    Group,
    LogEvent,
    Player,
)

__version__ = "30.0.0.rc1"

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], Awaitable[None]]
CommandHandler = Callable[[Player, str | None], Awaitable[None]]
CommandFunction = Callable[[Any, Player, str | None], Awaitable[None]]

_plugins: list["BotPlugin"] = []
_event_handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
_command_handlers: dict[str, "BotCommandHandler"] = {}

_core_plugins = [
    "urt30t.plugins.core.GameStatePlugin",
    "urt30t.plugins.core.CommandsPlugin",
]

_ignored_events = (
    EventType.log_parser_ready,
    EventType.log_separator,
    EventType.session_data_initialised,
)


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
        self.events_queue = asyncio.Queue[LogEvent](settings.bot.event_queue_max_size)
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
            register_event_handlers(obj)
            register_command_handlers(obj)

    async def event_dispatcher(self) -> None:
        event_queue_get = self.events_queue.get
        event_queue_done = self.events_queue.task_done
        handlers_get = _event_handlers.get
        while log_event := await event_queue_get():
            if (event_type := log_event.type) in _ignored_events:
                event_queue_done()
                continue
            if handlers := handlers_get(event_type):
                event = parse_log_event(log_event)
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


def register_event_handlers(plugin: BotPlugin) -> None:
    for name, meth in inspect.getmembers(plugin, predicate=inspect.iscoroutinefunction):
        if not name.startswith("on_"):
            continue
        event_name = name.removeprefix("on_")
        event_type = EventType[event_name]
        _event_handlers[event_type].append(meth)
        logger.info("added %s event handler: %s", event_type, meth)


def register_command_handlers(plugin: BotPlugin) -> None:
    for _, meth in inspect.getmembers(plugin, predicate=inspect.iscoroutinefunction):
        if not (cmd := getattr(meth.__func__, "bot_command", None)):
            continue
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


async def tail_log_events(log_file: Path, q: asyncio.Queue[LogEvent]) -> None:
    logger.info("Parsing game log file %s", log_file)
    async with aiofiles.open(log_file, encoding="utf-8") as fp:
        cur_pos = await fp.seek(0, os.SEEK_END)
        logger.info("Log file current position: %s", cur_pos)
        # signal that we are ready and wait for the event dispatcher to start
        await q.put(LogEvent(type=EventType.log_parser_ready, game_time="", data=""))
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


def parse_log_line(line: str) -> LogEvent:
    """Creates a LogEvent from a raw log entry.

    A typical log entry usually starts with the time (MMM:SS) left padded
    with spaces, the event followed by a colon and then the even data. Ex.

    >>> evt = parse_log_line("  0:28 Flag: 0 0: team_CTF_blueflag")
    >>> evt.game_time
    '0:28'
    >>> evt.type.name
    'flag'
    >>> evt.data
    '0 0: team_CTF_blueflag'

    This function main purpose is to perform a first pass parsing of the data
    in order to determine basic information about the log entry, such as
    the type of event.
    """
    game_time, _, rest = line.strip().partition(" ")
    event_name, sep, data = rest.partition(":")
    if sep:
        try:
            event_type = EventType(event_name)
        except ValueError:
            logger.warning("event type not found: [%s]-[%s]", event_name, data)
            event_type = EventType.unknown
            data = rest
        else:
            data = data.lstrip()
    elif event_name.startswith("Bombholder is "):
        event_type = EventType.bomb_holder
        data = event_name[14:]
    elif event_name.startswith("Bomb was "):
        event_type = EventType.bomb
        data = event_name[9:]
    elif event_name.startswith("Bomb has been "):
        event_type = EventType.bomb
        data = event_name[14:]
    elif event_name.startswith("Session data initialised for client on slot "):
        event_type = EventType.session_data_initialised
        data = event_name[44:]
    elif not event_name.strip("-"):
        event_type = EventType.log_separator
        data = ""
    else:
        logger.warning("event type not in log line: [%s]", line)
        event_type = EventType.unknown

    event = LogEvent(type=event_type, game_time=game_time, data=data)
    logger.debug("%r", event)
    return event


def parse_log_event(log_event: LogEvent) -> Event:
    data: dict[str, Any] = {}
    client = target = None
    match log_event.type:
        case EventType.account_validated:
            client, auth, text = log_event.data.split(" - ", maxsplit=2)
            data["text"] = text
            data["auth"] = auth
        case EventType.bomb_holder:
            client = log_event.data
        case EventType.bomb:
            parts = log_event.data.split(" ")
            data["action"] = parts[0]
            client = parts[2]
        case EventType.client_connect:
            client = log_event.data
        case EventType.client_disconnect:
            client = log_event.data
        case EventType.client_spawn:
            client = log_event.data
        case EventType.client_user_info | EventType.client_user_info_changed:
            client, _, text = log_event.data.partition(" ")
            data["text"] = text
        case EventType.flag_return:
            data["team"] = log_event.data
        case EventType.init_game:
            data["text"] = log_event.data
        case EventType.say | EventType.say_team:
            client, text = log_event.data.split(" ", maxsplit=1)
            name, text = text.split(": ", maxsplit=1)
            data["text"] = text
            data["name"] = name
        case EventType.say_tell:
            client, target, text = log_event.data.split(" ", maxsplit=2)
            name, text = text.split(": ", maxsplit=1)
            data["text"] = text
            data["name"] = name
        case EventType.session_data_initialised:
            data["text"] = log_event.data
        case EventType.unknown:
            data["text"] = log_event.data

    return Event(
        type=log_event.type,
        game_time=log_event.game_time,
        data=data or None,
        client=client,
        target=target,
    )
