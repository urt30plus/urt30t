import asyncio
import dataclasses
import logging
import os
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Self, cast

from . import Team
from .models import BombAction, BotContext, FlagAction, HitLocation, HitMode, KillMode

if TYPE_CHECKING:
    from pathlib import Path

type EventHandler[T] = Callable[[BotContext, T], Awaitable[None]]

logger = logging.getLogger(__name__)


class EventParseError(Exception):
    pass


@dataclasses.dataclass
class LogEntry:
    kind: type[Event]
    event_time: str = "0:00"
    data: str = ""

    def parse_event(self) -> Event:
        return self.kind.from_log_entry(self)


@dataclasses.dataclass
class Event:
    """Base class for all Bot and Game related events."""

    event_time: str

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        return cls(event_time=log_entry.event_time)


@dataclasses.dataclass
class BotStarted(Event):
    pass


@dataclasses.dataclass
class SlotEvent(Event):
    slot: str

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        if not log_entry.data:
            msg = f"data missing for event: {log_entry!r}"
            raise EventParseError(msg)
        return cls(event_time=log_entry.event_time, slot=log_entry.data)


@dataclasses.dataclass
class AccountKick(SlotEvent):
    """2:34 AccountKick: 13 - [ABC]foobar^7 rejected: no account"""

    text: str

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        slot, _, text = log_entry.data.partition(" - ")
        return cls(event_time=log_entry.event_time, slot=slot, text=text)


@dataclasses.dataclass
class AccountRejected(SlotEvent):
    """0:57 AccountRejected: 19 -  - "no account" """

    text: str

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        slot, _, text = log_entry.data.partition(" ")
        return cls(event_time=log_entry.event_time, slot=slot, text=text)


@dataclasses.dataclass
class AccountValidated(SlotEvent):
    """0:03 AccountValidated: 0 - m0neysh0t - 6 - "" """

    auth: str
    text: str

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        if not log_entry.data:
            msg = f"data missing for event: {log_entry!r}"
            raise EventParseError(msg)
        slot, auth, text = log_entry.data.split(" - ", maxsplit=2)
        return cls(event_time=log_entry.event_time, slot=slot, auth=auth, text=text)


@dataclasses.dataclass
class Assist(SlotEvent):
    """2:34 Assist: 12 1 0: Trance^7 assisted |30+|spooky^7 to kill |30+|Roberts^7"""

    killer: str
    victim: str
    text: str

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        slots, _, text = log_entry.data.partition(": ")
        slot, killer, victim = slots.split(" ")
        return cls(
            event_time=log_entry.event_time,
            slot=slot,
            killer=killer,
            victim=victim,
            text=text,
        )


@dataclasses.dataclass
class Bomb(SlotEvent):
    """0:44 Bomb was tossed by 8
    3:28 Bomb was planted by 13
    6:52 Bomb was defused by 11!
    3:22 Bomb has been collected by 13
    """

    action: BombAction

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        if not log_entry.data:
            msg = f"data missing for event: {log_entry!r}"
            raise EventParseError(msg)
        action, _, slot = log_entry.data.split(" ")
        slot = slot.rstrip("!")  # defused by 11!
        return cls(
            event_time=log_entry.event_time, slot=slot, action=BombAction(action)
        )


@dataclasses.dataclass
class BombHolder(SlotEvent):
    """5:52 Bombholder is 2"""

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        return cls(event_time=log_entry.event_time, slot=log_entry.data)


@dataclasses.dataclass
class CallVote(Event):
    """TODO: implement me"""


@dataclasses.dataclass
class ClientBegin(SlotEvent):
    """6:55 ClientBegin: 4"""


@dataclasses.dataclass
class ClientConnect(SlotEvent):
    """8:38 ClientConnect: 15"""


@dataclasses.dataclass
class ClientDisconnect(SlotEvent):
    """12:08 ClientDisconnect: 16"""


