import dataclasses
from collections.abc import Awaitable, Callable
from typing import NamedTuple, Self

from . import Team
from .models import BombAction, FlagAction, HitLocation, HitMode, KillMode

EventHandler = Callable[["GameEvent"], Awaitable[None]]


class EventParseError(Exception):
    pass


class LogEvent(NamedTuple):
    type: type["GameEvent"]
    game_time: str = "0:00"
    data: str = ""

    def game_event(self) -> "GameEvent":
        return self.type.from_log_event(self)


@dataclasses.dataclass
class GameEvent:
    """Base class for all game related events."""

    game_time: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        return cls(game_time=log_event.game_time)


@dataclasses.dataclass
class SlotGameEvent(GameEvent):
    slot: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        if not log_event.data:
            msg = f"data missing for event: {log_event!r}"
            raise EventParseError(msg)
        return cls(game_time=log_event.game_time, slot=log_event.data)


@dataclasses.dataclass
class AccountKick(SlotGameEvent):
    """2:34 AccountKick: 13 - [ABC]foobar^7 rejected: no account"""

    text: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        slot, _, text = log_event.data.partition(" - ")
        return cls(game_time=log_event.game_time, slot=slot, text=text)


@dataclasses.dataclass
class AccountRejected(SlotGameEvent):
    """0:57 AccountRejected: 19 -  - "no account" """

    text: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        slot, _, text = log_event.data.partition(" ")
        return cls(game_time=log_event.game_time, slot=slot, text=text)


@dataclasses.dataclass
class AccountValidated(SlotGameEvent):
    """0:03 AccountValidated: 0 - m0neysh0t - 6 - "" """

    auth: str
    text: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        if not log_event.data:
            msg = f"data missing for event: {log_event!r}"
            raise EventParseError(msg)
        slot, auth, text = log_event.data.split(" - ", maxsplit=2)
        return cls(game_time=log_event.game_time, slot=slot, auth=auth, text=text)


@dataclasses.dataclass
class Assist(SlotGameEvent):
    """2:34 Assist: 12 1 0: Trance^7 assisted |30+|spooky^7 to kill |30+|Roberts^7"""

    killer: str
    victim: str
    text: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        slots, _, text = log_event.data.partition(": ")
        slot, killer, victim = slots.split(" ")
        return cls(
            game_time=log_event.game_time,
            slot=slot,
            killer=killer,
            victim=victim,
            text=text,
        )


@dataclasses.dataclass
class Bomb(SlotGameEvent):
    """0:44 Bomb was tossed by 8
    3:28 Bomb was planted by 13
    6:52 Bomb was defused by 11!
    3:22 Bomb has been collected by 13
    """

    action: BombAction

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        if not log_event.data:
            msg = f"data missing for event: {log_event!r}"
            raise EventParseError(msg)
        action, _, slot = log_event.data.split(" ")
        slot = slot.rstrip("!")  # defused by 11!
        return cls(game_time=log_event.game_time, slot=slot, action=BombAction(action))


@dataclasses.dataclass
class BombHolder(SlotGameEvent):
    """5:52 Bombholder is 2"""

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        return cls(game_time=log_event.game_time, slot=log_event.data)


@dataclasses.dataclass
class BotStartup(GameEvent):
    pass


@dataclasses.dataclass
class CallVote(GameEvent):
    """TODO: implement me"""


@dataclasses.dataclass
class ClientBegin(SlotGameEvent):
    """6:55 ClientBegin: 4"""


@dataclasses.dataclass
class ClientConnect(SlotGameEvent):
    """8:38 ClientConnect: 15"""


@dataclasses.dataclass
class ClientDisconnect(SlotGameEvent):
    """12:08 ClientDisconnect: 16"""


@dataclasses.dataclass
class ClientMelted(SlotGameEvent):
    """1:52 ClientMelted: 11"""


@dataclasses.dataclass
class ClientSpawn(SlotGameEvent):
    """12:17 ClientSpawn: 4"""


@dataclasses.dataclass
class ClientUserInfo(SlotGameEvent):
    r"""12:17 ClientUserinfo: 12 \ip\..\authc\74..\authl\2..\cl_guid\...."""

    user_data: dict[str, str]

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        if not log_event.data:
            msg = f"data missing for event: {log_event!r}"
            raise EventParseError(msg)
        slot, _, text = log_event.data.partition(" ")
        data = _parse_info_string(text)
        return cls(game_time=log_event.game_time, slot=slot, user_data=data)


