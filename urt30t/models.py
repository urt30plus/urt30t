import enum
import time
from typing import Any, NamedTuple

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


class Cvar(NamedTuple):
    name: str
    value: str
    default: str | None = None


class Client(BaseModel):
    id: str


class EventType(enum.StrEnum):
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
