import asyncio
import logging
import os
from pathlib import Path

import aiofiles
import aiofiles.os

from .models import Event, EventType, LogEvent

logger = logging.getLogger(__name__)


async def parse_log_events(log_file: Path, q: asyncio.Queue[LogEvent]) -> None:
    logger.info("Parsing game log file %s", log_file)
    async with aiofiles.open(log_file, encoding="utf-8") as fp:
        await fp.seek(0, os.SEEK_END)
        while await asyncio.sleep(0.250, result=True):
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
                await q.put(from_log_line(line))


def from_log_line(line: str) -> LogEvent:
    """Creates a LogEvent from a raw log entry.

    A typical log entry usually starts with the time (MMM:SS) left padded
    with spaces, the event followed by a colon and then the even data. Ex.

    >>> evt = from_log_line("  0:28 Flag: 0 0: team_CTF_blueflag")
    >>> evt.game_time
    '0:28'
    >>> evt.event_type.name
    'flag'
    >>> evt.data
    '0 0: team_CTF_blueflag'

    This function main purpose is to perform a first pass parsing of the data
    in order to determine basic information about the log entry, such as
    the type of event.
    """
    game_time, _, rest = line.strip().partition(" ")
    event_name, sep, data = rest.partition(":")
    if sep:
        data = data.lstrip()
        try:
            event_type = EventType(event_name)
        except ValueError:
            logger.warning("event type not found: [%s]-[%s]", event_name, data)
            event_type = EventType.unknown
            data = rest
    elif event_name.startswith("Bombholder is "):
        event_type = EventType.bomb_holder
        data = event_name[14:]
    elif event_name.startswith("Bomb was "):
        event_type = EventType.bomb
        data = event_name[9:]
    elif event_name.startswith("Bomb has been "):
        event_type = EventType.bomb
        data = event_name[14:]
    elif event_name.startswith("Session data initialised for client on slot "):
        event_type = EventType.session_data_initialised
        data = event_name[44:]
    elif not event_name.strip("-"):
        event_type = EventType.log_separator
        data = ""
    else:
        logger.warning("event type not in log line: [%s]", line)
        event_type = EventType.unknown

    event = LogEvent(game_time=game_time, event_type=event_type, data=data)
    logger.debug("parsed %r", event)
    return event


async def from_log_event(log_event: LogEvent) -> Event:
    # TODO: implement me
    return Event(
        type=log_event.event_type,
        data={"data": log_event.data},
        client=None,
        target=None,
    )
