import dataclasses
from typing import NamedTuple, Self

from .models import BombAction, FlagAction, KillMode, Team


class LogEvent(NamedTuple):
    type: str
    game_time: str = "00:00"
    data: str = ""


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
        assert log_event.data
        return cls(game_time=log_event.game_time, slot=log_event.data)


@dataclasses.dataclass
class AccountKick(GameEvent):
    """2:34 AccountKick: 13 - [ABC]foobar^7 rejected: no account"""

    slot: str
    text: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        slot, _, text = log_event.data.partition(" - ")
        return cls(game_time=log_event.game_time, slot=slot, text=text)


@dataclasses.dataclass
class AccountRejected(GameEvent):
    """0:57 AccountRejected: 19 -  - "no account" """

    slot: str
    text: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        slot, _, text = log_event.data.partition(" ")
        return cls(game_time=log_event.game_time, slot=slot, text=text)


@dataclasses.dataclass
class AccountValidated(GameEvent):
    """0:03 AccountValidated: 0 - m0neysh0t - 6 - "" """

    slot: str
    auth: str
    text: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
        slot, auth, text = log_event.data.split(" - ", maxsplit=2)
        return cls(game_time=log_event.game_time, slot=slot, auth=auth, text=text)


@dataclasses.dataclass
class Assist(GameEvent):
    """2:34 Assist: 12 1 0: Trance^7 assisted |30+|spooky^7 to kill |30+|Roberts^7"""

    slot: str
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
class Bomb(GameEvent):
    """0:44 Bomb was tossed by 8
    3:28 Bomb was planted by 13
    6:52 Bomb was defused by 11!
    3:22 Bomb has been collected by 13
    """

    slot: str
    action: BombAction

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
        action, _, slot = log_event.data.split(" ")
        slot = slot.rstrip("!")  # defused by 11!
        return cls(game_time=log_event.game_time, slot=slot, action=BombAction(action))


@dataclasses.dataclass
class BombHolder(GameEvent):
    """5:52 Bombholder is 2"""

    slot: str

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

    slot: str


@dataclasses.dataclass
class ClientDisconnect(SlotGameEvent):
    """12:08 ClientDisconnect: 16"""

    slot: str


@dataclasses.dataclass
class ClientMelted(GameEvent):
    """TODO: implement me"""


@dataclasses.dataclass
class ClientSpawn(SlotGameEvent):
    """12:17 ClientSpawn: 4"""

    slot: str


@dataclasses.dataclass
class ClientUserInfo(GameEvent):
    r"""12:17 ClientUserinfo: 12 \ip\..\authc\74..\authl\2..\cl_guid\...."""
    slot: str
    user_data: dict[str, str]

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
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
class Flag(GameEvent):
    """0:46 Flag: 0 2: team_CTF_redflag"""

    slot: str
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
class FlagCaptureTime(GameEvent):
    """0:46 FlagCaptureTime: 0: 6000"""

    slot: str
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
        assert log_event.data
        return cls(game_time=log_event.game_time, team=Team[log_event.data])


@dataclasses.dataclass
class Freeze(GameEvent):
    pass


@dataclasses.dataclass
class Hit(GameEvent):
    """TODO: implement me"""


@dataclasses.dataclass
class HotPotato(GameEvent):
    """8:39 Hotpotato:"""


@dataclasses.dataclass
class InitAuth(GameEvent):
    r"""0:00 InitAuth: \auth\-1\auth_status\notoriety\auth_cheaters\1\..."""
    auth_data: dict[str, str]

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
        return cls(
            game_time=log_event.game_time, auth_data=_parse_info_string(log_event.data)
        )


@dataclasses.dataclass
class InitGame(GameEvent):
    r"""0:00 InitGame: \sv_allowdownload\0\g_matchmode\0\g_gametype\7\..."""
    game_data: dict[str, str]

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
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
class Kill(GameEvent):
    """3:17 Kill: 8 5 46: |30+|Mudcat^7 killed |30+|BenderBot^7 by UT_MOD_TOD50"""

    slot: str
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
class Say(GameEvent):
    """15:25 say: 3 |30+|MerryMandolin^7: ggs"""

    slot: str
    name: str
    text: str

    @classmethod
    def from_log_event(cls, log_event: LogEvent) -> Self:
        assert log_event.data
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
        assert log_event.data
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


def _parse_info_string(data: str) -> dict[str, str]:
    parts = data.lstrip("\\").split("\\")
    return dict(zip(parts[0::2], parts[1::2], strict=True))
