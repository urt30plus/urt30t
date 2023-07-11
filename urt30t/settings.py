"""
Bot settings and configuration.
"""
import logging
import zoneinfo
from pathlib import Path
from typing import Self

import dotenv
from pydantic import FieldValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings

dotenv.load_dotenv()

BASE_PATH = Path(__file__).parent.parent


class SharedSettings(BaseSettings):
    model_config = {"frozen": True}


class LogSettings(SharedSettings):
    model_config = {"env_prefix": "URT30T_LOG_"}

    level_root: str = "WARNING"
    level_discord: str = "WARNING"
    level_core: str = "INFO"
    level_rcon: str = "INFO"
    level_discord30: str = "INFO"
    level_plugins: str = "INFO"


log = LogSettings()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s:%(funcName)s %(message)s"
)
logging.getLogger().setLevel(log.level_root)
logging.getLogger("discord").setLevel(log.level_discord)
logging.getLogger("urt30t.core").setLevel(log.level_core)
logging.getLogger("urt30t.rcon").setLevel(log.level_rcon)
logging.getLogger("urt30t.discord30").setLevel(log.level_discord30)
logging.getLogger("urt30t.plugins").setLevel(log.level_plugins)

logger = logging.getLogger(__name__)


class FeatureSettings(SharedSettings):
    model_config = {"env_prefix": "URT30T_FEATURE_"}

    log_parsing: bool = True
    event_dispatch: bool = True
    command_dispatch: bool = True
    discord_updates: bool = True

    @field_validator("event_dispatch", mode="before")
    def validate_event_dispatch(
        cls,
        v: bool,  # noqa: FBT001
        info: FieldValidationInfo,
    ) -> bool:
        if v and not info.data.get("log_parsing"):
            logger.warning(
                "Event Dispatch is disabled because Log Parsing is not enabled"
            )
            return False
        return v

    @field_validator("command_dispatch", mode="before")
    def validate_command_dispatch(
        cls, v: bool, info: FieldValidationInfo  # noqa: FBT001
    ) -> bool:
        if v and not info.data.get("event_dispatch"):
            logger.warning(
                "Command Dispatch is disabled because Event Dispatch is not enabled"
            )
            return False
        return v

    @model_validator(mode="after")  # type: ignore[arg-type]
    def _validate_model(cls, self: Self) -> Self:
        if not any(
            (
                self.log_parsing,
                self.event_dispatch,
                self.command_dispatch,
                self.discord_updates,
            )
        ):
            msg = "At least one feature must be enabled"
            raise ValueError(msg)
        return self


class DiscordSettings(SharedSettings):
    model_config = {"env_prefix": "URT30T_DISCORD_"}

    user: str
    token: str
    server_name: str

    updates_channel_name: str

    gameinfo_updates_enabled: bool = True
    gameinfo_embed_title: str
    gameinfo_update_delay: float = 5.0
    gameinfo_update_delay_no_updates: float = 60.0
    gameinfo_update_timeout: float = 5.0

    mapcycle_updates_enabled: bool = True
    mapcycle_embed_title: str
    mapcycle_update_delay: float = 3600.0
    mapcycle_update_timeout: float = 30.0
    mapcycle_file: Path | None = None


class BotSettings(SharedSettings):
    model_config = {"env_prefix": "URT30T_"}

    name: str = "30+Bot"
    message_prefix: str = "^0(^230+Bot^0)^7:"
    time_format: str = "%I:%M%p %Z %m/%d/%y"
    time_zone: zoneinfo.ZoneInfo = zoneinfo.ZoneInfo("UTC")
    games_log: Path
    # SQLAlchemy url, ex. sqlite+aiosqlite:///file_path
    db_url: str
    event_queue_max_size: int = 100
    command_prefix: str = "$"
    plugins: list[str] = []
    log_read_delay: float = 0.250
    log_check_truncated: bool = False
    log_replay_from_start: bool = False
    game_host: str | None = None

    discord: DiscordSettings | None = None

    @field_validator("discord", mode="before")
    def _discord_settings(cls, v: DiscordSettings | None) -> DiscordSettings | None:
        if v is None:
            try:
                v = DiscordSettings()  # type: ignore[call-arg]
            except ValueError:
                logger.exception("Failed to load Discord Settings")
        return v

    @field_validator("time_zone", mode="before")
    def _time_zone_validate(cls, v: str | zoneinfo.ZoneInfo) -> zoneinfo.ZoneInfo:
        if isinstance(v, zoneinfo.ZoneInfo):
            return v
        return zoneinfo.ZoneInfo(v)


class RconSettings(SharedSettings):
    model_config = {"env_prefix": "URT30T_RCON_"}

    host: str = "127.0.0.1"
    port: int = 27960
    password: str
    recv_timeout: float = 0.25


features = FeatureSettings()
bot = BotSettings()  # type: ignore[call-arg]
rcon = RconSettings()  # type: ignore[call-arg]