@dataclasses.dataclass
class ClientMelted(SlotEvent):
    """1:52 ClientMelted: 11"""


@dataclasses.dataclass
class ClientSpawn(SlotEvent):
    """12:17 ClientSpawn: 4"""


@dataclasses.dataclass
class ClientUserInfo(SlotEvent):
    r"""12:17 ClientUserinfo: 12 \ip\..\authc\74..\authl\2..\cl_guid\...."""

    user_data: dict[str, str]

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        if not log_entry.data:
            msg = f"data missing for event: {log_entry!r}"
            raise EventParseError(msg)
        slot, _, text = log_entry.data.partition(" ")
        data = _parse_info_string(text)
        return cls(event_time=log_entry.event_time, slot=slot, user_data=data)


@dataclasses.dataclass
class ClientUserinfoChanged(ClientUserInfo):
    r"""12:19 ClientUserinfoChanged: 16 n\...^7\t\3\r\2"""


@dataclasses.dataclass
class Exit(Event):
    """13:26 Exit: Timelimit hit."""

    reason: str

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        return cls(event_time=log_entry.event_time, reason=log_entry.data)


@dataclasses.dataclass
class Flag(SlotEvent):
    """0:46 Flag: 0 2: team_CTF_redflag"""

    action: FlagAction
    team: Team

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        slots, _, flag = log_entry.data.partition(":")
        slot, action = slots.split(" ")
        flag = flag.strip()
        if flag == "team_CTF_redflag":
            team = Team.RED
        elif flag == "team_CTF_blueflag":
            team = Team.BLUE
        else:
            raise ValueError(flag)
        return cls(
            event_time=log_entry.event_time,
            slot=slot,
            action=FlagAction(action),
            team=team,
        )


@dataclasses.dataclass
class FlagCaptureTime(SlotEvent):
    """0:46 FlagCaptureTime: 0: 6000"""

    cap_time: float

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        slot, _, data = log_entry.data.partition(": ")
        cap_time = float(data) / 1000
        return cls(event_time=log_entry.event_time, slot=slot, cap_time=cap_time)


@dataclasses.dataclass
class FlagReturn(Event):
    """2:30 Flag Return: BLUE"""

    team: Team

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        if not log_entry.data:
            msg = f"data missing for event: {log_entry!r}"
            raise EventParseError(msg)
        return cls(event_time=log_entry.event_time, team=Team[log_entry.data])


@dataclasses.dataclass
class Freeze(SlotEvent):
    """1:36 Freeze: 4 17 38: |30+|money^7 froze <>(CK)<>^7 by UT_MOD_M4"""

    target: str
    freeze_mode: KillMode

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        slots, _, _ = log_entry.data.partition(":")
        slot, attacker, weapon = slots.split(" ")
        return cls(
            event_time=log_entry.event_time,
            slot=slot,
            target=attacker,
            freeze_mode=KillMode(weapon),
        )


@dataclasses.dataclass
class Hit(SlotEvent):
    """2:02 Hit: 4 8 4 19: |30+|Mudcat^7 hit |30+|money^7 in the Vest"""

    attacker: str
    location: HitLocation
    hit_mode: HitMode

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        slots, _, _ = log_entry.data.partition(":")
        slot, attacker, location, hit_mode = slots.split()
        return cls(
            event_time=log_entry.event_time,
            slot=slot,
            attacker=attacker,
            location=HitLocation(location),
            hit_mode=HitMode(hit_mode),
        )


@dataclasses.dataclass
class HotPotato(Event):
    """8:39 Hotpotato:"""


@dataclasses.dataclass
class InitAuth(Event):
    r"""0:00 InitAuth: \auth\-1\auth_status\notoriety\auth_cheaters\1\..."""

    auth_data: dict[str, str]

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        if not log_entry.data:
            msg = f"data missing for event: {log_entry!r}"
            raise EventParseError(msg)
        return cls(
            event_time=log_entry.event_time,
            auth_data=_parse_info_string(log_entry.data),
        )


