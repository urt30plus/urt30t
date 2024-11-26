import asyncio
import contextlib
import datetime
import importlib.util
import inspect
import logging
import os
import sys
from collections import defaultdict
from collections.abc import Callable, Coroutine
from pathlib import Path
from types import FunctionType
from typing import Any, TypeVar, cast

import aiofiles
import aiofiles.os
from urt30arcon import AsyncRconClient

from . import (
    db,
    discord30,
    events,
    settings,
)
from .models import (
    BotCommand,
    BotCommandConfig,
    BotError,
    BotPlugin,
    Game,
    Group,
    Player,
    Server,
    default_command_handler,
)

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class Bot:
    def __init__(self) -> None:
        self._conf = settings.bot
        self._started_at = datetime.datetime.now(tz=self._conf.time_zone)
        self._events_queue = asyncio.Queue[events.LogEvent](
            self._conf.event_queue_max_size
        )
        self._rcon: AsyncRconClient | None = None
        self._discord: discord30.DiscordClient | None = None
        self._plugins: list[BotPlugin] = []
        self._event_handlers: dict[
            type[events.GameEvent], list[events.EventHandler]
        ] = defaultdict(list)
        self._command_handlers: dict[str, BotCommandConfig] = {}
        self.game = Game()
        self.server = Server()
        self._tasks: set[asyncio.Task[None]] = set()

    async def run(self) -> None:
        logger.info("%s running", self)
        logger.info("Python %s", sys.version)
        self._run_background_task(self._run_cleanup())

        if settings.features.log_parsing:
            if not (games_log := settings.bot.games_log):
                raise BotError("games_log")
            self._run_background_task(
                _tail_log(
                    log_file=games_log,
                    event_queue=self._events_queue,
                    read_delay=self._conf.log_read_delay,
                    check_truncated=self._conf.log_check_truncated,
                )
            )
        else:
            logger.warning("Log Parsing is not enabled")

        if settings.features.event_dispatch:
            await self._load_plugins()
            self._event_handlers[events.BotStartup].append(
                self.on_startup  # type: ignore
            )
            await self._dispatch_events()
        else:
            logger.warning("Event Dispatch is not enabled")
            if settings.features.log_parsing:
                event = await self._events_queue.get()
                self._events_queue.task_done()
            else:
                event = events.LogEvent(type=events.BotStartup)

            await self.on_startup(events.BotStartup.from_log_event(event))
            while await self._events_queue.get():
                pass

    @property
    def rcon(self) -> AsyncRconClient:
        if self._rcon is None:
            msg = "Rcon Client is not initialized"
            raise BotError(msg)
        return self._rcon

    @property
    def command_prefix(self) -> str:
        return self._conf.command_prefix

    @property
    def message_prefix(self) -> str:
        return self._conf.message_prefix

    @property
    def commands(self) -> dict[str, BotCommandConfig]:
        return self._command_handlers

    async def sync_game(self) -> None:
        old_game = self.game
        for _ in range(5):
            try:
                rcon_game = await self.rcon.game_info()
                break
            except LookupError:
                await asyncio.sleep(1.5)
        else:
            return
        new_players = {
            p.slot: Player(
                slot=p.slot,
                name=p.clean_name,
                name_exact=p.name,
                auth=p.auth,
                guid=p.guid,
                team=p.team,
                # don't carry over kda, we'll track ourselves
                ip_address=p.ip_address,
            )
            for p in rcon_game.players
        }
        self.game = new_game = Game(
            map_name=rcon_game.map_name,
            type=rcon_game.type,
            warmup=rcon_game.warmup,
            match_mode=rcon_game.match_mode,
            score_red=rcon_game.score_red,
            score_blue=rcon_game.score_blue,
            players=new_players,
        )
        await asyncio.gather(*[self.sync_player(slot) for slot in new_game.players])
        logger.debug("Game state:\nbefore: %r\nafter: %r", old_game, self.game)

    async def sync_player(self, slot: str) -> Player:
        if not (player := self.player(slot)):
            raise BotError("invalid_slot", slot)

        if not (player.guid and player.auth):
            if userinfo := await self.rcon.dumpuser(slot):
                player.guid = userinfo["cl_guid"]
                player.auth = userinfo["authl"]
            else:
                logger.error("dumpuser failed for slot [%s]", slot)

        if settings.features.log_parsing and not player.db_id:
            await db.sync_player(player)
            # TODO: check for bans

        logger.info("%r", player)
        return player

    def player(self, slot: str) -> Player | None:
        return self.game.players.get(slot)

    def find_player(self, s: str, /) -> list[Player]:
        if len(s) <= 3 and s.isdigit():  # noqa: PLR2004
            p = self.player(s)
            return [p] if p else []
        needle = s.lower()
        return [
            p
            for p in self.game.players.values()
            if needle in p.name or needle == p.auth
        ]

    async def search_players(self, s: str, /) -> list[Player]:
        if not (s.startswith("@") and s[1:].isdigit()):
            return self.find_player(s)
        db_id = s[1:]
        logger.info("looking up player_db_id: %s", db_id)
        # TODO: lookup player in the database
        return []

    async def connect_player(self, player: Player) -> None:
        self.game.players[player.slot] = player

    async def disconnect_player(self, slot: str) -> None:
        with contextlib.suppress(KeyError):
            del self.game.players[slot]
        # TODO: db updates?

    async def on_startup(self, event: events.BotStartup) -> None:
        logger.debug(event)
        if settings.features.command_dispatch or settings.features.discord_updates:
            self._rcon = await AsyncRconClient.create_client(
                host=settings.rcon.host,
                port=settings.rcon.port,
                password=settings.rcon.password.get_secret_value(),
                recv_timeout=settings.rcon.recv_timeout,
            )
            logger.info(self._rcon)
            await self.sync_game()

        if settings.features.discord_updates:
            if not (discord_conf := settings.discord):
                raise BotError("discord_settings")
            self._discord = discord30.DiscordClient(
                bot_user=discord_conf.user,
                server_name=discord_conf.server_name,
            )
            await self._discord.login(discord_conf.token.get_secret_value())
            self._run_background_task(
                self._discord_update_mapcycle(self._discord, discord_conf)
            )
            self._run_background_task(
                self._discord_update_gameinfo(self._discord, discord_conf)
            )
        else:
            logger.warning("Discord Updates are not enabled")

    async def on_shutdown(self) -> None:
        await self._unload_plugins()
        if self._rcon:
            self._rcon.close()
        if self._discord:
            await self._discord.close()
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
                logger.warning("no handler registered for event: %r", log_event)

            event_queue_done()

    async def _load_plugins(self) -> None:
        core_plugins = ["urt30t.plugins.gamestate.Plugin"]
        if settings.features.command_dispatch:
            core_plugins.append("urt30t.plugins.commands.Plugin")
        else:
            logger.warning("Command Dispatch is not enabled")
        plugins_specs = [*core_plugins, *self._conf.plugins]
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
        for p in self._plugins:
            try:
                await p.plugin_unload()
            except Exception:
                logger.exception("Plugin %s failed to unload", p)

    async def _run_cleanup(self) -> None:
        fut: asyncio.Future[None] = asyncio.Future()
        try:
            await fut
        except asyncio.CancelledError:
            logger.info("Shutdown cleanup has been triggered")
            raise
        finally:
            await self.on_shutdown()

    async def _discord_update_gameinfo(
        self, api_client: discord30.DiscordClient, config: settings.DiscordSettings
    ) -> None:
        if not config.gameinfo_updates_enabled:
            logger.warning("Discord GameInfo Updates are not enabled")
            return
        channel_name = config.updates_channel_name
        embed_title = config.gameinfo_embed_title
        delay = config.gameinfo_update_delay
        delay_no_updates = config.gameinfo_update_delay_no_updates
        timeout = config.gameinfo_update_timeout
        updater = discord30.GameInfoUpdater(
            api_client=api_client,
            rcon_client=self.rcon,
            channel_name=channel_name,
            embed_title=embed_title,
            game_host=self._conf.game_host,
        )
        logger.info(
            "%r - delay=[%s], delay_no_updates=[%s], timeout=[%s]",
            updater,
            delay,
            delay_no_updates,
            timeout,
        )
        # delay on first start to allow mapcycle time to complete first
        await asyncio.sleep(15.0)
        while True:
            try:
                was_updated = await updater.update()
            except Exception:
                logger.exception("GameInfo update failed")
                was_updated = True  # use the shorter delay to retry

            await asyncio.sleep(delay if was_updated else delay_no_updates)

    async def _discord_update_mapcycle(
        self, api_client: discord30.DiscordClient, config: settings.DiscordSettings
    ) -> None:
        if not config.mapcycle_updates_enabled:
            logger.warning("Discord Mapcycle Updates are not enabled")
            return
        if not (mapcycle_file := config.mapcycle_file):
            mapcycle_file = await self.rcon.mapcycle_file()
        if not mapcycle_file or not mapcycle_file.exists():
            logger.warning(
                "Discord Mapcycle Updates disabled, mapcycle file does not exist: %s",
                mapcycle_file,
            )
            return
        channel_name = config.updates_channel_name
        embed_title = config.mapcycle_embed_title
        delay = config.mapcycle_update_delay
        timeout = config.mapcycle_update_timeout
        updater = discord30.MapCycleUpdater(
            api_client=api_client,
            rcon_client=self.rcon,
            channel_name=channel_name,
            embed_title=embed_title,
            mapcycle_file=mapcycle_file,
        )
        logger.info(
            "%r - delay=[%s], timeout=[%s], file=[%s]",
            updater,
            delay,
            timeout,
            mapcycle_file,
        )
        while True:
            try:
                await updater.update()
            except Exception:
                logger.exception("Mapcycle update failed")
            await asyncio.sleep(delay)

    def _run_background_task(self, coro: Coroutine[Any, None, Any]) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def __repr__(self) -> str:
        return f"Bot(v{settings.__version__}, started={self._started_at})"


