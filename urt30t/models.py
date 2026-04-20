import dataclasses
import enum
import logging
import re
import time
from collections.abc import Awaitable, Callable

from urt30arcon import (
    AsyncRconClient,
    GameType,
    Team,
)

from . import settings

TYPE_CHECKING = False
if TYPE_CHECKING:
    import asyncio

type CommandHandler = Callable[["BotCommand"], Awaitable[None]]

RE_COLOR = re.compile(r"(\^\d)")

logger = logging.getLogger(__name__)


class BotError(Exception):
    pass


class PlayerNotFoundError(BotError):
    pass


class TooManyPlayersFoundError(BotError):
    def __init__(self, players: list[Player]) -> None:
        self.players = players


class Timer:
    def __init__(self) -> None:
        self._mark = 0.0
        self._elapsed = 0.0

    def start(self) -> None:
        if not self._mark == 0.0:
            raise RuntimeError(self._mark)
        self._mark = time.time()

    def stop(self) -> None:
        if (mark := self._mark) == 0.0:
            raise RuntimeError(mark)
        self._mark = 0.0
        self._elapsed += time.time() - mark

    def elapsed(self) -> float:
        if mark := self._mark:
            return self._elapsed + (time.time() - mark)
        return self._elapsed

    def __repr__(self) -> str:
        return f"Timer({self.elapsed()})"


class Group(enum.IntEnum):
    GUEST = 1
    USER = 10
    FRIEND = 20
    MODERATOR = 30
    ADMIN = 100


class Penalty(enum.Enum):
    kick = "kick"
    tempban = "tempban"
    permban = "permban"


class MessageType(enum.Enum):
    PRIVATE = 1
    LOUD = 2
    BIG = 3


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


@dataclasses.dataclass
class Player:
    slot: str
    name: str
    name_exact: str = ""
    auth: str = ""
    guid: str = ""
    team: Team = Team.SPECTATOR
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    ip_address: str | None = None
    db_id: int | None = None
    group: Group = Group.GUEST
    xp: float = 0.0

    alive_timer: Timer = dataclasses.field(default_factory=Timer)

    def calc_xp(self) -> float:
        if play_time := self.alive_timer.elapsed():
            points = self.kills + (self.assists * 0.25)
            return points / play_time
        return 0.0

    def update_name(self, name: str) -> None:
        clean_name = RE_COLOR.sub("", name)
        self.name_exact = name
        self.name = clean_name

    def update_team(self, team: Team) -> None:
        self.team = team

    def __post_init__(self) -> None:
        if not self.name_exact:
            self.update_name(self.name)


@dataclasses.dataclass
class Server:
    map_list: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Game:
    map_name: str = ""
    type: GameType = GameType.FFA
    warmup: bool = False
    match_mode: bool = False
    score_red: int = 0
    score_blue: int = 0
    players: dict[str, Player] = dataclasses.field(default_factory=dict)

    def find_player(self, s: str, /) -> list[Player]:
        if len(s) <= 3 and s.isdigit():  # noqa: PLR2004
            p = self.players.get(s)
            return [p] if p else []
        needle = s.lower()
        return [
            p for p in self.players.values() if needle in p.name or needle == p.auth
        ]

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


@dataclasses.dataclass
class BotCommandConfig:
    handler: CommandHandler
    name: str
    level: Group = Group.USER
    alias: str | None = None
    args_required: int = 0
    args_optional: int = 0

    @property
    def min_args(self) -> int:
        return self.args_required

    @property
    def max_args(self) -> int:
        return self.args_required + self.args_optional


@dataclasses.dataclass
class BotContext:
    game: Game
    server: Server
    rcon: AsyncRconClient
    task_group: asyncio.TaskGroup

    async def sync_player(self, slot: str) -> Player:
        if not (player := self.game.players.get(slot)):
            raise BotError("invalid_slot", slot)

        if not (player.guid and player.auth):
            if userinfo := await self.rcon.dumpuser(slot):
                player.guid = userinfo["cl_guid"]
                player.auth = userinfo["authl"]
            else:
                logger.error("dumpuser failed for slot [%s]", slot)

        if not player.db_id:
            # TODO: await db.sync_player(player)
            # TODO: check for bans
            pass

        logger.info("%r", player)
        return player


@dataclasses.dataclass
class BotCommand:
    context: BotContext
    name: str
    message_type: MessageType
    player: Player
    args: list[str] = dataclasses.field(default_factory=list)

    def get_player(self, s: str) -> Player:
        if players := self.find_player(s):
            if len(players) == 1:
                return players[0]
            raise TooManyPlayersFoundError(players)
        raise PlayerNotFoundError(s)

    def find_player(self, s: str, /) -> list[Player]:
        if len(s) <= 3 and s.isdigit():  # noqa: PLR2004
            p = self.get_player(s)
            return [p] if p else []
        needle = s.lower()
        return [
            p
            for p in self.context.game.players.values()
            if needle in p.name or needle == p.auth
        ]

    async def message(
        self, message: str, message_type: MessageType | None = None
    ) -> None:
        prefix = settings.bot.message_prefix + " "
        if message_type is None:
            message_type = self.message_type
        if message_type is MessageType.PRIVATE:
            prefix += "^8[pm]^7 "
            message = prefix + message
            await self.context.rcon.tell(slot=self.player.slot, message=message)
        elif message_type is MessageType.LOUD:
            await self.context.rcon.say(message=prefix + message)
        else:
            await self.context.rcon.bigtext(message=prefix + message)
