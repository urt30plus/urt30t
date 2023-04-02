"""
Main entrypoint for the bot.
"""
import asyncio

import urt30t.bot


async def async_main() -> None:
    await urt30t.bot.run()


if __name__ == "__main__":
    asyncio.run(async_main())
