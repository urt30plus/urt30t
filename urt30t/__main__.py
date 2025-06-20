"""
Main entrypoint for the bot.
"""

import asyncio
import contextlib
import importlib


async def start_bot() -> None:
    # defer import until there is a running event loop
    import urt30t.core  # noqa: PLC0415

    await urt30t.core.Bot().run()


try:
    uvloop = importlib.import_module("uvloop")
except ModuleNotFoundError:
    aio_run = asyncio.run
else:
    aio_run = uvloop.run

with contextlib.suppress(KeyboardInterrupt):
    aio_run(start_bot())
