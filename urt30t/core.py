import asyncio
import contextlib
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
    Server,
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
            commands=_command_handlers,
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
