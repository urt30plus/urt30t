"""
Bot settings and configuration.
"""
import logging
from pathlib import Path

from pydantic import BaseSettings, Required

BASE_PATH = Path(__file__).parent.parent


class SharedSettings(BaseSettings):
    class Config:
        frozen = True
        env_file = BASE_PATH / ".env"


class LogSettings(SharedSettings, env_prefix="URT30T_LOG_"):
    level_root: str = "WARNING"
    level_bot: str = "INFO"
    level_bot_rcon: str = "INFO"
    level_discord: str = "WARNING"


class BotSettings(SharedSettings, env_prefix="URT30T_"):
    name: str = "30+Bot"
    prefix: str = "^0(^230+Bot^0)^7:"
    time_format: str = "%I:%M%p %Z %m/%d/%y"
    time_zone: str = "UTC"
    games_log: Path = Required
    # SQLAlchemy url, ex. sqlite+aiosqlite:///file_path
    db_url: str = Required
    event_queue_max_size: int = 100
    plugins: list[str] = []
    log_read_delay: float = 0.250
    log_check_truncated: bool = False


class RconSettings(SharedSettings, env_prefix="URT30T_RCON_"):
    host: str = "127.0.0.1"
    port: int = 27960
    password: str = Required
    recv_timeout: float = 0.220


bot = BotSettings()
log = LogSettings()
rcon = RconSettings()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s:%(funcName)s %(message)s"
)
logging.getLogger().setLevel(log.level_root)
logging.getLogger("urt30t").setLevel(log.level_bot)
logging.getLogger("urt30t.rcon").setLevel(log.level_bot_rcon)
logging.getLogger("discord").setLevel(log.level_discord)