@dataclasses.dataclass
class ClientUserinfoChanged(ClientUserInfo):
    r"""12:19 ClientUserinfoChanged: 16 n\...^7\t\3\r\2"""


@dataclasses.dataclass
class Exit(GameEvent):
    """13:26 Exit: Timelimit hit."""

    reason: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        return cls(game_time=log_event.game_time, reason=log_event.data)


@dataclasses.dataclass
class Flag(SlotGameEvent):
    """0:46 Flag: 0 2: team_CTF_redflag"""

    action: FlagAction
    team: Team

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        slots, _, flag = log_event.data.partition(":")
        slot, action = slots.split(" ")
        flag = flag.strip()
        if flag == "team_CTF_redflag":
            team = Team.RED
        elif flag == "team_CTF_blueflag":
            team = Team.BLUE
        else:
            raise ValueError(flag)
        return cls(
            game_time=log_event.game_time,
            slot=slot,
            action=FlagAction(action),
            team=team,
        )


@dataclasses.dataclass
class FlagCaptureTime(SlotGameEvent):
    """0:46 FlagCaptureTime: 0: 6000"""

    cap_time: float

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        slot, _, data = log_event.data.partition(": ")
        cap_time = float(data) / 1000
        return cls(game_time=log_event.game_time, slot=slot, cap_time=cap_time)


@dataclasses.dataclass
class FlagReturn(GameEvent):
    """2:30 Flag Return: BLUE"""

    team: Team

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        if not log_event.data:
            msg = f"data missing for event: {log_event!r}"
            raise EventParseError(msg)
        return cls(game_time=log_event.game_time, team=Team[log_event.data])


@dataclasses.dataclass
class Freeze(SlotGameEvent):
    """1:36 Freeze: 4 17 38: |30+|money^7 froze <>(CK)<>^7 by UT_MOD_M4"""

    target: str
    freeze_mode: KillMode

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        slots, _, _ = log_event.data.partition(":")
        slot, attacker, weapon = slots.split(" ")
        return cls(
            game_time=log_event.game_time,
            slot=slot,
            target=attacker,
            freeze_mode=KillMode(weapon),
        )


@dataclasses.dataclass
class Hit(SlotGameEvent):
    """2:02 Hit: 4 8 4 19: |30+|Mudcat^7 hit |30+|money^7 in the Vest"""

    attacker: str
    location: HitLocation
    hit_mode: HitMode

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        slots, _, _ = log_event.data.partition(":")
        slot, attacker, location, hit_mode = slots.split()
        return cls(
            game_time=log_event.game_time,
            slot=slot,
            attacker=attacker,
            location=HitLocation(location),
            hit_mode=HitMode(hit_mode),
        )


@dataclasses.dataclass
class HotPotato(GameEvent):
    """8:39 Hotpotato:"""


@dataclasses.dataclass
class InitAuth(GameEvent):
    r"""0:00 InitAuth: \auth\-1\auth_status\notoriety\auth_cheaters\1\..."""

    auth_data: dict[str, str]

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        if not log_event.data:
            msg = f"data missing for event: {log_event!r}"
            raise EventParseError(msg)
        return cls(
            game_time=log_event.game_time, auth_data=_parse_info_string(log_event.data)
        )


@dataclasses.dataclass
class InitGame(GameEvent):
    r"""0:00 InitGame: \sv_allowdownload\0\g_matchmode\0\g_gametype\7\..."""

    game_data: dict[str, str]

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        if not log_event.data:
            msg = f"data missing for event: {log_event!r}"
            raise EventParseError(msg)
        return cls(
            game_time=log_event.game_time, game_data=_parse_info_string(log_event.data)
        )


@dataclasses.dataclass
class InitRound(InitGame):
    r"""0:22 InitRound: \sv_allowdownload\0\g_matchmode\0\g_gametype\7\..."""


@dataclasses.dataclass
class Item(GameEvent):
    """1:51 Item: 13 team_CTF_redflag
    3:03 Item: 17 ut_weapon_tod50
    """


