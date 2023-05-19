import dataclasses
import enum
import functools
import logging
import re
from typing import Any, NamedTuple, Self

logger = logging.getLogger(__name__)

RE_COLOR = re.compile(r"(\^\d)")
RE_SCORES = re.compile(r"\s*R:(?P<red>\d+)\s+B:(?P<blue>\d+)")
_RE_PLAYER = re.compile(
    r"^(?P<slot>[0-9]+):(?P<name>.*)\s+"
    r"TEAM:(?P<team>RED|BLUE|SPECTATOR|FREE)\s+"
    r"KILLS:(?P<kills>-?[0-9]+)\s+"
    r"DEATHS:(?P<deaths>[0-9]+)\s+"
    r"ASSISTS:(?P<assists>[0-9]+)\s+"
    r"PING:(?P<ping>[0-9]+|CNCT|ZMBI)\s+"
    r"AUTH:(?P<auth>.*)\s+"
    r"IP:(?P<ip_address>.*)$",
    re.IGNORECASE,
)


class RconError(Exception):
    pass


class Cvar(NamedTuple):
    name: str
    value: str
    default: str | None = None


class Team(enum.Enum):
    UNKNOWN = "-1"
    FREE = "0"
    RED = "1"
    BLUE = "2"
    SPECTATOR = "3"


class GameType(enum.Enum):
    UNKNOWN = "UNKNOWN"
    FFA = "0"
    LMS = "1"
    TDM = "3"
    TS = "4"
    FTL = "5"
    CAH = "6"
    CTF = "7"
    BOMB = "8"
    JUMP = "9"
    FREEZETAG = "10"
    GUNGAME = "11"


@functools.total_ordering
@dataclasses.dataclass
class Player:
    slot: str
    name: str
    auth: str | None = None
    guid: str | None = None
    team: Team = Team.UNKNOWN
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    ping: int = 0
    ip_address: str | None = None

    @property
    def clean_name(self) -> str:
        return RE_COLOR.sub("", self.name)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Player):
            return NotImplemented
        # noinspection PyTypeChecker
        return (self.kills, self.deaths * -1, self.assists, self.name) < (
            other.kills,
            other.deaths * -1,
            other.assists,
            other.name,
        )

    @classmethod
    def from_string(cls, data: str) -> Self:
        """
        0:foo^7 TEAM:RED KILLS:15 DEATHS:22 ASSISTS:0 PING:98 AUTH:foo IP:127.0.0.1
        """
        if m := _RE_PLAYER.match(data.strip()):
            ip_addr, _, port = m["ip_address"].partition(":")
            ping = -1 if m["ping"] in ("CNCT", "ZMBI") else int(m["ping"])
            return cls(
                slot=m["slot"],
                name=m["name"].removesuffix("^7"),
                team=Team[m["temp"]],
                kills=int(m["kills"]),
                deaths=int(m["deaths"]),
                assists=int(m["assists"]),
                ping=ping,
                auth=m["auth"],
                ip_address=ip_addr,
            )

        raise ValueError(data)


@dataclasses.dataclass
class Game:
    map_name: str = "Unknown"
    player_count: int = 0
    type: GameType = GameType.UNKNOWN
    time: str = "0:00"
    warmup: bool = False
    match_mode: bool = False
    scores: str | None = None
    players: dict[str, Player] = dataclasses.field(default_factory=dict)

    @property
    def score_red(self) -> str | None:
        if not self.scores:
            return None
        if m := RE_SCORES.match(self.scores):
            return m["red"]
        return None

    @property
    def score_blue(self) -> str | None:
        if not self.scores:
            return None
        if m := RE_SCORES.match(self.scores):
            return m["blue"]
        return None

    @property
    def spectators(self) -> list[Player]:
        return self._get_team(Team.SPECTATOR)

    @property
    def team_free(self) -> list[Player]:
        return self._get_team(Team.FREE)

    @property
    def team_red(self) -> list[Player]:
        return self._get_team(Team.RED)

    @property
    def team_blue(self) -> list[Player]:
        return self._get_team(Team.BLUE)

    def _get_team(self, team: Team) -> list[Player]:
        return [p for p in self.players.values() if p.team is team]

    @classmethod
    def from_string(cls, data: str) -> Self:  # noqa: PLR0912
        """
        Map: ut4_abbey
        Players: 3
        GameType: CTF
        Scores: R:5 B:10
        MatchMode: OFF
        WarmupPhase: NO
        GameTime: 00:12:04
        0:foo^7 TEAM:RED KILLS:15 DEATHS:22 ASSISTS:0 PING:98 AUTH:foo IP:127.0.0.1
        """
        in_header = True
        game = cls()
        players = []
        for line in data.splitlines():
            k, v = line.split(":", maxsplit=1)
            v = v.strip()
            if in_header:
                if k == "Map":
                    game.map_name = v
                elif k == "Players":
                    game.player_count = int(v)
                elif k == "GameType":
                    game.type = GameType[v]
                elif k == "Scores":
                    game.scores = v
                elif k == "MatchMode":
                    game.match_mode = v != "OFF"
                elif k == "WarmupPhase":
                    game.warmup = v != "NO"
                elif k == "GameTime":
                    game.time = v
                    in_header = False
                else:
                    logger.warning("unknown header: %s - %s", k, v)
            elif k.isnumeric():
                players.append(Player.from_string(line))
            elif k == "Map":
                # back-to-back messages, start over
                game.map_name = v
                in_header = True

        if game.map_name == "Unknown":
            raise RconError("map_not_found")

        if len(players) != game.player_count:
            msg = (
                f"Player count {game.player_count} does not match "
                f"players {len(players)}"
                f"\n\n{game}"
            )
            raise RconError(msg)

        game.players = {p.slot: p for p in players}
        return game