def bot_command(
    level: Group = Group.USER, alias: str | None = None
) -> Callable[[_T], _T]:
    def inner(f: _T) -> _T:
        name = f.__name__.removeprefix("cmd_")  # type: ignore[attr-defined]
        sig = inspect.signature(f)  # type: ignore[arg-type]
        handler_name = f"{f.__module__}.{f.__qualname__}"  # type: ignore[attr-defined]
        if len(sig.parameters) < 2:  # noqa: PLR2004
            msg = (
                f"Command handler [{handler_name}] must have at"
                " least one parameter. Typically this is named `cmd` and "
                " annotated as `BotCommand`. For example:\n"
                "\tdef cmd_foobar(self, cmd: BotCommand) -> None:"
            )
            raise TypeError(msg)
        args_req = args_opt = 0
        for i, p in enumerate(sig.parameters.values()):
            if i == 0:
                continue
            if i == 1:
                if isinstance(p.annotation, type) and not issubclass(
                    p.annotation, BotCommand
                ):
                    msg = (
                        f"Command handler [{handler_name}] parameter"
                        f" is not the correct type. Expected {BotCommand},"
                        f" got {p.annotation}."
                    )
                    raise TypeError(msg)
                continue
            if p.kind not in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY):
                msg = (
                    f"Command handler [{handler_name}],"
                    " *args, **kwargs and keyword only parameters are not supported."
                    f" got {p.kind}."
                )
                raise TypeError(msg)
            if p.annotation and not issubclass(str, p.annotation):
                msg = (
                    f"Command handler [{handler_name}] additional"
                    f"parameters must be of type `str`, got {p.annotation}."
                )
                raise TypeError(msg)
            if p.default is p.empty:
                args_req += 1
            else:
                args_opt += 1
        f.bot_command_config = BotCommandConfig(  # type: ignore[attr-defined]
            handler=default_command_handler,
            name=name.lower(),
            level=level,
            alias=alias,
            args_required=args_req,
            args_optional=args_opt,
        )
        return f

    return inner


def bot_subscribe(f: _T) -> _T:
    func: FunctionType = cast(FunctionType, f)
    if (
        len(func.__annotations__) == 2  # noqa: PLR2004
        and func.__annotations__["return"] is None
    ):
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
    if check_truncated and settings.bot.log_replay_from_start:
        check_truncated = False
    async with aiofiles.open(log_file, encoding="utf-8") as fp:
        if settings.bot.log_replay_from_start:
            cur_pos = await fp.tell()
        else:
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