@dataclasses.dataclass
class Kill(SlotGameEvent):
    """3:17 Kill: 8 5 46: |30+|Mudcat^7 killed |30+|BenderBot^7 by UT_MOD_TOD50"""

    victim: str
    kill_mode: KillMode

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        parts, _, _ = log_event.data.partition(":")
        slot, victim, mode = parts.split(" ")
        return cls(
            game_time=log_event.game_time,
            slot=slot,
            victim=victim,
            kill_mode=KillMode(mode),
        )


@dataclasses.dataclass
class Pop(GameEvent):
    """9:24 Pop!"""


@dataclasses.dataclass
class Radio(GameEvent):
    """12:04 Radio: 10 - 9 - 9 - "A Stairs" - "^1[^2+^1]^2Thanks^1[^2+^1]" """


@dataclasses.dataclass
class Score(GameEvent):
    """13:26 score: 15  ping: 93  client: 10 |30+|hedgehog^7"""


@dataclasses.dataclass
class Say(SlotGameEvent):
    """15:25 say: 3 |30+|MerryMandolin^7: ggs"""

    name: str
    text: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        if not log_event.data:
            msg = f"data missing for event: {log_event!r}"
            raise EventParseError(msg)
        slot, text = log_event.data.split(" ", maxsplit=1)
        name, text = text.split(": ", maxsplit=1)
        return cls(game_time=log_event.game_time, slot=slot, name=name, text=text)


@dataclasses.dataclass
class SayTeam(Say):
    """7:31 sayteam: 2 |30+|money^7: nice one!"""


@dataclasses.dataclass
class SayTell(Say):
    target: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        if not log_event.data:
            msg = f"data missing for event: {log_event!r}"
            raise EventParseError(msg)
        slot, target, text = log_event.data.split(" ", maxsplit=2)
        name, text = text.split(": ", maxsplit=1)
        return cls(
            game_time=log_event.game_time,
            slot=slot,
            target=target,
            name=name,
            text=text,
        )


@dataclasses.dataclass
class ShutdownGame(GameEvent):
    """15:32 ShutdownGame:"""


@dataclasses.dataclass
class SurvivorWinner(GameEvent):
    """11403:1SurvivorWinner: Red
    3:43 SurvivorWinner: 0
    """

    # slot is optional so we do not use SlotGameEven
    # as the base
    slot: str | None = None
    team: Team | None = None

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        if log_event.data.isdigit():
            slot = log_event.data
            team = None
        else:
            slot = None
            team = Team[log_event.data.upper()]
        return cls(game_time=log_event.game_time, slot=slot, team=team)


@dataclasses.dataclass
class TeamScores(GameEvent):
    """15:22 red:8  blue:5"""

    red: int
    blue: int

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        red, _, blue = log_event.data.partition(" ")
        r = red.strip().removeprefix("red:")
        b = blue.strip().removeprefix("blue:")
        return cls(
            game_time=log_event.game_time,
            red=int(r),
            blue=int(b),
        )


@dataclasses.dataclass
class ThawOutFinished(SlotGameEvent):
    """1:42 ThawOutFinished: 4 13: |30+|money^7 thawed out I30+IColombianRipper^7"""

    target: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        slots, _, _ = log_event.data.partition(":")
        slot, target = slots.split()
        return cls(game_time=log_event.game_time, slot=slot, target=target)


@dataclasses.dataclass
class ThawOutStarted(SlotGameEvent):
    """1:52 ThawOutStarted: 4 9: |30+|money^7 started thawing out |30+|hedgehog^7"""

    target: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        slots, _, _ = log_event.data.partition(":")
        slot, target = slots.split()
        return cls(game_time=log_event.game_time, slot=slot, target=target)


@dataclasses.dataclass
class Vote(GameEvent):
    """TODO: implement me"""


@dataclasses.dataclass
class VoteFailed(GameEvent):
    """TODO: implement me"""


@dataclasses.dataclass
class VotePassed(GameEvent):
    """TODO: implement me"""


@dataclasses.dataclass
class Warmup(GameEvent):
    """0:00 Warmup:"""


_event_class_by_action: dict[str, type[GameEvent]] = {
    name.lower(): x
    for name, x in globals().copy().items()
    if isinstance(x, type) and issubclass(x, GameEvent)
}


def lookup_event_class(event_type: str) -> type[GameEvent] | None:
    return _event_class_by_action.get(event_type.lower())


def _parse_info_string(data: str) -> dict[str, str]:
    parts = data.lstrip("\\").split("\\")
    return dict(zip(parts[0::2], parts[1::2], strict=True))
