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
    level_async_dgram: str = "ERROR"
    level_discord: str = "WARNING"


class BotSettings(SharedSettings, env_prefix="URT30T_"):
    games_log: Path = Required


bot = BotSettings()
log = LogSettings()

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logging.getLogger().setLevel(log.level_root)
logging.getLogger("urt30t").setLevel(log.level_bot)
logging.getLogger("asyncio_dgram").setLevel(log.level_async_dgram)
logging.getLogger("discord").setLevel(log.level_discord)
