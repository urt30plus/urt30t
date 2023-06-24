"""
Main entrypoint for the bot.
"""
import asyncio
import contextlib
import importlib


async def async_main() -> None:
    import urt30t.core

    await urt30t.core.Bot().run()


if __name__ == "__main__":
    try:
        uvloop = importlib.import_module("uvloop")
    except ModuleNotFoundError:
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(async_main())
    else:
        with (
            contextlib.suppress(KeyboardInterrupt),
            asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner,
        ):
            runner.run(async_main())
