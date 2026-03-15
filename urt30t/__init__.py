"""
|30+| UrT Game Bot
"""

from urt30arcon import GameType, Team

from .core import (
    bot_command,
    bot_subscribe,
)
from .models import (
    Bot,
    BotCommand,
    BotError,
    BotPlugin,
    CommandHandler,
    FlagAction,
    Game,
    Group,
    MessageType,
    Player,
)
from .settings import __version__

__all__ = [
    "Bot",
    "BotCommand",
    "BotError",
    "BotPlugin",
    "CommandHandler",
    "FlagAction",
    "Game",
    "GameType",
    "Group",
    "MessageType",
    "Player",
    "Team",
    "__version__",
    "bot_command",
    "bot_subscribe",
]
