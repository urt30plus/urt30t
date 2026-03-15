"""
Bot settings and configuration.

See `etc/urt30t.toml` for the default settings. Copy this
file to another location, can name it anything you like
(e.g. urt30t.toml) and override the settings are needed.
Custom settings will be merged with the defaults, so you only
have to provide the settings you want to change. When running
the Bot, pass the path to the settings file as the first
argument, for example:

    python -m urt30t /path/to/urt30t.toml
"""

import dataclasses
import datetime
import functools
import logging
import os
import sys
import tomllib
import zoneinfo
from pathlib import Path

__version__ = "2026.03.14"

PACKAGE_ROOT = Path(__file__).parent
PROJECT_ROOT = PACKAGE_ROOT.parent

DEFAULTS_CONFIG_FILE = PROJECT_ROOT / "etc" / "urt30t.toml"

TRUE_VALUES = frozenset(["true", "1", "yes", "on", "enable"])


@dataclasses.dataclass(frozen=True)
class BotSettings:
    name: str
    message_prefix: str
    time_format: str
    time_zone_name: str
    games_log: str
    db_url: str
    db_debug: bool
    event_queue_max_size: int
    command_prefix: str
    plugins: list[str]
    log_read_delay: float
    log_check_truncated: bool
    log_replay_from_start: bool

    @functools.cached_property
    def time_zone(self) -> zoneinfo.ZoneInfo:
        return zoneinfo.ZoneInfo(self.time_zone_name)


@dataclasses.dataclass(frozen=True)
class RconSettings:
    host: str
    port: int
    password: str
    recv_timeout: float


@dataclasses.dataclass(frozen=True)
class LogLevelSettings:
    root: str
    core: str
    rcon: str
    plugins: str


with DEFAULTS_CONFIG_FILE.open(mode="rb") as fp:
    _config = tomllib.load(fp)

if "URT30T_CONFIG_FILE" in os.environ:
    _custom_config_file = Path(os.environ["URT30T_CONFIG_FILE"])
elif len(sys.argv) > 1:
    _custom_config_file = Path(sys.argv[1])
else:
    _custom_config_file = None

if _custom_config_file:
    with _custom_config_file.open(mode="rb") as fp:
        _custom_config = tomllib.load(fp)
    _config |= _custom_config

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
