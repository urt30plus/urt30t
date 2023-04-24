"""
Bot settings and configuration.
"""
import logging
import zoneinfo
from pathlib import Path

from pydantic import BaseSettings, Required, root_validator, validator

BASE_PATH = Path(__file__).parent.parent


class SharedSettings(BaseSettings):
    class Config:
        frozen = True
        env_file = BASE_PATH / ".env"


class LogSettings(SharedSettings, env_prefix="URT30T_LOG_"):
    level_root: str = "WARNING"
    level_bot: str = "INFO"
    level_bot_rcon: str = "INFO"
    level_bot_discord30: str = "INFO"


log = LogSettings()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s:%(funcName)s %(message)s"
)
logging.getLogger().setLevel(log.level_root)
logging.getLogger("urt30t").setLevel(log.level_bot)
logging.getLogger("urt30t.rcon").setLevel(log.level_bot_rcon)
logging.getLogger("urt30t.discord30").setLevel(log.level_bot_discord30)

logger = logging.getLogger(__name__)


class FeatureSettings(SharedSettings, env_prefix="URT30T_FEATURE_"):
    log_parsing: bool = True
    event_dispatch: bool = True
    command_dispatch: bool = True
    discord_updates: bool = True

    @validator("event_dispatch", always=True)
    def validate_event_dispatch(
        cls,
        v: bool,  # noqa: FBT001
        values: dict[str, bool],
    ) -> bool:
        if v and not values.get("log_parsing"):
            logger.warning(
                "Event Dispatch is disabled because Log Parsing is not enabled"
            )
            return False
        return v

    @validator("command_dispatch", always=True)
    def validate_command_dispatch(
        cls, v: bool, values: dict[str, bool]  # noqa: FBT001
    ) -> bool:
        if v and not values.get("event_dispatch"):
            logger.warning(
                "Command Dispatch is disabled because Event Dispatch is not enabled"
            )
            return False
        return v

    @root_validator
    def validate_discord_updates(cls, values: dict[str, bool]) -> dict[str, bool]:
        if not any(
            (
                values.get("log_parsing"),
                values.get("event_dispatch"),
                values.get("command_dispatch"),
                values.get("discord_updates"),
            )
        ):
            msg = "At least one feature must be enabled"
            raise ValueError(msg)
        return values


class BotSettings(SharedSettings, env_prefix="URT30T_"):
    name: str = "30+Bot"
    message_prefix: str = "^0(^230+Bot^0)^7:"
    time_format: str = "%I:%M%p %Z %m/%d/%y"
    time_zone: zoneinfo.ZoneInfo = zoneinfo.ZoneInfo("UTC")
    games_log: Path = Required
    # SQLAlchemy url, ex. sqlite+aiosqlite:///file_path
    db_url: str = Required
    event_queue_max_size: int = 100
    plugins: list[str] = []
    log_read_delay: float = 0.250
    log_check_truncated: bool = False

    @validator("time_zone", pre=True)
    def _time_zone_validate(cls, v: str | zoneinfo.ZoneInfo) -> zoneinfo.ZoneInfo:
        if isinstance(v, zoneinfo.ZoneInfo):
            return v
        return zoneinfo.ZoneInfo(v)


class RconSettings(SharedSettings, env_prefix="URT30T_RCON_"):
    host: str = "127.0.0.1"
    port: int = 27960
    password: str = Required
    recv_timeout: float = 0.220


class DiscordSettings(SharedSettings, env_prefix="URT30T_DISCORD_"):
    user: str = Required
    token: str = Required
    server_name: str = Required
    update_channel_name: str = Required
    mapcycle_embed_title: str = Required
    mapcycle_file: str = Required
    mapcycle_update_delay: float = 3600.0
    mapcycle_update_timeout: float = 30.0
    current_map_embed_title: str = Required
    current_map_update_delay: float = 5.0
    current_map_update_delay_no_players: float = 60.0
    current_map_update_timeout: float = 5.0


features = FeatureSettings()
bot = BotSettings()
rcon = RconSettings()

try:
    discord = DiscordSettings()
except Exception as exc:
    logger.warning("Failed to load Discord settings: %r", exc)
    discord = None  # type: ignore[assignment]
