import asyncio
import logging
import os
from pathlib import Path

import aiofiles
import aiofiles.os

from . import events

logger = logging.getLogger(__name__)


async def parse_log_events(log_file: Path) -> None:
    logger.info("Parsing game log file %s", log_file)
    async with aiofiles.open(log_file, encoding="utf-8") as fp:
        await fp.seek(0, os.SEEK_END)
        while True:
            if not (lines := await fp.readlines()):
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
                events.from_log_line(line.strip())

            await asyncio.sleep(0.250)
