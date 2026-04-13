import asyncio
import contextlib
import difflib
import importlib.util
import inspect
import logging
import sys
from collections import defaultdict
from typing import TYPE_CHECKING

from urt30arcon import AsyncRconClient

from . import (
    events,
    settings,
)
from .models import (
    BotCommand,
    BotCommandConfig,
    BotContext,
    Game,
    Group,
    MessageType,
    PlayerNotFoundError,
    Server,
    TooManyPlayersFoundError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable
    from types import ModuleType

    from .events import EventHandler

logger = logging.getLogger(__name__)

_event_queue = asyncio.Queue[events.LogEntry](settings.bot.event_queue_max_size)
_event_handlers: dict[type[events.Event], list[events.EventHandler]] = defaultdict(list)
_handler_modules: list[ModuleType] = []
_command_handlers: dict[str, BotCommandConfig] = {}
_commands_by_group: dict[str, Group] = {}


async def run() -> None:
    logger.info("%s running (Python %s)", settings.__version__, sys.version)
    load_handler_modules()
    async with create_context() as ctx:
        ctx.task_group.create_task(
            events.tail_log(
                log_file=settings.bot.games_log,
                event_queue=_event_queue,
                read_delay=settings.bot.log_read_delay,
            )
        )
        ctx.task_group.create_task(dispatch_events(ctx))


@contextlib.asynccontextmanager
async def create_context() -> AsyncGenerator[BotContext]:
    async with (
        asyncio.TaskGroup() as tg,
        AsyncRconClient(
            host=settings.rcon.host,
            port=settings.rcon.port,
            password=settings.rcon.password,
            recv_timeout=settings.rcon.recv_timeout,
        ) as rcon,
    ):
        yield BotContext(
            game=Game(),
            server=Server(),
            rcon=rcon,
            task_group=tg,
        )


async def dispatch_events(ctx: BotContext) -> None:
    while log_entry := await _event_queue.get():
        if handlers := _event_handlers.get(log_entry.kind):
            event = log_entry.parse_event()
            for handler in handlers:
                try:
                    await handler(ctx, event)
                except Exception:
                    logger.exception("%r failed to handle %r", handler, event)
        else:
            logger.warning("no handler registered for event: %r", log_entry)

        _event_queue.task_done()


def load_handler_modules() -> None:
    core_modules = [
        "urt30t.handlers.gamestate",
        "urt30t.handlers.commands",
    ]
    mod_specs = [*core_modules, *settings.bot.modules]
    logger.info("attempting to load plugin modules: %s", mod_specs)
    for spec in mod_specs:
        mod = importlib.import_module(spec)
        _handler_modules.append(mod)


def bot_command[T](
    level: Group = Group.USER, alias: str | None = None
) -> Callable[[T], T]:
    def inner(f: T) -> T:
        if not inspect.iscoroutinefunction(f):
            msg = "Command handler function must be async"
            raise TypeError(msg)

        sig = inspect.signature(f)

        handler_name = f"{f.__module__}.{f.__qualname__}"  # ty: ignore[unresolved-attribute]
        if len(sig.parameters) == 0:
            msg = (
                f"Command handler [{handler_name}] must have at"
                " least one parameter. Typically this is named `cmd` and "
                " annotated as `BotCommand`. For example:\n"
                "\tasync def cmd_foobar(self, cmd: BotCommand) -> None:"
            )
            raise TypeError(msg)

        args_req = args_opt = 0
        for i, p in enumerate(sig.parameters.values()):
            if i == 0:
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
            if p.kind not in {p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY}:
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

        name = f.__name__.removeprefix("cmd_").lower()  # ty: ignore[unresolved-attribute]
        _command_handlers[name] = BotCommandConfig(
            handler=f,
            name=name,
            level=level,
            alias=alias,
            args_required=args_req,
            args_optional=args_opt,
        )
        return f  # ty: ignore[invalid-return-type]

    return inner


def bot_subscribe(f: EventHandler) -> EventHandler:
    if not inspect.iscoroutinefunction(f):
        msg = "Handler function must be async"
        raise TypeError(msg)
    sig = inspect.signature(f)
    if len(sig.parameters) != 2:  # noqa: PLR2004
        msg = "Handler must accept 2 parameters - context and event."
        raise TypeError(msg)
    event_param = list(sig.parameters.values())[2 - 1]
    if not issubclass(event_param.annotation, events.Event):
        msg = "Handler must accept an Event type as the second parameter."
        raise TypeError(msg)
    _event_handlers[event_param.annotation].append(f)
    return f


@bot_subscribe
async def on_say(ctx: BotContext, event: events.Say) -> None:
    if not event.text.startswith(settings.bot.command_prefix):
        return
    logger.info(event)
    if not (player := ctx.game.players.get(event.slot)):
        logger.warning("no player found at: %s", event.slot)
        return
    cmd_and_data = event.text.lstrip(settings.bot.command_prefix)
    prefix_count = len(event.text) - len(cmd_and_data)
    if prefix_count not in MessageType:
        logger.warning("too many command prefixes, ignoring: %s", event.text)
        return
    message_type = MessageType(prefix_count)
    name, _, data = cmd_and_data.partition(" ")
    cmd_args = [x.strip() for x in data.split()]
    cmd = BotCommand(
        context=ctx,
        name=name,
        message_type=message_type,
        player=player,
        args=cmd_args,
    )
    if cmd_config := _find_command_config(name):
        # TODO: check player has access to this command via group
        if cmd_config.max_args == 0:
            cmd_args = []
        elif not cmd_config.min_args <= len(cmd_args) <= cmd_config.max_args:
            msg = (
                f"invalid arguments, expected between {cmd_config.min_args} "
                f"and {cmd_config.max_args} but got {len(cmd_args)}"
            )
            logger.error(msg)
            msg += f" see !help {name}"
            await cmd.message(msg, MessageType.PRIVATE)
            return
        try:
            await cmd_config.handler(cmd, *cmd_args)
        except PlayerNotFoundError as exc:
            await cmd.message(f"Player not found: {exc}", MessageType.PRIVATE)
        except TooManyPlayersFoundError as exc:
            choices = ", ".join(f"{p.name}" for p in exc.players)
            await cmd.message(f"Which player? {choices}", MessageType.PRIVATE)
    else:
        logger.warning("no command config found: %s", event)
        if candidates := _find_command_sounds_like(name, cmd.player.group):
            msg = f"did you mean? {', '.join(candidates)}"
        else:
            msg = f"command [{name}] not found"
        await cmd.message(msg, MessageType.PRIVATE)


@bot_subscribe
async def on_say_team(ctx: BotContext, event: events.SayTeam) -> None:
    await on_say(ctx, event)


@bot_subscribe
async def on_say_tell(ctx: BotContext, event: events.SayTell) -> None:
    if event.slot == event.target:
        await on_say(ctx, event)


@bot_command(level=Group.GUEST)
async def cmd_help(cmd: BotCommand, name: str | None = None) -> None:
    """Provides a list of commands available."""
    if name:
        if cmd_config := _find_command_config(name):
            # TODO: verify player has access to command via group
            if doc_string := cmd_config.handler.__doc__:
                clean_doc = " ".join(x.strip() for x in doc_string.splitlines())
                message = f'"{clean_doc}"'
            else:
                message = "no help found for this command"
        else:
            message = f"command [{name}] not found"
    else:
        # TODO: get list of commands available to the player that issued command
        #   or make sure the user has access to the target command
        message = f"there are {len(_command_handlers)} commands total"

    await cmd.message(message)


def _find_command_config(cmd_name: str) -> BotCommandConfig | None:
    if not (cmd_config := _command_handlers.get(cmd_name)):
        for c in _command_handlers.values():
            if c.alias == cmd_name:
                cmd_config = c
                break
    return cmd_config


def _find_command_sounds_like(cmd_name: str, group: Group) -> set[str]:
    if len(cmd_name) <= 1:
        return set()

    result = {
        name
        for name, level in _commands_by_group.items()
        if cmd_name in name and level <= group
    }

    # catch misspellings
    if more := difflib.get_close_matches(cmd_name, _commands_by_group):
        result.update(x for x in more if _commands_by_group[str(x)] <= group)

    return result
