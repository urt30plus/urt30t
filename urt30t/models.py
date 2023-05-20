import abc
import dataclasses
import enum
from collections.abc import Awaitable, Callable
from typing import NamedTuple, Protocol

from urt30arcon import AsyncRconClient, Game, Player

CommandHandler = Callable[["BotCommand"], Awaitable[None]]


class BotError(Exception):
    pass


class PlayerNotFoundError(BotError):
    pass


class TooManyPlayersFoundError(BotError):
    def __init__(self, players: list["Player"]) -> None:
        self.players = players


class Group(enum.IntEnum):
    UNKNOWN = -1
    GUEST = 1
    USER = 10
    FRIEND = 20
    MODERATOR = 30
    ADMIN = 100


class MessageType(enum.Enum):
    PRIVATE = 1
    LOUD = 2
    BIG = 3


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


class BotCommandConfig(NamedTuple):
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


class Bot(Protocol):
    game: Game

    @property
    @abc.abstractmethod
    def rcon(self) -> AsyncRconClient:
        ...

    @property
    @abc.abstractmethod
    def command_prefix(self) -> str:
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

    def get_player(self, s: str) -> Player:
        if players := self.bot.find_player(s):
            if len(players) == 1:
                return players[0]
            raise TooManyPlayersFoundError(players)
        raise PlayerNotFoundError(s)


@dataclasses.dataclass
class BotCommand:
    plugin: BotPlugin
    name: str
    message_type: MessageType
    player: Player
    args: list[str] = dataclasses.field(default_factory=list)

    def player_group(self) -> Group:
        # TODO: lookup the player's actual Group
        return Group.GUEST

    async def message(
        self, message: str, message_type: MessageType | None = None
    ) -> None:
        prefix = self.plugin.bot.message_prefix + " "
        if message_type is None:
            message_type = self.message_type
        if message_type is MessageType.PRIVATE:
            prefix += "^8[pm]^7 "
            message = prefix + message
            await self.plugin.bot.rcon.tell(slot=self.player.slot, message=message)
        elif message_type is MessageType.LOUD:
            await self.plugin.bot.rcon.say(message=prefix + message)
        else:
            await self.plugin.bot.rcon.bigtext(message=prefix + message)
