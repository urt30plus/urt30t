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
from typing import Any, TypeVar, cast

import aiofiles
import aiofiles.os
import discord

from . import events, rcon, settings, tasks, version
from .discord30 import gameinfo, mapcycle
from .models import (
    BotCommandConfig,
    BotError,
    BotPlugin,
    Game,
    Group,
    Player,
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
        self._rcon: rcon.RconClient | None = None
        self._discord: DiscordClient | None = None
        self._plugins: list[BotPlugin] = []
        self._event_handlers: dict[
            type[events.GameEvent], list[events.EventHandler]
        ] = defaultdict(list)
        self._command_handlers: dict[str, BotCommandConfig] = {}
        self.game = Game()

    async def run(self) -> None:
        logger.info("%s running", self)
        tasks.background(self._run_cleanup())

        if settings.features.log_parsing:
            tasks.background(
                _tail_log(
                    log_file=self._conf.games_log,
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
    def rcon(self) -> rcon.RconClient:
        if self._rcon is None:
            msg = "Rcon Client is not initialized"
            raise BotError(msg)
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
        if not (player := self.player(slot)):
            raise RuntimeError(slot)
        # TODO: load/save info from/to db
        # TODO: check for bans
        if player.group is Group.UNKNOWN:
            player.group = Group.GUEST
        return player

    def player(self, slot: str) -> Player | None:
        return self.game.players.get(slot)

    def find_player(self, s: str, /) -> list[Player]:
        if len(s) <= 3 and s.isdigit():
            p = self.player(s)
            return [p] if p else []
        needle = s.lower()
        return [
            p
            for p in self.game.players.values()
            if needle in p.clean_name or needle == p.auth
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
            self._rcon = await rcon.create_client(
                host=settings.rcon.host,
                port=settings.rcon.port,
                password=settings.rcon.password,
                recv_timeout=settings.rcon.recv_timeout,
            )
            logger.info(self._rcon)
            await self.sync_game()

        if settings.features.discord_updates and self._conf.discord:
            self._discord = DiscordClient(
                bot_user=self._conf.discord.user,
                server_name=self._conf.discord.server_name,
            )
            await self._discord.login(self._conf.discord.token)
            tasks.background(self._discord_update_gameinfo())
            tasks.background(self._discord_update_mapcycle())
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

    async def _discord_update_gameinfo(self) -> None:
        if not self._conf.discord.gameinfo_updates_enabled:
            logger.warning("Discord GameInfo Updates are not enabled")
            return
        channel_name = self._conf.discord.updates_channel_name
        embed_title = self._conf.discord.gameinfo_embed_title
        delay_updates = self._conf.discord.gameinfo_update_delay_players
        delay_no_updates = self._conf.discord.gameinfo_update_delay
        timeout = self._conf.discord.gameinfo_update_timeout
        logger.info("Starting Discord GameInfo Updater")
        logger.info(
            "Channel Name [%s], Embed Title [%s], delay_no_players=[%s], "
            "delay_players=[%s], timeout=[%s]",
            channel_name,
            embed_title,
            delay_no_updates,
            delay_updates,
            timeout,
        )
        updater = DiscordEmbedUpdater(
            client=self._discord, channel_name=channel_name, embed_title=embed_title
        )
        while True:
            game = await self._rcon.players()
            if await gameinfo.update(updater, Game.from_dict(game)):
                await asyncio.sleep(delay_updates)
            else:
                await asyncio.sleep(delay_no_updates)

    async def _discord_update_mapcycle(self) -> None:
        if not self._conf.discord.mapcycle_updates_enabled:
            logger.warning("Discord Mapcycle Updates are not enabled")
            return
        if not (mapcycle_file := self._conf.discord.mapcycle_file):
            mapcycle_file = await self._rcon.mapcycle_file()
        if not mapcycle_file.exists():
            logger.warning(
                "Discord Mapcycle Updates disabled, mapcycle file does not exist: %s",
                mapcycle_file,
            )
            return
        channel_name = self._conf.discord.updates_channel_name
        embed_title = self._conf.discord.mapcycle_embed_title
        delay = self._conf.discord.mapcycle_update_delay
        timeout = self._conf.discord.mapcycle_update_timeout
        logger.info("Starting Discord Mapcycle Updater")
        logger.info(
            "Channel Name [%s], Embed Title [%s], delay=[%s], timeout=[%s], file=[%s]",
            channel_name,
            embed_title,
            delay,
            timeout,
            mapcycle_file,
        )
        updater = DiscordEmbedUpdater(
            client=self._discord, channel_name=channel_name, embed_title=embed_title
        )
        while True:
            await mapcycle.update(updater, mapcycle_file)
            await asyncio.sleep(delay)

    def __repr__(self) -> str:
        return f"Bot(v{version.__version__}, started={self._started_at})"


class DiscordClient(discord.Client):
    def __init__(
        self,
        bot_user: str,
        server_name: str,
        **kwargs: Any,
    ) -> None:
        if "intents" not in kwargs:
            kwargs["intents"] = discord.Intents.all()
        super().__init__(**kwargs)
        self.bot_user = bot_user
        self.server_name = server_name
        self._guild: discord.Guild | None = None

    async def login(self, token: str) -> None:
        await super().login(token)
        async for guild in super().fetch_guilds():
            if guild.name == self.server_name:
                self._guild = guild
                break
        else:
            msg = f"Discord Server not found: {self.server_name}"
            raise BotError(msg)

    async def _channel_by_name(self, name: str) -> discord.TextChannel:
        logger.info("Looking for channel named [%s]", name)
        if self._guild is None:
            msg = f"Discord Guild not found: {name}"
            raise BotError(msg)
        channels = await self._guild.fetch_channels()
        for ch in channels:
            if ch.name == name:
                logger.info("Found channel: %s [%s]", ch.name, ch.id)
                if isinstance(ch, discord.TextChannel):
                    return ch
                msg = f"Discord Invalid Channel Type: {ch}"
                raise BotError(msg)

        msg = f"Discord Channel Not Found: {name}"
        raise BotError(msg)

    async def _last_messages(
        self,
        channel: discord.TextChannel,
        limit: int = 1,
    ) -> list[discord.Message]:
        messages = []
        logger.info(
            "Fetching last %s messages if posted by %r in channel %s",
            limit,
            self.bot_user,
            channel.name,
        )
        async for msg in channel.history(limit=limit):
            author = msg.author
            author_user = f"{author.name}#{author.discriminator}"
            if author.bot and author_user == self.bot_user:
                messages.append(msg)
        logger.info("Found [%s] messages", len(messages))
        return messages

    async def _find_message_by_embed_title(
        self,
        channel: discord.TextChannel,
        embed_title: str,
        limit: int = 5,
    ) -> discord.Message | None:
        messages = await self._last_messages(channel, limit=limit)
        logger.info("Looking for message with the %r embed title", embed_title)
        for msg in messages:
            for embed in msg.embeds:
                if embed.title == embed_title:
                    return msg
        return None

    async def fetch_embed_message(
        self,
        channel_name: str,
        embed_title: str,
        limit: int = 5,
    ) -> tuple[discord.TextChannel, discord.Message | None]:
        channel = await self._channel_by_name(channel_name)
        message = await self._find_message_by_embed_title(
            channel=channel,
            embed_title=embed_title,
            limit=limit,
        )
        return channel, message

    def __str__(self) -> str:
        return f"DiscordClient(bot_user={self.bot_user!r}, server={self.server_name!r})"


class DiscordEmbedUpdater:
    def __init__(
        self, client: DiscordClient, channel_name: str, embed_title: str
    ) -> None:
        self.client = client
        self.channel_name = channel_name
        self.embed_title = embed_title
        self._channel: discord.TextChannel | None = None

    async def fetch_embed_message(self) -> discord.Message | None:
        channel, message = await self.client.fetch_embed_message(
            self.channel_name, self.embed_title, limit=20
        )
        self._channel = channel
        return message

    async def new_message(self, embed: discord.Embed) -> discord.Message:
        if self._channel is None:
            msg = f"Discord Channel has not be fetched for: {self.channel_name}"
            raise BotError(msg)
        return await self._channel.send(embed=embed)

    def __repr__(self) -> str:
        return (
            f"DiscordEmbedUpdater(channel_name={self.channel_name!r}, "
            f"embed_title={self.embed_title!r})"
        )


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