@dataclasses.dataclass
class InitGame(Event):
    r"""0:00 InitGame: \sv_allowdownload\0\g_matchmode\0\g_gametype\7\..."""

    game_data: dict[str, str]

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        if not log_entry.data:
            msg = f"data missing for event: {log_entry!r}"
            raise EventParseError(msg)
        return cls(
            event_time=log_entry.event_time,
            game_data=_parse_info_string(log_entry.data),
        )


@dataclasses.dataclass
class InitRound(InitGame):
    r"""0:22 InitRound: \sv_allowdownload\0\g_matchmode\0\g_gametype\7\..."""


@dataclasses.dataclass
class Item(Event):
    """1:51 Item: 13 team_CTF_redflag
    3:03 Item: 17 ut_weapon_tod50
    """


@dataclasses.dataclass
class Kill(SlotEvent):
    """3:17 Kill: 8 5 46: |30+|Mudcat^7 killed |30+|BenderBot^7 by UT_MOD_TOD50"""

    victim: str
    kill_mode: KillMode

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        parts, _, _ = log_entry.data.partition(":")
        slot, victim, mode = parts.split(" ")
        return cls(
            event_time=log_entry.event_time,
            slot=slot,
            victim=victim,
            kill_mode=KillMode(mode),
        )


@dataclasses.dataclass
class Pop(Event):
    """9:24 Pop!"""


@dataclasses.dataclass
class Radio(Event):
    """12:04 Radio: 10 - 9 - 9 - "A Stairs" - "^1[^2+^1]^2Thanks^1[^2+^1]" """


@dataclasses.dataclass
class Score(Event):
    """13:26 score: 15  ping: 93  client: 10 |30+|hedgehog^7"""


@dataclasses.dataclass
class Say(SlotEvent):
    """15:25 say: 3 |30+|MerryMandolin^7: ggs"""

    name: str
    text: str

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        if not log_entry.data:
            msg = f"data missing for event: {log_entry!r}"
            raise EventParseError(msg)
        slot, text = log_entry.data.split(" ", maxsplit=1)
        name, text = text.split(": ", maxsplit=1)
        return cls(event_time=log_entry.event_time, slot=slot, name=name, text=text)


@dataclasses.dataclass
class SayTeam(Say):
    """7:31 sayteam: 2 |30+|money^7: nice one!"""


@dataclasses.dataclass
class SayTell(Say):
    target: str

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        if not log_entry.data:
            msg = f"data missing for event: {log_entry!r}"
            raise EventParseError(msg)
        slot, target, text = log_entry.data.split(" ", maxsplit=2)
        name, text = text.split(": ", maxsplit=1)
        return cls(
            event_time=log_entry.event_time,
            slot=slot,
            target=target,
            name=name,
            text=text,
        )


@dataclasses.dataclass
class ShutdownGame(Event):
    """15:32 ShutdownGame:"""


@dataclasses.dataclass
class SurvivorWinner(Event):
    """11403:1SurvivorWinner: Red
    3:43 SurvivorWinner: 0
    """

    # slot is optional so we do not use SlotGameEven
    # as the base
    slot: str | None = None
    team: Team | None = None

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        if log_entry.data.isdigit():
            slot = log_entry.data
            team = None
        else:
            slot = None
            team = Team[log_entry.data.upper()]
        return cls(event_time=log_entry.event_time, slot=slot, team=team)


@dataclasses.dataclass
class TeamScores(Event):
    """15:22 red:8  blue:5"""

    red: int
    blue: int

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        red, _, blue = log_entry.data.partition(" ")
        r = red.strip().removeprefix("red:")
        b = blue.strip().removeprefix("blue:")
        return cls(
            event_time=log_entry.event_time,
            red=int(r),
            blue=int(b),
        )


