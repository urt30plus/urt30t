"""
Main entrypoint for the bot.
"""
import asyncio
import contextlib


async def async_main() -> None:
    import urt30t

    await urt30t.Bot().run()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(async_main())
