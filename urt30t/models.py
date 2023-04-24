import abc
import dataclasses
import enum
import functools
from collections.abc import Awaitable, Callable
from typing import Any, NamedTuple, Protocol, Self

from . import rcon

CommandHandler = Callable[["BotCommand"], Awaitable[None]]


class Group(enum.IntEnum):
    UNKNOWN = -1
    GUEST = 1
    USER = 10
    FRIEND = 20
    MODERATOR = 30
    ADMIN = 100


class MessageType(enum.Enum):
    BIG = "&"
    LOUD = "@"
    PRIVATE = "!"


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


class FlagAction(enum.Enum):
    DROPPED = "0"
    RETURNED = "1"
    CAPTURED = "2"


class HitLocation(enum.Enum):
    HEAD = "1"
    HELMET = "2"
    TORSO = "3"
    VEST = "4"
    LEFT_ARM = "5"
    RIGHT_ARM = "6"
    GROIN = "7"
    BUTT = "8"
    LEFT_UPPER_LEG = "9"
    RIGHT_UPPER_LEG = "10"
    LEFT_LOWER_LEG = "11"
    RIGHT_LOWER_LEG = "12"
    LEFT_FOOT = "13"
    RIGHT_FOOT = "14"


class HitMode(enum.Enum):
    KNIFE = "1"
    BERETTA = "2"
    DEAGLE = "3"
    SPAS = "4"
    MP5K = "5"
    UMP45 = "6"
    LR300 = "8"
    G36 = "9"
    PSG1 = "10"
    SR8 = "14"
    AK103 = "15"
    NEGEV = "17"
    M4 = "19"
    GLOCK = "20"
    COLT1911 = "21"
    MAC11 = "22"
    FRF1 = "23"
    BENELLI = "24"
    P90 = "25"
    MAGNUM = "26"
    TOD50 = "27"
    KICKED = "29"
    KNIFE_THROWN = "30"


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
    score: PlayerScore = PlayerScore(0, 0, 0)  # noqa: RUF009
    ping: int = 0
    ip_address: str | None = None
    validated: bool = False
    state: PlayerState = PlayerState.UNKNOWN
    group: Group = Group.UNKNOWN

    @property
    def clean_name(self) -> str:
        return rcon.RE_COLOR.sub("", self.name)

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
    def from_dict(cls, p: rcon.Player) -> Self:
        ping = -1 if p["ping"] in ("CNCT", "ZMBI") else int(p["ping"])
        return cls(
            slot=p["slot"],
            name=p["name"],
            team=Team[p["team"]],
            score=PlayerScore(p["kills"], p["deaths"], p["assists"]),
            ping=ping,
            auth=p["auth"],
            ip_address=p["ip_address"],
        )


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
    time: str = "0:00"
    map_name: str = "Unknown"
    state: GameState = GameState.UNKNOWN
    match_mode: bool = False
    scores: str | None = None
    players: dict[str, Player] = dataclasses.field(default_factory=dict)

    @property
    def score_red(self) -> str | None:
        if not self.scores:
            return None
        if m := rcon.RE_SCORES.match(self.scores):
            return m["red"]
        return None

    @property
    def score_blue(self) -> str | None:
        if not self.scores:
            return None
        if m := rcon.RE_SCORES.match(self.scores):
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
    def from_dict(cls, g: rcon.Game) -> Self:
        players = [Player.from_dict(p) for p in g["Slots"]]
        if (player_count := g.get("Players", 0)) != len(players):
            msg = (
                f"Player count {player_count} does not match "
                f"players {len(players)}"
                f"\n\n{g}"
            )
            raise RuntimeError(msg)

        if not (map_name := g.get("Map")):
            raise RuntimeError("MAP_NOT_SET", g)

        return cls(
            type=GameType[g["GameType"]],
            time=g["GameTime"],
            map_name=map_name,
            state=GameState.WARMUP if g.get("WarmupPhase") else GameState.LIVE,
            match_mode=g.get("MatchMode", False),
            scores=g.get("Scores"),
            players={p.slot: p for p in players},
        )


class BotCommandConfig(NamedTuple):
    handler: CommandHandler
    name: str
    level: Group = Group.USER
    alias: str | None = None


class Bot(Protocol):
    game: Game

    @property
    @abc.abstractmethod
    def rcon(self) -> rcon.RconClient:
        ...

    @property
    @abc.abstractmethod
    def message_prefix(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def commands(self) -> dict[str, BotCommandConfig]:
        ...

    async def connect_player(self, player: Player) -> None:
        ...

    async def disconnect_player(self, slot: str) -> None:
        ...

    def player(self, slot: str) -> Player | None:
        ...

    def find_player(self, s: str, /) -> list[Player]:
        ...

    async def search_players(self, s: str, /) -> list[Player]:
        ...

    async def sync_player(self, slot: str) -> Player:
        ...


class BotPlugin:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def plugin_load(self) -> None:
        pass

    async def plugin_unload(self) -> None:
        pass


@dataclasses.dataclass
class BotCommand:
    plugin: BotPlugin
    message_type: MessageType
    player: Player
    args: list[str] = dataclasses.field(default_factory=list)

    async def message(
        self, message: str, message_type: MessageType | None = None
    ) -> None:
        prefix = self.plugin.bot.message_prefix + " "
        # TODO: handle wrapping
        if message_type is None:
            message_type = self.message_type
        if message_type is MessageType.PRIVATE:
            prefix += "^8[pm]^7 "
            await self.plugin.bot.rcon.private_message(
                self.player.slot, prefix + message
            )
        elif message_type is MessageType.LOUD:
            await self.plugin.bot.rcon.message(prefix + message)
        else:
            await self.plugin.bot.rcon.bigtext(prefix + message)
