import dataclasses
import enum
import functools
import re
from typing import Any, NamedTuple, Self

RE_COLOR = re.compile(r"(\^\d)")

RE_SCORES = re.compile(r"\s*R:(?P<red>\d+)\s+B:(?P<blue>\d+)")

RE_PLAYER = re.compile(
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


class Group(enum.IntEnum):
    GUEST = 0
    USER = 1
    REGULAR = 2
    MODERATOR = 20
    ADMIN = 40
    FULL_ADMIN = 60
    SENIOR_ADMIN = 80
    SUPER_ADMIN = 100


class Team(enum.Enum):
    UNKNOWN = "-1"
    FREE = "0"
    RED = "1"
    BLUE = "2"
    SPECTATOR = "3"


class BombAction(enum.Enum):
    COLLECTED = "collected"
    DEFUSED = "defused"
    DROPPED = "dropped"
    PLACED = "placed"
    PLANTED = "planted"
    TOSSED = "tossed"


class KillMode(enum.Enum):
    WATER = "1"
    LAVA = "3"
    TELEFRAG = "5"
    FALLING = "6"
    SUICIDE = "7"
    TRIGGER_HURT = "9"
    CHANGE_TEAM = "10"
    KNIFE = "12"
    KNIFE_THROWN = "13"
    BERETTA = "14"
    DEAGLE = "15"
    SPAS = "16"
    UMP45 = "17"
    MP5K = "18"
    LR300 = "19"
    G36 = "20"
    PSG1 = "21"
    HK69 = "22"
    BLED = "23"
    KICKED = "24"
    HEGRENADE = "25"
    SR8 = "28"
    AK103 = "30"
    SPLODED = "31"
    SLAPPED = "32"
    SMITED = "33"
    BOMBED = "34"
    NUKED = "35"
    NEGEV = "36"
    HK69_HIT = "37"
    M4 = "38"
    GLOCK = "39"
    COLT1911 = "40"
    MAC11 = "41"
    FRF1 = "42"
    BENELLI = "43"
    P90 = "44"
    MAGNUM = "45"
    TOD50 = "46"
    FLAG = "47"
    GOOMBA = "48"


class PlayerScore(NamedTuple):
    kills: int
    deaths: int
    assists: int


class PlayerState(enum.Enum):
    DEAD = "1"
    ALIVE = "2"
    UNKNOWN = "3"


@functools.total_ordering
@dataclasses.dataclass
class Player:
    slot: str
    name: str
    guid: str | None = None
    auth: str | None = None
    team: Team = Team.UNKNOWN
    score: PlayerScore = PlayerScore(0, 0, 0)
    ping: int = 0
    ip_address: str | None = None
    validated: bool = False
    state: PlayerState = PlayerState.UNKNOWN

    @property
    def kills(self) -> int:
        return self.score.kills

    @property
    def deaths(self) -> int:
        return self.score.deaths

    @property
    def assists(self) -> int:
        return self.score.assists

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
        if m := RE_PLAYER.match(data.strip()):
            name = RE_COLOR.sub("", m["name"])
            team = Team[m["team"]]
            score = PlayerScore._make(int(m[x]) for x in PlayerScore._fields)
            ping = -1 if m["ping"] in ("CNCT", "ZMBI") else int(m["ping"])
            ip_addr, _, port = m["ip_address"].partition(":")
            return cls(
                slot=m["slot"],
                name=name,
                team=team,
                score=score,
                ping=ping,
                auth=m["auth"],
                ip_address=ip_addr,
            )
        raise ValueError(data)


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


class GameState(enum.Enum):
    UNKNOWN = "0"
    WARMUP = "1"
    LIVE = "2"


@dataclasses.dataclass
class Game:
    type: GameType = GameType.UNKNOWN
    time: str = "00:00:00"
    map_name: str = "Unknown"
    state: GameState = GameState.UNKNOWN
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
    def from_string(cls, data: str) -> Self:
        in_header = True
        settings = {}
        players = []
        for line in data.splitlines():
            k, v = line.split(":", maxsplit=1)
            if in_header:
                settings[k] = v.strip()
                if k == "GameTime":
                    in_header = False
            elif k.isnumeric():
                players.append(Player.from_string(line))
            elif k == "Map":
                # back-to-back messages, start over
                settings[k] = v.strip()
                in_header = True

        if (player_count := int(settings.get("Players", "0"))) != len(players):
            msg = (
                f"Player count {player_count} does not match "
                f"players {len(players)}"
                f"\n\n{data}"
            )
            raise RuntimeError(msg)

        if not (map_name := settings.get("Map", "Unknown")):
            raise RuntimeError("MAP_NOT_SET", data)

        return cls(
            type=GameType[settings.get("GameType", "UNKNOWN")],
            time=settings.get("GameTime", "00:00:00"),
            map_name=map_name,
            state=GameState.LIVE
            if settings.get("WarmupPhase", "NO") != "NO"
            else GameState.WARMUP,
            match_mode=settings.get("MatchMode", "OFF") != "OFF",
            scores=settings.get("Scores"),
            players={p.slot: p for p in players},
        )


class Cvar(NamedTuple):
    name: str
    value: str
    default: str | None = None