@dataclasses.dataclass
class ThawOutFinished(SlotEvent):
    """1:42 ThawOutFinished: 4 13: |30+|money^7 thawed out I30+IColombianRipper^7"""

    target: str

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        slots, _, _ = log_entry.data.partition(":")
        slot, target = slots.split()
        return cls(event_time=log_entry.event_time, slot=slot, target=target)


@dataclasses.dataclass
class ThawOutStarted(SlotEvent):
    """1:52 ThawOutStarted: 4 9: |30+|money^7 started thawing out |30+|hedgehog^7"""

    target: str

    @classmethod
    def from_log_entry(cls, log_entry: LogEntry) -> Self:
        slots, _, _ = log_entry.data.partition(":")
        slot, target = slots.split()
        return cls(event_time=log_entry.event_time, slot=slot, target=target)


@dataclasses.dataclass
class Vote(Event):
    """TODO: implement me"""


@dataclasses.dataclass
class VoteFailed(Event):
    """TODO: implement me"""


@dataclasses.dataclass
class VotePassed(Event):
    """TODO: implement me"""


@dataclasses.dataclass
class Warmup(Event):
    """0:00 Warmup:"""


_event_class_by_action: dict[str, type[Event]] = {
    name.lower(): cast("type[Event]", x)
    for name, x in globals().copy().items()
    if isinstance(x, type) and issubclass(x, Event)
}


def _parse_info_string(data: str) -> dict[str, str]:
    parts = data.lstrip("\\").split("\\")
    return dict(zip(parts[0::2], parts[1::2], strict=True))


async def tail_log(
    log_file: Path,
    *,
    event_queue: asyncio.Queue[LogEntry],
    read_delay: float,
) -> None:
    logger.info("Parsing game log file %s", log_file)
    fp = await asyncio.to_thread(log_file.open, mode="r", encoding="utf-8")
    try:
        cur_pos = await asyncio.to_thread(fp.seek, 0, os.SEEK_END)
        logger.info(
            "read delay [%s], current pos [%s]",
            read_delay,
            cur_pos,
        )
        # signal that we are ready and wait for the event dispatcher to start
        await event_queue.put(LogEntry(kind=BotStarted))
        await event_queue.join()
        while await asyncio.sleep(read_delay, result=True):
            if lines := await asyncio.to_thread(fp.readlines):
                for line in lines:
                    if log_entry := parse_log_line(line):  # ty: ignore[invalid-argument-type]
                        await event_queue.put(log_entry)
    finally:
        await asyncio.to_thread(fp.close)


def parse_log_line(line: str) -> LogEntry | None:
    """Creates a LogEntry from a raw log entry.

    A typical log entry usually starts with the time (MMM:SS) left padded
    with spaces, the event followed by a colon and then the even data. Ex.

    This function main purpose is to perform a first pass parsing of the data
    in order to determine basic information about the log entry, such as
    the type of event.
    """
    event_time = line[:7].strip()
    rest = line[7:].strip()
    event_name, sep, data = rest.partition(":")
    event_type: type[Event] | None
    if sep:
        event_name = event_name.replace(" ", "")
        data = data.lstrip()
        if event_name == "red":
            event_type = TeamScores
            data = f"red:{data}"
        elif not (event_type := _event_class_by_action.get(event_name.lower())):
            logger.warning("no event class found: %s", line)
    elif event_name.startswith("Bombholder is "):
        event_type = BombHolder
        data = event_name[14:]
    elif event_name.startswith("Bomb was "):
        event_type = Bomb
        data = event_name[9:]
    elif event_name.startswith("Bomb has been "):
        event_type = Bomb
        data = event_name[14:]
    elif event_name == "Pop!":
        event_type = Pop
        data = ""
    elif event_name.startswith(("Session data", "-----")):
        event_type = None
    else:
        logger.warning("event type not in log line: [%s]", line)
        event_type = None

    if event_type is None:
        return None

    event = LogEntry(kind=event_type, event_time=event_time, data=data)
    logger.debug(event)
    return event
