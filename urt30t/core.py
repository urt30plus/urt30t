import asyncio
import contextlib
import datetime
import importlib.util
import inspect
import logging
import os
from collections import defaultdict
from collections.abc import Awaitable, Callable, Coroutine
from pathlib import Path
from types import FunctionType
from typing import Any, NamedTuple, TypeVar, cast

import aiofiles
import aiofiles.os

from . import events, rcon, settings
from .models import (
    Game,
    Group,
    MessageType,
    Player,
)

__version__ = "30.0.0.rc1"

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

EventHandler = Callable[[events.GameEvent], Awaitable[None]]
CommandHandler = Callable[["BotCommand"], Awaitable[None]]

_event_class_by_action: dict[str, type[events.GameEvent]] = {
    name.lower(): cls
    for name, cls in inspect.getmembers(events, predicate=inspect.isclass)
    if issubclass(cls, events.GameEvent)
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


class BotCommandConfig(NamedTuple):
    handler: CommandHandler
    name: str
    level: Group = Group.USER
    alias: str | None = None


class BotCommand(NamedTuple):
    plugin: BotPlugin
    message_type: MessageType
    player: Player
    data: str | None = None

    async def message(
        self, message: str, message_type: MessageType | None = None
    ) -> None:
        prefix = self.plugin.bot.conf.message_prefix + " "
        # TODO: handle wrapping
        if message_type is None:
            message_type = self.message_type
        if message_type is MessageType.PRIVATE:
            prefix += "^8[pm]^7 "
            await self.plugin.bot.rcon.private_message(
                self.player.slot, prefix + message
            )
        elif message_type is MessageType.LOUD:
            await self.plugin.bot.rcon.message(prefix + message)
        else:
            await self.plugin.bot.rcon.bigtext(prefix + message)


class Bot:
    def __init__(self) -> None:
        self.conf = settings.bot
        self._started_at = datetime.datetime.now(tz=self.conf.time_zone)
        self._events_queue = asyncio.Queue[events.LogEvent](
            self.conf.event_queue_max_size
        )
        self._rcon: rcon.RconClient | None = None
        self._plugins: list[BotPlugin] = []
        self._event_handlers: dict[
            type[events.GameEvent], list[EventHandler]
        ] = defaultdict(list)
        self._command_handlers: dict[str, BotCommandConfig] = {}
        self._tasks: set[asyncio.Task[Any]] = set()
        self.game = Game()

    async def run(self) -> None:
        logger.info("%s running", self)
        self._rcon = await rcon.create_client(
            host=settings.rcon.host,
            port=settings.rcon.port,
            password=settings.rcon.password,
            recv_timeout=settings.rcon.recv_timeout,
        )
        logger.info(self._rcon)
        self.background_task(self._run_cleanup())
        self.background_task(
            _tail_log(
                log_file=self.conf.games_log,
                event_queue=self._events_queue,
                read_delay=self.conf.log_read_delay,
                check_truncated=self.conf.log_check_truncated,
            )
        )

        await self.sync_game()
        await self._load_plugins()
        await self._dispatch_events()

    @property
    def rcon(self) -> rcon.RconClient:
        if self._rcon is None:
            raise RuntimeError("rcon_client_not_set")
        return self._rcon

    def background_task(self, coro: Coroutine[Any, None, Any]) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @property
    def commands(self) -> dict[str, BotCommandConfig]:
        return self._command_handlers

    async def sync_game(self) -> None:
        old_game = self.game
        self.game = new_game = await self.rcon.players()
        await asyncio.gather(
            *[self.sync_player(p.slot) for p in new_game.players.values()]
        )
        logger.debug("Game state:\nbefore: %r\nafter: %r", old_game, new_game)

    async def sync_player(self, slot: str) -> Player:
        if not (player := self.find_player(slot)):
            raise RuntimeError(slot)
        # TODO: load/save info from/to db
        # TODO: check for bans
        if player.group is Group.UNKNOWN:
            player.group = Group.GUEST
        return player

    def find_player(self, slot: str) -> Player | None:
        return self.game.players.get(slot)

    async def connect_player(self, player: Player) -> None:
        self.game.players[player.slot] = player

    async def disconnect_player(self, slot: str) -> None:
        with contextlib.suppress(KeyError):
            del self.game.players[slot]
        # TODO: db updates?

    async def _dispatch_events(self) -> None:
        event_queue_get = self._events_queue.get
        event_queue_done = self._events_queue.task_done
        handlers_get = self._event_handlers.get
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

    async def _load_plugins(self) -> None:
        plugins_specs = [*_core_plugins, *self.conf.plugins]
        logger.info("attempting to load plugin classes: %s", plugins_specs)
        plugin_classes: list[type[BotPlugin]] = []
        for spec in plugins_specs:
            mod_path, class_name = spec.rsplit(".", maxsplit=1)
            mod = importlib.import_module(mod_path)
            plugin_class = getattr(mod, class_name)
            if not issubclass(plugin_class, BotPlugin):
                logger.error("%s is not a BotPlugin subclass", plugin_class)
            else:
                plugin_classes.append(plugin_class)

        # TODO: sort plugins based on dependencies

        for cls in plugin_classes:
            obj = cls(bot=self)
            self._register_plugin(obj)
            self._plugins.append(obj)

        for p in self._plugins:
            await p.plugin_load()

    def _register_plugin(self, plugin: BotPlugin) -> None:
        for _, meth in inspect.getmembers(
            plugin, predicate=inspect.iscoroutinefunction
        ):
            if subscription := getattr(meth.__func__, "bot_subscription", None):
                self._event_handlers[subscription].append(meth)
                logger.info("added subscription %s - %s", subscription, meth)

            if cmd_config := getattr(meth.__func__, "bot_command_config", None):
                resolved = cmd_config._replace(handler=meth)
                self._command_handlers[resolved.name] = resolved
                logger.info("added %r", resolved)

    async def _unload_plugins(self) -> None:
        await asyncio.wait(
            [asyncio.create_task(p.plugin_unload()) for p in self._plugins], timeout=5.0
        )

    async def _run_cleanup(self) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        try:
            await fut
        except asyncio.CancelledError:
            logger.info("triggered")
            raise
        finally:
            await self._unload_plugins()
            self.rcon.close()
            logger.info("%s stopped", self)

    def __repr__(self) -> str:
        return f"Bot(v{__version__}, started={self._started_at})"


def bot_command(
    level: Group = Group.USER, alias: str | None = None
) -> Callable[[_T], _T]:
    def inner(f: _T) -> _T:
        name = f.__name__.removeprefix("cmd_")  # type: ignore[attr-defined]
        f.bot_command_config = BotCommandConfig(  # type: ignore[attr-defined]
            handler=None,  # type: ignore
            name=name.lower(),
            level=level,
            alias=alias,
        )
        return f

    return inner


def bot_subscribe(f: _T) -> _T:
    func: FunctionType = cast(FunctionType, f)
    if len(func.__annotations__) == 2 and func.__annotations__["return"] is None:
        for var_name, var_type in func.__annotations__.items():
            if var_name == "return":
                continue
            if issubclass(var_type, events.GameEvent):
                f.bot_subscription = var_type  # type: ignore[attr-defined]
                return f

    raise TypeError


async def _tail_log(
    log_file: Path,
    *,
    event_queue: asyncio.Queue[events.LogEvent],
    read_delay: float,
    check_truncated: bool,
) -> None:
    logger.info("Parsing game log file %s", log_file)
    async with aiofiles.open(log_file, encoding="utf-8") as fp:
        cur_pos = await fp.seek(0, os.SEEK_END)
        logger.info(
            "read delay [%s], check truncated [%s], current pos [%s]",
            read_delay,
            check_truncated,
            cur_pos,
        )
        # signal that we are ready and wait for the event dispatcher to start
        await event_queue.put(events.LogEvent())
        await event_queue.join()
        while await asyncio.sleep(read_delay, result=True):
            if not (lines := await fp.readlines()):
                if not check_truncated:
                    continue

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
                await event_queue.put(parse_log_line(line))


def parse_log_line(line: str) -> events.LogEvent:
    """Creates a LogEvent from a raw log entry.

    A typical log entry usually starts with the time (MMM:SS) left padded
    with spaces, the event followed by a colon and then the even data. Ex.

    This function main purpose is to perform a first pass parsing of the data
    in order to determine basic information about the log entry, such as
    the type of event.
    """
    game_time = line[:7].strip()
    rest = line[7:].strip()
    event_name, sep, data = rest.partition(":")
    if sep:
        event_type = event_name.lower().replace(" ", "")
        data = data.lstrip()
        if event_name == "red":
            event_type = "teamscores"
            data = f"red:{data}"
    elif event_name.startswith("Bombholder is "):
        event_type = "bombholder"
        data = event_name[14:]
    elif event_name.startswith("Bomb was "):
        event_type = "bomb"
        data = event_name[9:]
    elif event_name.startswith("Bomb has been "):
        event_type = "bomb"
        data = event_name[14:]
    elif event_name == "Pop!":
        event_type = "pop"
        data = ""
    elif event_name.startswith("Session data"):
        event_type = None
        data = event_name
    elif event_name.startswith("-----"):
        event_type = None
        data = ""
    else:
        logger.warning("event type not in log line: [%s]", line)
        event_type = None
        data = event_name

    event = events.LogEvent(type=event_type, game_time=game_time, data=data)
    logger.debug(event)
    return event
