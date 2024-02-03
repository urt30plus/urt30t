"""
Main entrypoint for the bot.
"""

import asyncio
import contextlib
import importlib


async def start_bot() -> None:
    # defer import until there is a running event loop
    import urt30t.core

    await urt30t.core.Bot().run()


try:
    uvloop = importlib.import_module("uvloop")
    aio_run = uvloop.run
except ModuleNotFoundError:
    aio_run = asyncio.run

with contextlib.suppress(KeyboardInterrupt):
    aio_run(start_bot())
