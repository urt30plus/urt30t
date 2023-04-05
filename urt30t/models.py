import dataclasses
import enum
import functools
import re
from typing import Any, NamedTuple, Self


class Group(enum.IntEnum):
    guest = 0
    user = 1
    reg = 2
    mod = 20
    admin = 40
    full_admin = 60
    senior_admin = 80
    super_admin = 100


class Team(enum.Enum):
    UNKNOWN = "-1"
    FREE = "0"
    SPEC = "1"
    RED = "2"
    BLUE = "3"


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
    RE_COLOR = re.compile(r"(\^\d)")

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

    id: str
    name: str
    guid: str | None = None
    team: Team = Team.UNKNOWN
    score: PlayerScore = PlayerScore(0, 0, 0)
    ping: int = 0
    auth: str | None = None
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
        if m := re.match(Player.RE_PLAYER, data.strip()):
            name = re.sub(Player.RE_COLOR, "", m["name"])
            team = Team[m["team"]]
            score = PlayerScore._make(int(m[x]) for x in PlayerScore._fields)
            ping = -1 if m["ping"] in ("CNCT", "ZMBI") else int(m["ping"])
            return cls(
                id=m["slot"],
                name=name,
                team=team,
                score=score,
                ping=ping,
                auth=m["auth"],
                ip_address=m["ip_address"],
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
    RE_SCORES = re.compile(r"\s*R:(?P<red>\d+)\s+B:(?P<blue>\d+)")

    type: GameType = GameType.UNKNOWN
    time: str = "00:00:00"
    map_name: str = "Unknown"
    state: GameState = GameState.UNKNOWN
    scores: str | None = None
    players: dict[str, Player] = dataclasses.field(default_factory=dict)

    @property
    def score_red(self) -> str | None:
        if not self.scores:
            return None
        if m := re.match(self.RE_SCORES, self.scores):
            return m["red"]
        return None

    @property
    def score_blue(self) -> str | None:
        if not self.scores:
            return None
        if m := re.match(self.RE_SCORES, self.scores):
            return m["blue"]
        return None

    @property
    def spectators(self) -> list[Player]:
        return self._get_team(Team.SPEC)

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

        players.sort(reverse=True)
        return cls(
            type=GameType[settings.get("GameType", "UNKNOWN")],
            time=settings.get("GameTime", "00:00:00"),
            map_name=map_name,
            scores=settings.get("Scores"),
        )


class Cvar(NamedTuple):
    name: str
    value: str
    default: str | None = None


class EventType(enum.Enum):
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


class LogEvent(NamedTuple):
    type: EventType
    game_time: str
    data: str


class Event(NamedTuple):
    type: EventType
    game_time: str
    data: dict[str, Any] | None = None
    client: str | None = None
    target: str | None = None
