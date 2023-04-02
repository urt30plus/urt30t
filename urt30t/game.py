import enum
import time

from pydantic import BaseModel, Field


class Team(enum.IntEnum):
    UNKNOWN = -1
    FREE = 0
    SPEC = 1
    RED = 2
    BLUE = 3


class PlayerState(enum.IntEnum):
    DEAD = 1
    ALIVE = 2
    UNKNOWN = 3


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


class Game(BaseModel):
    type: GameType = GameType.UNKNOWN
    map_name: str = "unknown"
    map_start_time: float = Field(default_factory=time.time)
    round_start_time: float = Field(default_factory=time.time)
    cap_limit: int | None = None
    frag_imit: int | None = None
    time_limit: int | None = None


class Client(BaseModel):
    id: str
