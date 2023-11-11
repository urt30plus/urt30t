"""
Main entrypoint for the bot.
"""

import asyncio
import contextlib
import importlib


async def async_main() -> None:
    import urt30t.core

    await urt30t.core.Bot().run()


def main() -> None:
    try:
        uvloop = importlib.import_module("uvloop")
    except ModuleNotFoundError:
        loop_factory = None
    else:
        loop_factory = uvloop.new_event_loop

    with (
        contextlib.suppress(KeyboardInterrupt),
        asyncio.Runner(loop_factory=loop_factory) as runner,
    ):
        runner.run(async_main())


if __name__ == "__main__":
    main()
