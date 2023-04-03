"""
Main entrypoint for the bot.
"""
import asyncio
import contextlib

import urt30t.bot


async def async_main() -> None:
    await urt30t.bot.Bot().run()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(async_main())
