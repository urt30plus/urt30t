import enum
import logging
from typing import Any

from pydantic import BaseModel

from .game import Client

logger = logging.getLogger(__name__)


class EventType(enum.StrEnum):
    account_kick = "AccountKick"
    account_rejected = "AccountRejected"
    account_validated = "AccountValidated"
    assist = "Assist"
    bomb = "Bomb"
    bomb_pop = "Pop"
    bomb_holder = "Bombholder"
    call_vote = "Callvote"
    client_begin = "ClientBegin"
    client_connect = "ClientConnect"
    client_disconnect = "ClientDisconnect"
    client_goto = "ClientGoto"
    client_jump_run_canceled = "ClientJumpRunCanceled"
    client_jump_run_started = "ClientJumpRunStarted"
    client_jump_run_stopped = "ClientJumpRunStopped"
    client_load_position = "ClientLoadPosition"
    client_melted = "ClientMelted"
    client_save_position = "ClientSavePosition"
    client_spawn = "ClientSpawn"
    client_user_info = "ClientUserinfo"
    client_user_info_changed = "ClientUserinfoChanged"
    exit_game = "Exit"
    flag = "Flag"
    flag_capture_time = "FlagCaptureTime"
    flag_return = "Flag Return"
    freeze = "Freeze"
    hit = "Hit"
    hot_potato = "Hotpotato"
    init_auth = "InitAuth"
    init_game = "InitGame"
    init_round = "InitRound"
    item = "Item"
    kill = "Kill"
    log_separator = "Log Separator"
    radio = "Radio"
    red = "red"
    say = "say"
    say_team = "sayteam"
    say_tell = "saytell"
    score = "score"
    session_data_initialised = "Session data"
    shutdown_game = "ShutdownGame"
    unknown = "unknown"
    vote = "Vote"
    vote_failed = "VoteFailed"
    vote_passed = "VotePassed"
    warmup = "Warmup"


class Event(BaseModel):
    type: EventType
    data: dict[str, Any] | None
    client: Client | None
    target: Client | None


class LogEvent(BaseModel):
    game_time: str
    event_type: EventType
    data: str | None


def from_log_line(line: str) -> LogEvent:
    """Creates a LogEvent from a raw log entry.

    A typical log entry usually starts with the time (MMM:SS) left padded
    with spaces, the event followed by a colon and then the even data. Ex.

    >>> event = from_log_line("  0:28 Flag: 0 0: team_CTF_blueflag")
    >>> event.game_time
    '0:28'
    >>> event.event_type.name
    'flag'
    >>> event.data
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
