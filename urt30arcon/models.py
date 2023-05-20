import dataclasses
import enum
import functools
import logging
import re
from typing import Any, NamedTuple, Self

logger = logging.getLogger(__name__)

RE_COLOR = re.compile(r"(\^\d)")
RE_SCORES = re.compile(r"\s*R:(?P<RED>\d+)\s+B:(?P<BLUE>\d+)")
RE_PLAYER = re.compile(
    r"^(?P<slot>[0-9]+):(?P<name>.*)\s+"
    r"TEAM:(?P<team>RED|BLUE|SPECTATOR|FREE)\s+"
    r"KILLS:(?P<kills>-?[0-9]+)\s+"
    r"DEATHS:(?P<deaths>[0-9]+)\s+"
    r"ASSISTS:(?P<assists>[0-9]+)\s+"
    r"PING:(?P<ping>[0-9]+|CNCT|ZMBI)\s+"
    r"AUTH:(?P<auth>.*)\s+"
    r"IP:(?P<ip_address>.*):(?P<ip_port>.*)$",
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
        0:foo^7 TEAM:RED KILLS:8 DEATHS:5 ASSISTS:0 PING:98 AUTH:foo IP:127.0.0.1:27960
        """
        if m := RE_PLAYER.match(data.strip()):
            try:
                ping = int(m["ping"])
            except ValueError:
                if m["ping"] == "CNCT":
                    ping = -1
                elif m["ping"] == "ZMBI":
                    ping = -2
                else:
                    raise
            return cls(
                slot=m["slot"],
                name=m["name"].removesuffix("^7"),
                team=Team[m["team"]],
                kills=int(m["kills"]),
                deaths=int(m["deaths"]),
                assists=int(m["assists"]),
                ping=ping,
                auth=m["auth"],
                ip_address=m["ip_address"],
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
        return self._get_score_by_team(Team.RED)

    @property
    def score_blue(self) -> str | None:
        return self._get_score_by_team(Team.BLUE)

    @property
    def spectators(self) -> list[Player]:
        return self._get_players_by_team(Team.SPECTATOR)

    @property
    def team_free(self) -> list[Player]:
        return self._get_players_by_team(Team.FREE)

    @property
    def team_red(self) -> list[Player]:
        return self._get_players_by_team(Team.RED)

    @property
    def team_blue(self) -> list[Player]:
        return self._get_players_by_team(Team.BLUE)

    def _get_players_by_team(self, team: Team) -> list[Player]:
        return [p for p in self.players.values() if p.team is team]

    def _get_score_by_team(self, team: Team) -> str | None:
        if self.scores and (m := RE_SCORES.match(self.scores)):
            return m[team.name]
        return None

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
        game = cls()
        in_header = True
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
                player = Player.from_string(line)
                game.players[player.slot] = player
            elif k == "Map":
                # back-to-back messages, start over
                game.map_name = v
                in_header = True

        if game.map_name == "Unknown":
            raise RconError("map_not_found")

        if len(game.players) != game.player_count:
            msg = (
                f"Player count {game.player_count} does not match "
                f"players {len(game.players)}"
                f"\n\n{game}"
            )
            raise RconError(msg)

        return game
