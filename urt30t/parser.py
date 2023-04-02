import asyncio
import logging
from pathlib import Path

import aiofiles

from . import events

logger = logging.getLogger(__name__)


async def parse_log_events(log_file: Path) -> None:
    logger.info("Parsing game log file %s", log_file)
    async with aiofiles.open(log_file, encoding="utf-8") as fp:
        while True:
            if lines := await fp.readlines():
                for line in lines:
                    events.from_log_line(line.strip())
            await asyncio.sleep(0.250)
