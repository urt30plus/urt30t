import asyncio
import contextlib
import datetime
import importlib.util
import inspect
import logging
import os
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from types import FunctionType
from typing import TypeVar, cast

import aiofiles
import aiofiles.os

from . import events, rcon, settings, tasks
from .models import (
    BotCommandConfig,
    BotPlugin,
    Game,
    Group,
    Player,
)

__version__ = "30.0.0.rc1"

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

_core_plugins = [
    "urt30t.plugins.core.GameStatePlugin",
    "urt30t.plugins.core.CommandsPlugin",
]


class BotError(Exception):
    pass


class Bot:
    def __init__(self) -> None:
        self._conf = settings.bot
        self._started_at = datetime.datetime.now(tz=self._conf.time_zone)
        self._events_queue = asyncio.Queue[events.LogEvent](
            self._conf.event_queue_max_size
        )
        self._rcon: rcon.RconClient | None = None
        self._plugins: list[BotPlugin] = []
        self._event_handlers: dict[
            type[events.GameEvent], list[events.EventHandler]
        ] = defaultdict(list)
        self._command_handlers: dict[str, BotCommandConfig] = {}
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
        tasks.background(self._run_cleanup())
        tasks.background(
            _tail_log(
                log_file=self._conf.games_log,
                event_queue=self._events_queue,
                read_delay=self._conf.log_read_delay,
                check_truncated=self._conf.log_check_truncated,
            )
        )
        self._event_handlers[events.BotStartup].append(self.on_startup)  # type: ignore
        await self.sync_game()
        await self._load_plugins()
        await self._dispatch_events()

    @property
    def rcon(self) -> rcon.RconClient:
        if self._rcon is None:
            raise RuntimeError("rcon_client_not_set")
        return self._rcon

    @property
    def message_prefix(self) -> str:
        return self._conf.message_prefix

    @property
    def commands(self) -> dict[str, BotCommandConfig]:
        return self._command_handlers

    async def sync_game(self) -> None:
        old_game = self.game
        new_game = await self.rcon.players()
        self.game = Game.from_dict(new_game)
        await asyncio.gather(
            *[self.sync_player(p.slot) for p in self.game.players.values()]
        )
        logger.debug("Game state:\nbefore: %r\nafter: %r", old_game, self.game)

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

    async def on_startup(self, event: events.BotStartup) -> None:
        pass

    async def on_shutdown(self) -> None:
        await self._unload_plugins()
        self.rcon.close()
        logger.info("%s stopped", self)

    async def _dispatch_events(self) -> None:
        event_queue_get = self._events_queue.get
        event_queue_done = self._events_queue.task_done
        handlers_get = self._event_handlers.get
        while log_event := await event_queue_get():
            if handlers := handlers_get(log_event.type):
                event = log_event.game_event()
                for handler in handlers:
                    try:
                        await handler(event)
                    except Exception:
                        logger.exception("%r failed to handle %r", handler, event)
            else:
                logger.debug("no handler registered for event: %r", log_event)

            event_queue_done()

    async def _load_plugins(self) -> None:
        plugins_specs = [*_core_plugins, *self._conf.plugins]
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
            await self.on_shutdown()

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
        await event_queue.put(events.LogEvent(type=events.BotStartup))
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
                if log_event := parse_log_line(line):
                    await event_queue.put(log_event)


def parse_log_line(line: str) -> events.LogEvent | None:
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
    event_type: type[events.GameEvent] | None
    if sep:
        event_name = event_name.replace(" ", "")
        data = data.lstrip()
        if event_name == "red":
            event_type = events.TeamScores
            data = f"red:{data}"
        elif not (event_type := events.lookup_event_class(event_name)):
            logger.warning("no event class found: %s", line)
    elif event_name.startswith("Bombholder is "):
        event_type = events.BombHolder
        data = event_name[14:]
    elif event_name.startswith("Bomb was "):
        event_type = events.Bomb
        data = event_name[9:]
    elif event_name.startswith("Bomb has been "):
        event_type = events.Bomb
        data = event_name[14:]
    elif event_name == "Pop!":
        event_type = events.Pop
        data = ""
    elif event_name.startswith(("Session data", "-----")):
        event_type = None
    else:
        logger.warning("event type not in log line: [%s]", line)
        event_type = None

    if event_type is None:
        return None

    event = events.LogEvent(type=event_type, game_time=game_time, data=data)
    logger.debug(event)
    return event
