"""
Bot settings and configuration.

When running the Bot, pass the path to the settings file as the first
argument, for example:

    python -m urt30t /path/to/urt30t.toml
"""

import datetime
import functools
import logging
import os
import sys
import tomllib
import zoneinfo
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

__version__ = "2026.03.29"

PACKAGE_ROOT = Path(__file__).parent
PROJECT_ROOT = PACKAGE_ROOT.parent

TRUE_VALUES = frozenset(["true", "1", "yes", "on", "enable"])


class BotSettings(BaseModel, frozen=True):
    name: str = "30+Bot"
    message_prefix: str = "^0(^230+Bot^0)^7:"
    time_format: str = "%I:%M%p %Z %m/%d/%y"
    time_zone_name: str = "UTC"
    games_log: str
    db_url: str
    db_debug: bool = False
    event_queue_max_size: int = 100
    command_prefix: str = "!"
    plugins: list[str] = []
    log_read_delay: float = 0.25
    log_check_truncated: bool = False
    log_replay_from_start: bool = False

    @functools.cached_property
    def time_zone(self) -> zoneinfo.ZoneInfo:
        return zoneinfo.ZoneInfo(self.time_zone_name)


class RconSettings(BaseModel, frozen=True):
    host: str = "127.0.0.1"
    port: int = 27960
    password: Annotated[str, Field(repr=False)]
    recv_timeout: float = 0.25


class LogLevelSettings(BaseModel, frozen=True):
    root: str = "WARNING"
    core: str = "INFO"
    rcon: str = "INFO"
    plugins: str = "INFO"


if "URT30T_CONFIG_FILE" in os.environ:
    _config_file = Path(os.environ["URT30T_CONFIG_FILE"])
elif len(sys.argv) > 1:
    _config_file = Path(sys.argv[1])
else:
    raise RuntimeError("missing_config_file")

with _config_file.open(mode="rb") as fp:
    _config = tomllib.load(fp)

bot = BotSettings(**_config["bot"])
rcon = RconSettings(**_config["rcon"])
log_levels = LogLevelSettings(**_config["log_levels"])

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s:%(funcName)s %(message)s"
)
logging.getLogger().setLevel(log_levels.root)
logging.getLogger("urt30t.core").setLevel(log_levels.core)
logging.getLogger("urt30t.rcon").setLevel(log_levels.rcon)
logging.getLogger("urt30t.plugins").setLevel(log_levels.plugins)

logger = logging.getLogger(__name__)


def now() -> datetime.datetime:
    return datetime.datetime.now(tz=bot.time_zone)
